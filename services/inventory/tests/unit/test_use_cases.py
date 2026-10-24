import pytest
from src.domain.stock import StockItem
from src.domain.purchase import PurchaseItem
from src.application.use_cases import (
    ListStock, GetStock, TopUpStock, CreatePurchase, HandleOrderCreated,
)


# --- in-memory фейки ---

class FakeStockRepo:
    def __init__(self, initial: dict[int, StockItem] | None = None):
        self._data = dict(initial or {})
    async def get(self, book_id): return self._data.get(book_id)
    async def list_all(self): return list(self._data.values())
    async def save(self, item):
        self._data[item.book_id] = item
        return item
    async def top_up(self, book_id, amount):
        if book_id not in self._data: return None
        self._data[book_id].quantity += amount
        return self._data[book_id]
    async def top_up_reserved(self, book_id, amount):
        self._data[book_id].reserved += amount


class FakePurchaseRepo:
    def __init__(self): self.created = []
    async def create(self, p):
        p.id = len(self.created) + 1
        self.created.append(p)
        return p


class FakeOutbox:
    def __init__(self): self.events = []
    async def enqueue(self, event_type, payload):
        self.events.append((event_type, payload))


class FakeInbox:
    def __init__(self): self.processed = set()
    async def is_processed(self, event_id): return event_id in self.processed
    async def mark_processed(self, event_id, event_type): self.processed.add(event_id)


class FakeCommit:
    def __init__(self): self.calls = 0
    async def __call__(self): self.calls += 1


# --- Stock use cases ---

async def test_list_and_get_stock():
    repo = FakeStockRepo({1: StockItem(book_id=1, quantity=5, reserved=1)})
    lst = await ListStock(repo).execute()
    assert lst[0].book_id == 1 and lst[0].available == 4
    assert (await GetStock(repo).execute(1)).quantity == 5
    assert await GetStock(repo).execute(999) is None


async def test_top_up_existing():
    repo = FakeStockRepo({1: StockItem(book_id=1, quantity=5)})
    item = await TopUpStock(repo).execute(1, 3)
    assert item.quantity == 8


async def test_top_up_creates_missing():
    """Если книги нет в stock_items — создаём запись и пополняем."""
    repo = FakeStockRepo({})
    item = await TopUpStock(repo).execute(42, 7)
    assert item.book_id == 42 and item.quantity == 7


async def test_top_up_rejects_nonpositive():
    repo = FakeStockRepo({})
    with pytest.raises(ValueError, match="amount_must_be_positive"):
        await TopUpStock(repo).execute(1, 0)


# --- Purchase use case ---

async def test_create_purchase_increases_stock():
    stocks = FakeStockRepo({1: StockItem(book_id=1, quantity=0)})
    purchases = FakePurchaseRepo()
    p = await CreatePurchase(purchases, stocks).execute(
        supplier_id=1, total_cost=1000,
        items=[PurchaseItem(book_id=1, quantity=3)],
    )
    assert p.id == 1
    assert stocks._data[1].quantity == 3


async def test_create_purchase_empty_items():
    with pytest.raises(ValueError, match="empty_purchase"):
        await CreatePurchase(FakePurchaseRepo(), FakeStockRepo()).execute(1, 100, [])


# --- HandleOrderCreated: ключевой сценарий саги ---

def _build_uc(stocks, inbox, outbox):
    return HandleOrderCreated(
        stocks=stocks, inbox=inbox, outbox=outbox,
        session=None, commit=FakeCommit(),
    )


async def test_handle_order_created_reserves_stock():
    """Достаточно остатков — резервируем и пишем inventory.stock.reserved."""
    stocks = FakeStockRepo({
        1: StockItem(book_id=1, quantity=10, reserved=0),
        2: StockItem(book_id=2, quantity=5, reserved=1),
    })
    inbox, outbox = FakeInbox(), FakeOutbox()
    await _build_uc(stocks, inbox, outbox).execute(
        event_id="11111111-1111-1111-1111-111111111111",
        payload={"order_id": 42, "items": [{"book_id": 1, "quantity": 2},
                                          {"book_id": 2, "quantity": 1}]},
    )
    assert stocks._data[1].reserved == 2
    assert stocks._data[2].reserved == 2
    assert outbox.events == [("inventory.stock.reserved", {"order_id": 42})]
    assert "11111111-1111-1111-1111-111111111111" in inbox.processed


async def test_handle_order_created_rejects_when_insufficient():
    """Остатков не хватает — пишем inventory.stock.rejected, остатки не трогаем."""
    stocks = FakeStockRepo({1: StockItem(book_id=1, quantity=1, reserved=0)})
    inbox, outbox = FakeInbox(), FakeOutbox()
    await _build_uc(stocks, inbox, outbox).execute(
        event_id="22222222-2222-2222-2222-222222222222",
        payload={"order_id": 42, "items": [{"book_id": 1, "quantity": 5}]},
    )
    assert stocks._data[1].reserved == 0
    assert outbox.events[0][0] == "inventory.stock.rejected"
    assert outbox.events[0][1]["order_id"] == 42


async def test_handle_order_created_idempotent():
    """Повторный event_id — второй раз ничего не делаем (inbox)."""
    stocks = FakeStockRepo({1: StockItem(book_id=1, quantity=10)})
    inbox = FakeInbox()
    inbox.processed.add("33333333-3333-3333-3333-333333333333")
    outbox = FakeOutbox()
    await _build_uc(stocks, inbox, outbox).execute(
        event_id="33333333-3333-3333-3333-333333333333",
        payload={"order_id": 42, "items": [{"book_id": 1, "quantity": 1}]},
    )
    assert outbox.events == []
    assert stocks._data[1].reserved == 0
