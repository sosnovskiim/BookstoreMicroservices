import os
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


# Интеграционные тесты запускаются только с RUN_INTEGRATION=1,
# потому что требуют живую БД (docker compose up -d postgres).
# Локально: $env:RUN_INTEGRATION="1"; pytest tests/integration -v


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires postgres; set RUN_INTEGRATION=1")
async def test_health():
    """Сервис отвечает на health-check."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert r.status_code == 200


@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"),
                    reason="requires postgres; set RUN_INTEGRATION=1")
async def test_admin_seed_login():
    """Сид-админ существует и успешно логинится, получая непустой JWT."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/auth/login", json={
            "email": "admin@bookstore.com",
            "password": "admin123",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"
