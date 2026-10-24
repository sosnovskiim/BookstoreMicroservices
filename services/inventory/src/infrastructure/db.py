import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, select, update
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from ..domain.stock import StockItem as StockEntity
from ..domain.purchase import Purchase as PurchaseEntity, PurchaseItem


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей Inventory."""
    pass


class StockItemModel(Base):
    """inventory.stock_items — остаток книги."""
    __tablename__ = "stock_items"
    __table_args__ = {"schema": "inventory"}
    book_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class SupplierModel(Base):
    """inventory.suppliers — поставщик (справочник)."""
    __tablename__ = "suppliers"
    __table_args__ = {"schema": "inventory"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))


class PurchaseModel(Base):
    """inventory.purchases — закупка."""
    __tablename__ = "purchases"
    __table_args__ = {"schema": "inventory"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(Integer)
    time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_cost: Mapped[int] = mapped_column(Integer)


class PurchaseItemModel(Base):
    """inventory.books_purchases — строки закупки."""
    __tablename__ = "books_purchases"
    __table_args__ = {"schema": "inventory"}
    purchase_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)


class OutboxModel(Base):
    """inventory.outbox — transaction outbox (требование 8)."""
    __tablename__ = "outbox"
    __table_args__ = {"schema": "inventory"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class InboxModel(Base):
    """inventory.inbox — идемпотентная обработка входящих (требование 8)."""
    __tablename__ = "inbox"
    __table_args__ = {"schema": "inventory"}
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128))
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# search_path=inventory — имена таблиц резолвятся в нужную схему.
engine = create_async_engine(
    settings.database_url,
    connect_args={"server_settings": {"search_path": "inventory"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# --- Репозитории ---

class SqlStockRepository:
    """StockRepository поверх SQLAlchemy."""
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, row: StockItemModel) -> StockEntity:
        return StockEntity(book_id=row.book_id, quantity=row.quantity, reserved=row.reserved)

    async def get(self, book_id: int) -> StockEntity | None:
        row = await self.session.get(StockItemModel, book_id)
        return self._to_entity(row) if row else None

    async def list_all(self) -> list[StockEntity]:
        rows = (await self.session.execute(
            select(StockItemModel).order_by(StockItemModel.book_id)
        )).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def save(self, item: StockEntity) -> StockEntity:
        row = StockItemModel(book_id=item.book_id, quantity=item.quantity,
                             reserved=item.reserved)
        self.session.add(row)
        await self.session.commit()
        return item

    async def top_up(self, book_id: int, amount: int) -> StockEntity | None:
        """Атомарно увеличивает quantity. Возвращает None, если записи нет."""
        result = await self.session.execute(
            update(StockItemModel)
            .where(StockItemModel.book_id == book_id)
            .values(quantity=StockItemModel.quantity + amount)
            .returning(StockItemModel)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def top_up_reserved(self, book_id: int, amount: int) -> None:
        """Увеличивает reserved (это и есть резервирование)."""
        await self.session.execute(
            update(StockItemModel)
            .where(StockItemModel.book_id == book_id)
            .values(reserved=StockItemModel.reserved + amount)
        )


class SqlPurchaseRepository:
    """PurchaseRepository поверх SQLAlchemy."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, purchase: PurchaseEntity) -> PurchaseEntity:
        row = PurchaseModel(supplier_id=purchase.supplier_id, total_cost=purchase.total_cost)
        self.session.add(row)
        await self.session.flush()  # получить id до commit
        for it in purchase.items:
            self.session.add(PurchaseItemModel(
                purchase_id=row.id, book_id=it.book_id, quantity=it.quantity,
            ))
        await self.session.commit()
        await self.session.refresh(row)
        purchase.id = row.id
        purchase.time = row.time
        return purchase


# --- Outbox/Inbox ---

class SqlOutbox:
    """Реализация EventPublisher: пишет события в inventory.outbox."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(self, event_type: str, payload: dict) -> None:
        self.session.add(OutboxModel(event_type=event_type, payload=payload))


class SqlInbox:
    """Реализация InboxRepository: идемпотентность consumer'а."""
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
