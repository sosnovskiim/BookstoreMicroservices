from datetime import datetime
from pydantic import BaseModel, Field


# HTTP-схемы Sales.

class OrderItemRequest(BaseModel):
    book_id: int
    quantity: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    """Тело POST /orders. customer_id берётся из JWT, не из тела."""
    payment_method_id: int
    delivery_id: int | None = None
    items: list[OrderItemRequest]


class OrderItemResponse(BaseModel):
    book_id: int
    quantity: int


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    payment_method_id: int
    delivery_id: int | None
    total_cost: int
    status: str
    time: datetime | None
    items: list[OrderItemResponse]
