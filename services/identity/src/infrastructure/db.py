from datetime import datetime
from sqlalchemy import String, Integer, DateTime, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ..config import settings
from ..domain.user import User as UserEntity


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей этого сервиса."""
    pass


class UserModel(Base):
    """ORM-модель таблицы identity.users."""
    __tablename__ = "users"
    __table_args__ = {"schema": "identity"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="customer")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# search_path=identity — все голые имена таблиц резолвятся в эту схему.
# Так SQLAlchemy не требует явно указывать схему в каждом запросе.
engine = create_async_engine(
    settings.database_url,
    connect_args={"server_settings": {"search_path": "identity"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class SqlUserRepository:
    """Реализация порта UserRepository поверх SQLAlchemy."""
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, row: UserModel) -> UserEntity:
        """Преобразование ORM-модели в доменную сущность (изоляция слоёв)."""
        return UserEntity(id=row.id, email=row.email,
                          password_hash=row.password_hash, role=row.role)

    async def get_by_email(self, email: str) -> UserEntity | None:
        row = (await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_id(self, user_id: int) -> UserEntity | None:
        row = await self.session.get(UserModel, user_id)
        return self._to_entity(row) if row else None

    async def add(self, user: UserEntity) -> UserEntity:
        # commit + refresh — чтобы получить актуальный id после вставки.
        row = UserModel(email=user.email, password_hash=user.password_hash, role=user.role)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_entity(row)

    async def count(self) -> int:
        """Используется сидом, чтобы не пересоздавать пользователей при рестарте."""
        return (await self.session.execute(
            select(func.count()).select_from(UserModel)
        )).scalar_one()
