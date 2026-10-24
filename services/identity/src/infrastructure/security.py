from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from ..config import settings

# bcrypt — стандарт де-факто для паролей; passlib берёт на себя соль и формат.
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptHasher:
    """Реализация порта PasswordHasher."""
    def hash(self, password: str) -> str:
        return _pwd.hash(password)

    def verify(self, password: str, hash: str) -> bool:
        try:
            return _pwd.verify(password, hash)
        except ValueError:
            # Невалидный хеш в БД — возвращаем False, а не роняем запрос.
            return False


class JwtIssuer:
    """Реализация порта TokenIssuer: выпускает HS256 JWT со сроком жизни."""
    def issue(self, user_id: int, role: str) -> str:
        payload = {
            "sub": str(user_id),  # subject — id пользователя
            "role": role,  # роль для require_admin
            "exp": datetime.now(tz=timezone.utc)
                   + timedelta(minutes=settings.jwt_expires_minutes),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
