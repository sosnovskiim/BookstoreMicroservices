from datetime import datetime, timezone

from ..domain.order import Order, OrderItem, OrderStatus


class CreateOrder:
    """
    Use case: создание заказа.
    1. Проверяет, что клиент есть в Sales (иначе FK упадёт на вставке).
    2. Синхронно тянет цены из Catalog через gRPC (требование 10).
    3. Считает total_cost, сохраняет Order(PENDING) + outbox (требование 8).
    """
    def __init__(self, orders, outbox, catalog, commit):
        self.orders = orders
        self.outbox = outbox
        self.catalog = catalog
        self._commit = commit

    async def execute(self, customer_id: int, payment_method_id: int,
                      delivery_id: int | None,
                      items: list[dict]) -> Order:
        if not items:
            raise ValueError("empty_order")
        if not await self.orders.customer_exists(customer_id):
            raise ValueError("customer_not_registered")

        book_ids = list({it["book_id"] for it in items})
        prices = await self.catalog.get_prices(book_ids)

        # Все книги должны существовать в каталоге — иначе заказ не имеет смысла.
        missing = [bid for bid in book_ids if bid not in prices]
        if missing:
            raise ValueError(f"books_not_found:{missing}")

        order_items = [
            OrderItem(book_id=it["book_id"], quantity=it["quantity"],
                      price=prices[it["book_id"]])
            for it in items
        ]
        total = sum(i.price * i.quantity for i in order_items)
        if total <= 0:
            raise ValueError("total_cost_must_be_positive")

        order = Order(
            id=None, customer_id=customer_id, payment_method_id=payment_method_id,
            delivery_id=delivery_id, total_cost=total,
            status=OrderStatus.PENDING, items=order_items,
            time=datetime.now(tz=timezone.utc),
        )
        saved = await self.orders.create(order)

        # Событие о создании заказа: Inventory по нему попробует зарезервировать.
        await self.outbox.enqueue(
            "sales.order.created",
            {
                "order_id": saved.id,
                "items": [{"book_id": i.book_id, "quantity": i.quantity}
                          for i in order_items],
            },
        )
        await self._commit()
        return saved


class GetOrder:
    """Получить заказ с позициями — используется и HTTP, и consumer'ом."""
    def __init__(self, orders):
        self.orders = orders

    async def execute(self, order_id: int) -> Order | None:
        return await self.orders.get_by_id(order_id)


class ListOrders:
    """Все заказы клиента из JWT."""
    def __init__(self, orders):
        self.orders = orders

    async def execute(self, customer_id: int) -> list[Order]:
        return await self.orders.list_by_customer(customer_id)


class HandleInventoryResult:
    """
    Use case consumer'а: обработка inventory.stock.reserved / rejected.
    Идемпотентность через inbox, статус Order меняется атомарно.
    """
    def __init__(self, orders, inbox, commit):
        self.orders = orders
        self.inbox = inbox
        self._commit = commit

    async def execute(self, event_id: str, event_type: str, payload: dict) -> None:
        if await self.inbox.is_processed(event_id):
            return

        order_id = payload["order_id"]
        # События двух видов: успех и отказ.
        if event_type == "inventory.stock.reserved":
            await self.orders.update_status(order_id, OrderStatus.CONFIRMED.value)
        elif event_type == "inventory.stock.rejected":
            await self.orders.update_status(order_id, OrderStatus.CANCELLED.value)

        await self.inbox.mark_processed(event_id, event_type)
        await self._commit()
