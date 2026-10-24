from pydantic import BaseModel, Field


# Pydantic-схемы HTTP-слоя Inventory.

class StockResponse(BaseModel):
    book_id: int
    quantity: int
    reserved: int
    available: int


class TopUpRequest(BaseModel):
    amount: int = Field(gt=0)


class PurchaseItemRequest(BaseModel):
    book_id: int
    quantity: int = Field(gt=0)


class CreatePurchaseRequest(BaseModel):
    supplier_id: int
    total_cost: int = Field(gt=0)
    items: list[PurchaseItemRequest]
