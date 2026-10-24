from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    """Статусы заказа. Меняются в ходе саги (требование 7)."""
    PENDING = "PENDING"  # создан, ждём ответ Inventory
    CONFIRMED = "CONFIRMED"  # inventory.stock.reserved
    CANCELLED = "CANCELLED"  # inventory.stock.rejected


@dataclass
class OrderItem:
    """Строка заказа: какая книга и сколько."""
    book_id: int
    quantity: int
    price: int  # цена на момент оформления (снимок)


@dataclass
class Order:
    """
    Агрегат Order — корень контекста Sales.
    total_cost и items фиксируются при создании; status меняется сагой.
    """
    id: int | None
    customer_id: int
    payment_method_id: int
    delivery_id: int | None
    total_cost: int
    status: OrderStatus = OrderStatus.PENDING
    items: list[OrderItem] = field(default_factory=list)
    time: datetime | None = None
