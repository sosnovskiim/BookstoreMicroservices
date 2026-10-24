"""
E2E-тест распределённой транзакции (требование 7).
Требует поднятого через docker compose стека:
    docker compose up -d --build
    RUN_E2E=1 pytest tests/e2e -v
Тестирует оба исхода саги — CONFIRMED и CANCELLED.
"""
import os
import time

import httpx
import pytest


BASE_IDENTITY = "http://localhost:8001"
BASE_SALES = "http://localhost:8003"


@pytest.fixture(scope="module")
def token() -> str:
    """Логин seed-клиента (id=1, есть в sales.customers)."""
    r = httpx.post(f"{BASE_IDENTITY}/auth/login", json={
        "email": "olga.sosnovskaya@mail.ru",
        "password": "password123",
    }, timeout=10.0)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _wait_status(order_id: int, headers: dict, expected: set[str],
                 timeout: float = 20.0) -> str:
    """
    Опрашивает GET /orders/{id}, пока status не станет одним из expected.
    Пуллинг нужен, потому что сага асинхронная (RabbitMQ + outbox publisher).
    """
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = httpx.get(f"{BASE_SALES}/orders/{order_id}", headers=headers, timeout=5.0)
        if r.status_code == 200:
            last = r.json()["status"]
            if last in expected:
                return last
        time.sleep(0.5)
    raise AssertionError(f"order {order_id} status={last}, expected {expected}")


@pytest.mark.skipif(not os.getenv("RUN_E2E"),
                    reason="requires docker compose stack; set RUN_E2E=1")
def test_saga_confirmed(token):
    """Успешный сценарий: достаточно остатков — заказ CONFIRMED."""
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{BASE_SALES}/orders", headers=headers, json={
        "payment_method_id": 2,
        "delivery_id": None,
        "items": [{"book_id": 1, "quantity": 1}],
    }, timeout=15.0)
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "PENDING"
    final = _wait_status(order["id"], headers, {"CONFIRMED", "CANCELLED"})
    assert final == "CONFIRMED", f"expected CONFIRMED, got {final}"


@pytest.mark.skipif(not os.getenv("RUN_E2E"),
                    reason="requires docker compose stack; set RUN_E2E=1")
def test_saga_cancelled(token):
    """Негативный сценарий: недостаточно остатков — заказ CANCELLED."""
    headers = {"Authorization": f"Bearer {token}"}
    # 100 единиц почти наверняка больше, чем в наличии у любой книги.
    r = httpx.post(f"{BASE_SALES}/orders", headers=headers, json={
        "payment_method_id": 2,
        "items": [{"book_id": 8, "quantity": 100}],
    }, timeout=15.0)
    assert r.status_code == 201, r.text
    order = r.json()
    final = _wait_status(order["id"], headers, {"CONFIRMED", "CANCELLED"})
    assert final == "CANCELLED", f"expected CANCELLED, got {final}"
