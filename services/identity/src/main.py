from contextlib import asynccontextmanager
from fastapi import FastAPI
from .presentation.http import router
from .infrastructure.db import SessionLocal
from .infrastructure.security import BcryptHasher
from .seed import seed_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Событие старта приложения: идемпотентный сид пользователей."""
    async with SessionLocal() as session:
        await seed_users(session, BcryptHasher())
    yield


# FastAPI-приложение; все HTTP-эндпоинты подключаются через роутер.
app = FastAPI(title="Identity Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["health"])
async def health():
    """Простой health-check для docker healthcheck и локальной проверки."""
    return {"status": "ok"}
