from dataclasses import dataclass
from datetime import date as DateType


@dataclass
class Review:
    """ Агрегат Review — отдельный корень внутри контекста Catalog. """
    id: int | None
    book_id: int
    customer_id: int
    date: DateType
    rating: int
    text: str | None
