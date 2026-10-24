from datetime import datetime, timezone
from ..domain.stock import StockItem
from ..domain.purchase import Purchase, PurchaseItem


class ListStock:
    """Список всех остатков (публичный эндпоинт)."""
    def __init__(self, stocks):
        self.stocks = stocks

    async def execute(self) -> list[StockItem]:
        return await self.stocks.list_all()


class GetStock:
    """Остаток конкретной книги."""
    def __init__(self, stocks):
        self.stocks = stocks

    async def execute(self, book_id: int) -> StockItem | None:
        return await self.stocks.get(book_id)


class TopUpStock:
    """
    Пополнение остатка (админ). Если книги нет в stock_items — создаём запись.
    Используется в т.ч. для тестов саги.
    """
    def __init__(self, stocks):
        self.stocks = stocks

    async def execute(self, book_id: int, amount: int) -> StockItem:
        if amount <= 0:
            raise ValueError("amount_must_be_positive")
        item = await self.stocks.top_up(book_id, amount)
        if item is None:
            # создаём запись нулевой и повторяем пополнение
            await self.stocks.save(StockItem(book_id=book_id, quantity=0, reserved=0))
            item = await self.stocks.top_up(book_id, amount)
        return item


class CreatePurchase:
    """Оформление закупки: создаёт Purchase и увеличивает остатки по каждой строке."""
    def __init__(self, purchases, stocks):
        self.purchases = purchases
        self.stocks = stocks

    async def execute(self, supplier_id: int, total_cost: int,
                      items: list[PurchaseItem]) -> Purchase:
        if not items:
            raise ValueError("empty_purchase")
        if total_cost <= 0:
            raise ValueError("total_cost_must_be_positive")

        purchase = Purchase(
            id=None, supplier_id=supplier_id, total_cost=total_cost,
            items=items, time=datetime.now(tz=timezone.utc),
        )
        saved = await self.purchases.create(purchase)
        # Каждое пополнение по строке — отдельная операция поверх stock.
        for it in items:
            await self.stocks.top_up(it.book_id, it.quantity)
        return saved


class HandleOrderCreated:
    """
    Use case consumer'а: обработка события sales.order.created.
    Идемпотентность через inbox. Результат пишется в outbox
    в ТОЙ ЖЕ транзакции (требования 7–9).
    """
    def __init__(self, stocks, inbox, outbox, session, commit):
        self.stocks = stocks
        self.inbox = inbox
        self.outbox = outbox
        self.session = session  # для commit атомарной транзакции
        self._commit = commit

    async def execute(self, event_id: str, payload: dict) -> None:
        # 1. Идемпотентность: уже обработали — выходим.
        if await self.inbox.is_processed(event_id):
            return

        order_id = payload["order_id"]
        items = payload["items"]

        # 2. Проверяем остатки по всем строкам. Если хоть что-то не хватает — отказ.
        sufficient = True
        for it in items:
            stock = await self.stocks.get(it["book_id"])
            available = (stock.quantity - stock.reserved) if stock else 0
            if available < it["quantity"]:
                sufficient = False
                break

        # 3. В зависимости от результата пишем одно из двух событий.
        if sufficient:
            for it in items:
                await self.stocks.top_up_reserved(it["book_id"], it["quantity"])
            await self.outbox.enqueue("inventory.stock.reserved", {"order_id": order_id})
        else:
            await self.outbox.enqueue(
                "inventory.stock.rejected",
                {"order_id": order_id, "reason": "insufficient_stock"},
            )

        # 4. Фиксируем факт обработки (inbox) — в той же транзакции.
        await self.inbox.mark_processed(event_id, "sales.order.created")
        await self._commit()
