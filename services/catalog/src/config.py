import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки сервиса. Значения берутся из env (в т.ч. .env)."""
    database_url: str = "postgresql+asyncpg://bookstore:bookstore@postgres:5432/bookstore"
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    grpc_port: int = 50051

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
