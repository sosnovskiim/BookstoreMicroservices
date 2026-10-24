import os
import pytest
from httpx import AsyncClient, ASGITransport

# Интеграционные тесты требуют живой БД.
# Запуск: $env:RUN_INTEGRATION="1"; pytest tests/integration -v


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires postgres; set RUN_INTEGRATION=1")
async def test_health():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert r.status_code == 200


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires postgres; set RUN_INTEGRATION=1")
async def test_list_stock_returns_seed():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/stock")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 10
        assert {"book_id", "quantity", "reserved", "available"} <= rows[0].keys()
