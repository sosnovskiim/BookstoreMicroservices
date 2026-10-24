from datetime import date as today
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_current_user, require_admin, CurrentUser
from .schemas import (
    BookResponse, CreateBookRequest,
    ReviewResponse, CreateReviewRequest,
)
from ..domain.book import Book
from ..domain.review import Review
from ..infrastructure.db import (
    SessionLocal, SqlBookRepository, SqlReviewRepository,
)
from ..infrastructure.cache import BookCache
from ..application.use_cases import (
    ListBooks, GetBook, CreateBook, DeleteBook,
    CreateReview, ListBookReviews, DeleteReview,
)

router = APIRouter()


async def get_session():
    """FastAPI-зависимость: сессия SQLAlchemy на время запроса."""
    async with SessionLocal() as session:
        yield session


# --- Книги ---

@router.get("/books", response_model=list[BookResponse], tags=["books"])
async def list_books(session: AsyncSession = Depends(get_session)):
    """Список книг с кешем в Redis (требование 5)."""
    cache = BookCache()
    cached = await cache.get_list()
    if cached is not None:
        return cached

    books = await ListBooks(SqlBookRepository(session)).execute()
    payload = [BookResponse.model_validate(b).model_dump(mode="json") for b in books]
    await cache.set_list(payload)
    return payload


@router.get("/books/{book_id}", response_model=BookResponse, tags=["books"])
async def get_book(book_id: int, session: AsyncSession = Depends(get_session)):
    """Книга по id. Тоже кешируется."""
    cache = BookCache()
    cached = await cache.get_one(book_id)
    if cached is not None:
        return cached

    book = await GetBook(SqlBookRepository(session)).execute(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    payload = BookResponse.model_validate(book).model_dump(mode="json")
    await cache.set_one(book_id, payload)
    return payload


@router.post("/books", response_model=BookResponse, status_code=status.HTTP_201_CREATED,
             tags=["books"])
async def create_book(body: CreateBookRequest,
                      _: CurrentUser = Depends(require_admin),  # только админ
                      session: AsyncSession = Depends(get_session)):
    """Создание книги (admin). Инвалидирует кеш списка."""
    domain = Book(id=None, **body.model_dump())
    try:
        created = await CreateBook(SqlBookRepository(session)).execute(domain)
    except Exception as e:
        # Наиболее вероятная причина — конфликт по ISBN (unique).
        raise HTTPException(status_code=400, detail=f"cannot create book: {e}")
    await BookCache().invalidate_list()
    return BookResponse.model_validate(created)


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["books"])
async def delete_book(book_id: int,
                      _: CurrentUser = Depends(require_admin),   # только админ
                      session: AsyncSession = Depends(get_session)):
    """Удаление книги (admin). Инвалидирует оба кеш-ключа."""
    ok = await DeleteBook(SqlBookRepository(session)).execute(book_id)
    if not ok:
        raise HTTPException(status_code=404, detail="book not found")
    cache = BookCache()
    await cache.invalidate_list()
    await cache.invalidate_one(book_id)


# --- Отзывы ---

@router.get("/books/{book_id}/reviews", response_model=list[ReviewResponse], tags=["reviews"])
async def list_reviews(book_id: int, session: AsyncSession = Depends(get_session)):
    """Публичный список отзывов о книге."""
    reviews = await ListBookReviews(SqlReviewRepository(session)).execute(book_id)
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.post("/books/{book_id}/reviews", response_model=ReviewResponse,
             status_code=status.HTTP_201_CREATED, tags=["reviews"])
async def create_review(book_id: int, body: CreateReviewRequest,
                        user: CurrentUser = Depends(get_current_user),  # любой авторизованный
                        session: AsyncSession = Depends(get_session)):
    """Оставить отзыв. Автор берётся из JWT (не из тела запроса)."""
    review = Review(
        id=None, book_id=book_id, customer_id=user.user_id,
        date=today.today(), rating=body.rating, text=body.text,
    )
    created = await CreateReview(SqlReviewRepository(session)).execute(review)
    return ReviewResponse.model_validate(created)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["reviews"])
async def delete_review(review_id: int,
                        user: CurrentUser = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    """Удалить отзыв: только автор или админ (правило в use case)."""
    try:
        await DeleteReview(SqlReviewRepository(session)).execute(
            review_id, requester_id=user.user_id, is_admin=(user.role == "admin"),
        )
    except ValueError as e:
        code = 404 if str(e) == "not_found" else 403
        raise HTTPException(status_code=code, detail=str(e))


# --- Справочники (read-only) ---
# Полезны админу для получения category_id/publisher_id при создании книги.

@router.get("/categories", tags=["reference"])
async def list_categories(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(text("SELECT id, name FROM catalog.categories ORDER BY id"))).all()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.get("/publishers", tags=["reference"])
async def list_publishers(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(text("SELECT id, name FROM catalog.publishers ORDER BY id"))).all()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.get("/genres", tags=["reference"])
async def list_genres(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(text("SELECT id, name FROM catalog.genres ORDER BY id"))).all()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.get("/authors", tags=["reference"])
async def list_authors(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        text("SELECT id, first_name, last_name FROM catalog.authors ORDER BY id")
    )).all()
    return [{"id": r[0], "first_name": r[1], "last_name": r[2]} for r in rows]
