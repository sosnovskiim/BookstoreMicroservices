import asyncio
from contextlib import asynccontextmanager

import aio_pika
from fastapi import FastAPI

from .config import settings
from .presentation.http import router
from .infrastructure.consumer import OrderCreatedConsumer
from .infrastructure.outbox_publisher import OutboxPublisher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    При старте поднимаем два фоновых asyncio-таска:
      - consumer слушает очередь sales.order.created (требование 9);
      - outbox publisher читает inventory.outbox и публикует в RabbitMQ (требование 8).
    При остановке — отменяем таски и закрываем соединение.
    """
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    consumer = OrderCreatedConsumer(connection)
    publisher = OutboxPublisher(connection)

    tasks = [
        asyncio.create_task(consumer.start(), name="order-created-consumer"),
        asyncio.create_task(publisher.start(), name="outbox-publisher"),
    ]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await connection.close()


# FastAPI-приложение Inventory.
app = FastAPI(title="Inventory Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["health"])
async def health():
    """Health-check для docker healthcheck."""
    return {"status": "ok"}
