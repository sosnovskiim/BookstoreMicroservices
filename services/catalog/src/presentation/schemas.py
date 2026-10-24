from datetime import date
from pydantic import BaseModel, Field


# Pydantic-схемы HTTP-слоя. from_attributes — чтобы создавать из доменных объектов.

class BookResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    description: str
    category_id: int
    publisher_id: int
    isbn: str
    age_limit: str
    publication_date: str
    pages_number: int
    weight: int
    price: int


class CreateBookRequest(BaseModel):
    """Тело админского POST /books. Валидаторы повторяют CHECK'и из БД."""
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1)
    category_id: int
    publisher_id: int
    isbn: str = Field(min_length=1, max_length=32)
    age_limit: str = Field(min_length=1, max_length=4)
    publication_date: str = Field(min_length=4, max_length=4)
    pages_number: int = Field(gt=0)
    weight: int = Field(gt=0)
    price: int = Field(gt=0)


class ReviewResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    book_id: int
    customer_id: int
    date: date
    rating: int
    text: str | None


class CreateReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str | None = None
