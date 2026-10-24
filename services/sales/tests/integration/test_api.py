import os
import pytest
from httpx import AsyncClient, ASGITransport

# Требуют живые Postgres + RabbitMQ + Catalog.
# Запуск: $env:RUN_INTEGRATION="1"; pytest tests/integration -v


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires infra; set RUN_INTEGRATION=1")
async def test_health():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert r.status_code == 200
