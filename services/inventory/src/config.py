import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки сервиса. Значения берутся из env (в т.ч. .env)."""
    database_url: str = "postgresql+asyncpg://bookstore:bookstore@postgres:5432/bookstore"
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    rabbitmq_exchange: str = os.getenv("RABBITMQ_EXCHANGE", "bookstore.events")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
