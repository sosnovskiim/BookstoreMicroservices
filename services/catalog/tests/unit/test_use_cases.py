import pytest
from datetime import date
from src.domain.book import Book
from src.domain.review import Review
from src.application.use_cases import (
    ListBooks, GetBook, CreateBook, DeleteBook,
    CreateReview, ListBookReviews, DeleteReview,
)


# --- in-memory фейки (без БД и без FastAPI) ---

class FakeBookRepo:
    def __init__(self): self._data: dict[int, Book] = {}
    async def list_all(self): return list(self._data.values())
    async def get_by_id(self, book_id): return self._data.get(book_id)
    async def get_by_ids(self, ids): return [self._data[i] for i in ids if i in self._data]
    async def add(self, book):
        book.id = len(self._data) + 1
        self._data[book.id] = book
        return book
    async def delete(self, book_id):
        return self._data.pop(book_id, None) is not None


class FakeReviewRepo:
    def __init__(self): self._data: dict[int, Review] = {}
    async def list_by_book(self, book_id):
        return [r for r in self._data.values() if r.book_id == book_id]
    async def get_by_id(self, review_id): return self._data.get(review_id)
    async def add(self, review):
        review.id = len(self._data) + 1
        self._data[review.id] = review
        return review
    async def delete(self, review_id):
        return self._data.pop(review_id, None) is not None


def _make_book(name: str = "Test") -> Book:
    return Book(id=None, name=name, description="d", category_id=1, publisher_id=1,
                isbn="123", age_limit="0+", publication_date="2025",
                pages_number=100, weight=100, price=500)


def _make_review(customer_id: int = 1) -> Review:
    return Review(id=None, book_id=1, customer_id=customer_id,
                  date=date(2025, 1, 1), rating=5, text="ok")


# --- Book use cases ---

async def test_create_and_list_books():
    repo = FakeBookRepo()
    created = await CreateBook(repo).execute(_make_book("A"))
    assert created.id == 1
    books = await ListBooks(repo).execute()
    assert len(books) == 1 and books[0].name == "A"


async def test_get_book_ok_and_missing():
    repo = FakeBookRepo()
    await CreateBook(repo).execute(_make_book())
    assert (await GetBook(repo).execute(1)).name == "Test"
    assert await GetBook(repo).execute(999) is None


async def test_delete_book():
    repo = FakeBookRepo()
    await CreateBook(repo).execute(_make_book())
    assert await DeleteBook(repo).execute(1) is True
    assert await DeleteBook(repo).execute(1) is False


# --- Review use cases ---

async def test_create_and_list_reviews():
    repo = FakeReviewRepo()
    await CreateReview(repo).execute(_make_review(customer_id=1))
    await CreateReview(repo).execute(_make_review(customer_id=2))
    reviews = await ListBookReviews(repo).execute(book_id=1)
    assert len(reviews) == 2


async def test_delete_review_by_author():
    """Автор может удалить свой отзыв."""
    repo = FakeReviewRepo()
    created = await CreateReview(repo).execute(_make_review(customer_id=1))
    assert await DeleteReview(repo).execute(
        created.id, requester_id=1, is_admin=False,
    ) is True


async def test_delete_review_by_admin():
    """Админ может удалить чужой отзыв."""
    repo = FakeReviewRepo()
    created = await CreateReview(repo).execute(_make_review(customer_id=1))
    assert await DeleteReview(repo).execute(
        created.id, requester_id=99, is_admin=True,
    ) is True


async def test_delete_review_forbidden():
    """Чужой отзыв без прав администратора удалить нельзя."""
    repo = FakeReviewRepo()
    created = await CreateReview(repo).execute(_make_review(customer_id=1))
    with pytest.raises(ValueError, match="forbidden"):
        await DeleteReview(repo).execute(created.id, requester_id=2, is_admin=False)


async def test_delete_review_not_found():
    repo = FakeReviewRepo()
    with pytest.raises(ValueError, match="not_found"):
        await DeleteReview(repo).execute(999, requester_id=1, is_admin=False)
