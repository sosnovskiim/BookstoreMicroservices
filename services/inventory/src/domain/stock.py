from dataclasses import dataclass


@dataclass
class StockItem:
    """
    Агрегат StockItem — остаток конкретной книги.
    available — вычисляемое: сколько можно продать (не зарезервировано).
    """
    book_id: int
    quantity: int
    reserved: int = 0

    @property
    def available(self) -> int:
        return max(self.quantity - self.reserved, 0)
