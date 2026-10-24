import os
import pytest
from httpx import AsyncClient, ASGITransport

# Интеграционные тесты требуют живую БД (docker compose up -d postgres).
# Запуск: $env:DATABASE_URL="postgresql+asyncpg://bookstore:bookstore@localhost:5432/bookstore"
#         $env:RUN_INTEGRATION="1"; pytest tests/integration -v


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires postgres; set RUN_INTEGRATION=1")
async def test_health():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert r.status_code == 200


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires postgres; set RUN_INTEGRATION=1")
async def test_list_books_returns_seed():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/books")
        assert r.status_code == 200
        books = r.json()
        assert len(books) == 10
