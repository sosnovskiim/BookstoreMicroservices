import datetime
from sqlalchemy import String, Integer, Text, Date, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from ..domain.book import Book as BookEntity
from ..domain.review import Review as ReviewEntity


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей этого сервиса."""
    pass


class BookModel(Base):
    """ORM-модель таблицы catalog.books."""
    __tablename__ = "books"
    __table_args__ = {"schema": "catalog"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(Integer)
    publisher_id: Mapped[int] = mapped_column(Integer)
    isbn: Mapped[str] = mapped_column(String(32), unique=True)
    age_limit: Mapped[str] = mapped_column(String(4))
    publication_date: Mapped[str] = mapped_column(String(4))
    pages_number: Mapped[int] = mapped_column(Integer)
    weight: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)


class ReviewModel(Base):
    """ORM-модель таблицы catalog.reviews (отдельный агрегат, та же схема)."""
    __tablename__ = "reviews"
    __table_args__ = {"schema": "catalog"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer)
    customer_id: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime.date] = mapped_column(Date)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)


# search_path=catalog — голые имена таблиц резолвятся в нужную схему.
engine = create_async_engine(
    settings.database_url,
    connect_args={"server_settings": {"search_path": "catalog"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _to_book(row: BookModel) -> BookEntity:
    """Маппинг ORM → домен."""
    return BookEntity(
        id=row.id, name=row.name, description=row.description,
        category_id=row.category_id, publisher_id=row.publisher_id,
        isbn=row.isbn, age_limit=row.age_limit,
        publication_date=row.publication_date,
        pages_number=row.pages_number, weight=row.weight, price=row.price,
    )


def _to_review(row: ReviewModel) -> ReviewEntity:
    return ReviewEntity(
        id=row.id, book_id=row.book_id, customer_id=row.customer_id,
        date=row.date, rating=row.rating, text=row.text,
    )


class SqlBookRepository:
    """Реализация BookRepository на SQLAlchemy."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[BookEntity]:
        rows = (await self.session.execute(select(BookModel).order_by(BookModel.id))).scalars().all()
        return [_to_book(r) for r in rows]

    async def get_by_id(self, book_id: int) -> BookEntity | None:
        row = await self.session.get(BookModel, book_id)
        return _to_book(row) if row else None

    async def get_by_ids(self, ids: list[int]) -> list[BookEntity]:
        """Используется gRPC-сервером для быстрого lookup'а пачки книг."""
        if not ids:
            return []
        rows = (await self.session.execute(
            select(BookModel).where(BookModel.id.in_(ids))
        )).scalars().all()
        return [_to_book(r) for r in rows]

    async def add(self, book: BookEntity) -> BookEntity:
        row = BookModel(**{k: getattr(book, k) for k in (
            "name", "description", "category_id", "publisher_id", "isbn",
            "age_limit", "publication_date", "pages_number", "weight", "price",
        )})
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return _to_book(row)

    async def delete(self, book_id: int) -> bool:
        row = await self.session.get(BookModel, book_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.commit()
        return True


class SqlReviewRepository:
    """Реализация ReviewRepository на SQLAlchemy."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_book(self, book_id: int) -> list[ReviewEntity]:
        rows = (await self.session.execute(
            select(ReviewModel).where(ReviewModel.book_id == book_id).order_by(ReviewModel.id)
        )).scalars().all()
        return [_to_review(r) for r in rows]

    async def get_by_id(self, review_id: int) -> ReviewEntity | None:
        row = await self.session.get(ReviewModel, review_id)
        return _to_review(row) if row else None

    async def add(self, review: ReviewEntity) -> ReviewEntity:
        row = ReviewModel(
            book_id=review.book_id, customer_id=review.customer_id,
            date=review.date, rating=review.rating, text=review.text,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return _to_review(row)

    async def delete(self, review_id: int) -> bool:
        row = await self.session.get(ReviewModel, review_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.commit()
        return True
