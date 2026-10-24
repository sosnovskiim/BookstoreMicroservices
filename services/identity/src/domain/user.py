from dataclasses import dataclass


@dataclass
class User:
    """
    Доменная сущность пользователя (не ORM-модель).
    Живёт в слое domain — ничего не знает про БД и FastAPI.
    """
    id: int | None
    email: str
    password_hash: str
    role: str  # 'customer' | 'admin'
