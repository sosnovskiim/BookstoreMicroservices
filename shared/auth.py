"""
Общий модуль валидации JWT для всех сервисов, КРОМЕ identity.
Identity выпускает токен, остальные — только проверяют подпись общим секретом.
Реализует требование 11 (единый микросервис авторизации + JWT).
"""
import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import decode
from jwt.exceptions import InvalidTokenError

# Секрет и алгоритм должны совпадать со значениями, которые использует identity.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# auto_error=False — сами отдаём 401 с понятным сообщением вместо дефолтного 403.
_security = HTTPBearer(auto_error=False)


class CurrentUser:
    """Минимальная модель пользователя из JWT — только то, что нужно для авторизации."""
    def __init__(self, user_id: int, role: str):
        self.user_id = user_id
        self.role = role


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_security),
) -> CurrentUser:
    """FastAPI-зависимость: проверяет JWT и возвращает пользователя."""
    if creds is None:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        # decode сам проверит подпись и exp; исключение ловим ниже.
        payload = decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return CurrentUser(user_id=int(payload["sub"]), role=payload["role"])
    except (InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="invalid token")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Зависимость для админских эндпоинтов: пропускает только role='admin'."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return user
