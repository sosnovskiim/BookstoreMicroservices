import pytest
from src.domain.user import User
from src.application.use_cases import RegisterUser, AuthenticateUser


# --- in-memory фейки портов (без БД, без FastAPI) ---

class FakeRepo:
    """Хранит пользователей в словаре. Хватает для проверки use case'ов."""
    def __init__(self): self._users: dict[str, User] = {}
    async def get_by_email(self, email): return self._users.get(email)
    async def get_by_id(self, uid):
        return next((u for u in self._users.values() if u.id == uid), None)
    async def add(self, user):
        user.id = len(self._users) + 1
        self._users[user.email] = user
        return user
    async def count(self): return len(self._users)


class FakeHasher:
    """Псевдо-хеш: 'h:<пароль>'. Достаточно, чтобы проверить hash/verify контракт."""
    def hash(self, pw): return f"h:{pw}"
    def verify(self, pw, h): return h == f"h:{pw}"


class FakeIssuer:
    """Псевдо-JWT: 'token:<id>:<role>'. Проверяем, что use case передал верные аргументы."""
    def issue(self, uid, role): return f"token:{uid}:{role}"


async def test_register_and_login_ok():
    """Регистрация, затем успешный вход с тем же паролем."""
    repo = FakeRepo()
    user = await RegisterUser(repo, FakeHasher()).execute("a@b.c", "secret")
    assert user.id == 1 and user.role == "customer"

    token = await AuthenticateUser(repo, FakeHasher(), FakeIssuer()).execute("a@b.c", "secret")
    assert token == "token:1:customer"


async def test_register_duplicate_raises():
    """Повторная регистрация того же email должна падать."""
    repo = FakeRepo()
    reg = RegisterUser(repo, FakeHasher())
    await reg.execute("a@b.c", "secret")
    with pytest.raises(ValueError, match="user_exists"):
        await reg.execute("a@b.c", "secret")


async def test_login_wrong_password():
    """Неверный пароль — invalid_credentials."""
    repo = FakeRepo()
    await RegisterUser(repo, FakeHasher()).execute("a@b.c", "secret")
    with pytest.raises(ValueError, match="invalid_credentials"):
        await AuthenticateUser(repo, FakeHasher(), FakeIssuer()).execute("a@b.c", "wrong")
