from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки сервиса. Значения берутся из env (в т.ч. .env через docker-compose)."""
    database_url: str
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"  # прочие переменные окружения не ломают запуск

settings = Settings()
