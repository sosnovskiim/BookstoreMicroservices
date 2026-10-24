import asyncio
from contextlib import asynccontextmanager

import aio_pika
from fastapi import FastAPI

from .config import settings
from .presentation.http import router
from .infrastructure.grpc_client import CatalogGrpcClient
from .infrastructure.outbox_publisher import OutboxPublisher
from .infrastructure.consumer import InventoryResultConsumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    При старте:
      - устанавливаем gRPC-канал в Catalog (требование 10);
      - запускаем outbox-publisher и consumer ответов Inventory (требования 7–9).
    """
    grpc_client = CatalogGrpcClient(settings.catalog_grpc_host, settings.catalog_grpc_port)
    await grpc_client.connect()
    # Прокидываем клиента в HTTP-слой через app.state (просто и без глобальных переменных).
    app.state.grpc_client = grpc_client

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    publisher = OutboxPublisher(connection)
    consumer = InventoryResultConsumer(connection)

    tasks = [
        asyncio.create_task(publisher.start(), name="sales-outbox-publisher"),
        asyncio.create_task(consumer.start(), name="inventory-result-consumer"),
    ]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await grpc_client.close()
        await connection.close()


app = FastAPI(title="Sales Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
