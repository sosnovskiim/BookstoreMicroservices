import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, select, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from ..domain.order import Order as OrderEntity, OrderItem as OrderItemEntity, OrderStatus


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей Sales."""
    pass


class OrderModel(Base):
    """sales.orders — заголовок заказа."""
    __tablename__ = "orders"
    __table_args__ = {"schema": "sales"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer)
    payment_method_id: Mapped[int] = mapped_column(Integer)
    delivery_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_cost: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")


class OrderItemModel(Base):
    """sales.books_orders — строки заказа. price хранится как снимок на момент заказа."""
    __tablename__ = "books_orders"
    __table_args__ = {"schema": "sales"}
    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)


class CustomerModel(Base):
    """sales.customers — профиль клиента (ID совпадает с identity.users.id по seed)."""
    __tablename__ = "customers"
    __table_args__ = {"schema": "sales"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(32))


class OutboxModel(Base):
    """sales.outbox — transaction outbox (требование 8)."""
    __tablename__ = "outbox"
    __table_args__ = {"schema": "sales"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class InboxModel(Base):
    """sales.inbox — идемпотентная обработка входящих (требование 8)."""
    __tablename__ = "inbox"
    __table_args__ = {"schema": "sales"}
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128))
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# search_path=sales — имена таблиц резолвятся в нужную схему.
engine = create_async_engine(
    settings.database_url,
    connect_args={"server_settings": {"search_path": "sales"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class SqlOrderRepository:
    """Реализация OrderRepository поверх SQLAlchemy."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _load_items(self, order_id: int) -> list[OrderItemEntity]:
        """Отдельный запрос — у нас нет relationship, чтобы не тянуть ORM-магию."""
        rows = (await self.session.execute(
            select(OrderItemModel).where(OrderItemModel.order_id == order_id)
        )).scalars().all()
        # Цена снимка хранится в orders (агрегат) — здесь только book_id/qty.
        # Price подтянем из Order при сборке — упрощённый вариант для учебного проекта.
        return [OrderItemEntity(book_id=r.book_id, quantity=r.quantity, price=0) for r in rows]

    async def create(self, order: OrderEntity) -> OrderEntity:
        row = OrderModel(
            customer_id=order.customer_id,
            payment_method_id=order.payment_method_id,
            delivery_id=order.delivery_id,
            total_cost=order.total_cost,
            status=order.status.value if hasattr(order.status, "value") else order.status,
        )
        self.session.add(row)
        await self.session.flush()  # получить order.id до commit
        for it in order.items:
            self.session.add(OrderItemModel(
                order_id=row.id, book_id=it.book_id, quantity=it.quantity,
            ))
        await self.session.flush()
        order.id = row.id
        order.time = row.time
        return order

    async def get_by_id(self, order_id: int) -> OrderEntity | None:
        row = await self.session.get(OrderModel, order_id)
        if row is None:
            return None
        items = await self._load_items(order_id)
        return OrderEntity(
            id=row.id, customer_id=row.customer_id,
            payment_method_id=row.payment_method_id, delivery_id=row.delivery_id,
            total_cost=row.total_cost, status=OrderStatus(row.status),
            items=items, time=row.time,
        )

    async def list_by_customer(self, customer_id: int) -> list[OrderEntity]:
        rows = (await self.session.execute(
            select(OrderModel).where(OrderModel.customer_id == customer_id)
            .order_by(OrderModel.id.desc())
        )).scalars().all()
        orders = []
        for row in rows:
            items = await self._load_items(row.id)
            orders.append(OrderEntity(
                id=row.id, customer_id=row.customer_id,
                payment_method_id=row.payment_method_id, delivery_id=row.delivery_id,
                total_cost=row.total_cost, status=OrderStatus(row.status),
                items=items, time=row.time,
            ))
        return orders

    async def update_status(self, order_id: int, status: str) -> None:
        row = await self.session.get(OrderModel, order_id)
        if row is not None:
            row.status = status

    async def customer_exists(self, customer_id: int) -> bool:
        return (await self.session.get(CustomerModel, customer_id)) is not None


class SqlOutbox:
    """EventPublisher через inventory.outbox."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(self, event_type: str, payload: dict) -> None:
        self.session.add(OutboxModel(event_type=event_type, payload=payload))


class SqlInbox:
    """InboxRepository для consumer'а."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_processed(self, event_id: str) -> bool:
        try:
            uid = uuid.UUID(event_id)
        except (ValueError, TypeError):
            return False
        return (await self.session.get(InboxModel, uid)) is not None

    async def mark_processed(self, event_id: str, event_type: str) -> None:
        self.session.add(InboxModel(event_id=uuid.UUID(event_id), event_type=event_type))
