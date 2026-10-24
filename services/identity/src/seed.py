from .domain.user import User
from .infrastructure.db import SqlUserRepository
from .infrastructure.security import BcryptHasher

# Emails совпадают с sales.customers из исходных данных:
# так ID пользователей Identity и customers в Sales будут одинаковыми.
_SEED = [
    "olga.sosnovskaya@mail.ru", "evgeniya.moiseenko@gmail.com",
    "mariya.chadaeva@gmail.com", "polina.tokareva@mail.ru",
    "patimat.magomedova@mail.ru", "daniil.stepanov@gmail.com",
    "demid.filatov@gmail.com", "elizaveta.sorokina@yandex.ru",
    "polina.tikhonova@mail.ru", "miron.gusev@gmail.com",
    "ekaterina.prokofeva@yandex.ru", "mikhail.vasilev@mail.ru",
    "andrei.fomichev@mail.ru", "ivan.antonov@yandex.ru",
]


async def seed_users(session, hasher: BcryptHasher) -> None:
    """
    Идемпотентный сид: 14 обычных пользователей + 1 админ.
    Пароли: password123 (customer) / admin123 (admin) — только для учебной демонстрации.
    """
    repo = SqlUserRepository(session)
    # Если в таблице уже есть записи — сид не запускаем (повторные рестарты безопасны).
    if await repo.count() > 0:
        return
    for email in _SEED:
        await repo.add(User(id=None, email=email,
                            password_hash=hasher.hash("password123"),
                            role="customer"))
    await repo.add(User(id=None, email="admin@bookstore.com",
                        password_hash=hasher.hash("admin123"),
                        role="admin"))
