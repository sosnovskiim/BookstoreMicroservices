from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PurchaseItem:
    """Строка закупки (book + количество)."""
    book_id: int
    quantity: int


@dataclass
class Purchase:
    """Агрегат Purchase — закупка у поставщика."""
    id: int | None
    supplier_id: int
    total_cost: int
    items: list[PurchaseItem] = field(default_factory=list)
    time: datetime | None = None
