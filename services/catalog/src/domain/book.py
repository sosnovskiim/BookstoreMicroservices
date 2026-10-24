from dataclasses import dataclass


@dataclass
class Book:
    """
    Агрегат Book — корень каталога.
    Чистая доменная сущность: не знает ни про ORM, ни про HTTP.
    """
    id: int | None
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
