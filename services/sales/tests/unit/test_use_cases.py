import pytest
from src.domain.order import Order, OrderStatus
from src.application.use_cases import CreateOrder, GetOrder, HandleInventoryResult


# --- in-memory фейки ---

class FakeOrderRepo:
    def __init__(self, known_customers=None):
        self._orders: dict[int, Order] = {}
        self._customers = known_customers or {1, 2, 3}
    async def create(self, order):
        order.id = len(self._orders) + 1
        self._orders[order.id] = order
        return order
    async def get_by_id(self, order_id): return self._orders.get(order_id)
    async def list_by_customer(self, cid):
        return [o for o in self._orders.values() if o.customer_id == cid]
    async def update_status(self, order_id, status):
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus(status)
    async def customer_exists(self, cid): return cid in self._customers


class FakeOutbox:
    def __init__(self): self.events = []
    async def enqueue(self, event_type, payload):
        self.events.append((event_type, payload))


class FakeInbox:
    def __init__(self, pre_processed=None):
        self.processed = set(pre_processed or [])
    async def is_processed(self, eid): return eid in self.processed
    async def mark_processed(self, eid, et): self.processed.add(eid)


class FakeCatalog:
    def __init__(self, prices: dict[int, int] | None = None, fail: bool = False):
        self.prices = prices or {}
        self.fail = fail
    async def get_prices(self, ids):
        if self.fail:
            raise RuntimeError("catalog_unavailable:UNAVAILABLE")
        return {bid: self.prices[bid] for bid in ids if bid in self.prices}


class FakeCommit:
    def __init__(self): self.calls = 0
    async def __call__(self): self.calls += 1


# --- CreateOrder ---

def _uc_create(repo, outbox, catalog):
    return CreateOrder(repo, outbox, catalog, FakeCommit())


async def test_create_order_success():
    repo = FakeOrderRepo()
    outbox = FakeOutbox()
    catalog = FakeCatalog(prices={1: 700, 2: 800})
    order = await _uc_create(repo, outbox, catalog).execute(
        customer_id=1, payment_method_id=1, delivery_id=None,
        items=[{"book_id": 1, "quantity": 2}, {"book_id": 2, "quantity": 1}],
    )
    assert order.id == 1
    assert order.total_cost == 700 * 2 + 800 * 1
    assert order.status == OrderStatus.PENDING
    assert outbox.events[0][0] == "sales.order.created"
    assert outbox.events[0][1]["order_id"] == 1
    assert outbox.events[0][1]["items"] == [
        {"book_id": 1, "quantity": 2}, {"book_id": 2, "quantity": 1},
    ]


async def test_create_order_empty_items():
    with pytest.raises(ValueError, match="empty_order"):
        await _uc_create(FakeOrderRepo(), FakeOutbox(), FakeCatalog()).execute(
            1, 1, None, [],
        )


async def test_create_order_customer_missing():
    with pytest.raises(ValueError, match="customer_not_registered"):
        await _uc_create(FakeOrderRepo(known_customers={1}), FakeOutbox(),
                         FakeCatalog()).execute(99, 1, None,
                                               [{"book_id": 1, "quantity": 1}])


async def test_create_order_book_missing():
    with pytest.raises(ValueError, match="books_not_found"):
        await _uc_create(FakeOrderRepo(), FakeOutbox(),
                         FakeCatalog(prices={1: 100})).execute(
            1, 1, None, [{"book_id": 1, "quantity": 1}, {"book_id": 2, "quantity": 1}],
        )


async def test_create_order_catalog_down():
    with pytest.raises(RuntimeError, match="catalog_unavailable"):
        await _uc_create(FakeOrderRepo(), FakeOutbox(),
                         FakeCatalog(fail=True)).execute(
            1, 1, None, [{"book_id": 1, "quantity": 1}],
        )


# --- HandleInventoryResult ---

def _uc_handle(repo, inbox):
    return HandleInventoryResult(repo, inbox, FakeCommit())


async def _seed_order(repo) -> int:
    o = Order(id=None, customer_id=1, payment_method_id=1, delivery_id=None,
              total_cost=500, status=OrderStatus.PENDING, items=[])
    await repo.create(o)
    return o.id


async def test_handle_reserved_confirms_order():
    repo = FakeOrderRepo()
    oid = await _seed_order(repo)
    inbox = FakeInbox()
    await _uc_handle(repo, inbox).execute(
        event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        event_type="inventory.stock.reserved",
        payload={"order_id": oid},
    )
    assert (await repo.get_by_id(oid)).status == OrderStatus.CONFIRMED
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in inbox.processed


async def test_handle_rejected_cancels_order():
    repo = FakeOrderRepo()
    oid = await _seed_order(repo)
    await _uc_handle(repo, FakeInbox()).execute(
        event_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        event_type="inventory.stock.rejected",
        payload={"order_id": oid},
    )
    assert (await repo.get_by_id(oid)).status == OrderStatus.CANCELLED


async def test_handle_idempotent():
    """Повторный event_id не должен менять статус."""
    repo = FakeOrderRepo()
    oid = await _seed_order(repo)
    inbox = FakeInbox(pre_processed={"cccccccc-cccc-cccc-cccc-cccccccccccc"})
    await _uc_handle(repo, inbox).execute(
        event_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        event_type="inventory.stock.reserved",
        payload={"order_id": oid},
    )
    # Статус остался PENDING, потому что event уже в inbox.
    assert (await repo.get_by_id(oid)).status == OrderStatus.PENDING
