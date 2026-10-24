from ..domain.user import User
from .ports import UserRepository, PasswordHasher, TokenIssuer


class RegisterUser:
    """Use case: регистрация пользователя. Хеширует пароль и сохраняет запись."""
    def __init__(self, users: UserRepository, hasher: PasswordHasher):
        self.users = users
        self.hasher = hasher

    async def execute(self, email: str, password: str, role: str = "customer") -> User:
        # Проверяем уникальность email до вставки — понятная доменная ошибка вместо SQL-исключения.
        if await self.users.get_by_email(email) is not None:
            raise ValueError("user_exists")
        user = User(id=None, email=email,
                    password_hash=self.hasher.hash(password), role=role)
        return await self.users.add(user)


class AuthenticateUser:
    """Use case: проверка пароля и выдача JWT при успехе."""
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenIssuer):
        self.users = users
        self.hasher = hasher
        self.tokens = tokens

    async def execute(self, email: str, password: str) -> str:
        user = await self.users.get_by_email(email)
        # Одинаковая ошибка на «нет пользователя» и «неверный пароль» — не палим существование email.
        if user is None or not self.hasher.verify(password, user.password_hash):
            raise ValueError("invalid_credentials")
        return self.tokens.issue(user.id, user.role)
