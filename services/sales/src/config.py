import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки Sales. gRPC-адрес Catalog'а — для синхронных вызовов (требование 10)."""
    database_url: str = "postgresql+asyncpg://bookstore:bookstore@postgres:5432/bookstore"
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    rabbitmq_exchange: str = os.getenv("RABBITMQ_EXCHANGE", "bookstore.events")
    catalog_grpc_host: str = os.getenv("CATALOG_GRPC_HOST", "catalog")
    catalog_grpc_port: int = int(os.getenv("CATALOG_GRPC_PORT", "50051"))

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
