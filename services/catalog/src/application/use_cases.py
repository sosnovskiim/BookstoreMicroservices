from ..domain.book import Book
from ..domain.review import Review
from .ports import BookRepository, ReviewRepository


# --- Книги ---

class ListBooks:
    """Use case: получить все книги каталога."""
    def __init__(self, books: BookRepository):
        self.books = books

    async def execute(self) -> list[Book]:
        return await self.books.list_all()


class GetBook:
    """Use case: получить книгу по id."""
    def __init__(self, books: BookRepository):
        self.books = books

    async def execute(self, book_id: int) -> Book | None:
        return await self.books.get_by_id(book_id)


class CreateBook:
    """Use case: создать книгу (вызывается только из админского эндпоинта)."""
    def __init__(self, books: BookRepository):
        self.books = books

    async def execute(self, book: Book) -> Book:
        return await self.books.add(book)


class DeleteBook:
    """Use case: удалить книгу по id."""
    def __init__(self, books: BookRepository):
        self.books = books

    async def execute(self, book_id: int) -> bool:
        return await self.books.delete(book_id)


# --- Отзывы ---

class CreateReview:
    """Use case: оставить отзыв. Проверка авторизации — на уровне HTTP."""
    def __init__(self, reviews: ReviewRepository):
        self.reviews = reviews

    async def execute(self, review: Review) -> Review:
        return await self.reviews.add(review)


class ListBookReviews:
    """Use case: отзывы о книге."""
    def __init__(self, reviews: ReviewRepository):
        self.reviews = reviews

    async def execute(self, book_id: int) -> list[Review]:
        return await self.reviews.list_by_book(book_id)


class DeleteReview:
    """
    Use case: удалить отзыв. Доменное правило:
    разрешено автору отзыва или администратору.
    """
    def __init__(self, reviews: ReviewRepository):
        self.reviews = reviews

    async def execute(self, review_id: int, requester_id: int, is_admin: bool) -> bool:
        review = await self.reviews.get_by_id(review_id)
        if review is None:
            raise ValueError("not_found")
        if not is_admin and review.customer_id != requester_id:
            raise ValueError("forbidden")
        return await self.reviews.delete(review_id)
