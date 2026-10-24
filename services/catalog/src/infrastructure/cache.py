import json
from redis.asyncio import Redis
from ..config import settings


# Один клиент на процесс: redis.asyncio безопасен для параллельных вызовов.
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class BookCache:
    """
    Кеш каталога в Redis (требование 5).
    TTL 60 сек — простой демонстрационный вариант.
    На мутациях явно инвалидируем затронутые ключи.
    """
    LIST_KEY = "catalog:books:list"
    ONE_KEY = "catalog:book:{}"
    TTL = 60

    async def get_list(self) -> list[dict] | None:
        raw = await redis_client.get(self.LIST_KEY)
        return json.loads(raw) if raw else None

    async def set_list(self, data: list[dict]) -> None:
        await redis_client.set(self.LIST_KEY, json.dumps(data), ex=self.TTL)

    async def get_one(self, book_id: int) -> dict | None:
        raw = await redis_client.get(self.ONE_KEY.format(book_id))
        return json.loads(raw) if raw else None

    async def set_one(self, book_id: int, data: dict) -> None:
        await redis_client.set(self.ONE_KEY.format(book_id), json.dumps(data), ex=self.TTL)

    async def invalidate_list(self) -> None:
        await redis_client.delete(self.LIST_KEY)

    async def invalidate_one(self, book_id: int) -> None:
        await redis_client.delete(self.ONE_KEY.format(book_id))
