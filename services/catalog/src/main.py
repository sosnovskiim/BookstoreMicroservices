from contextlib import asynccontextmanager
from fastapi import FastAPI

from .presentation.http import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Поднимаем gRPC-сервер вместе с HTTP в одном процессе (grpc.aio).
    Импорт ленивый: если стабы не сгенерированы (например, локальные unit-тесты),
    сервис продолжает работать в HTTP-only режиме.
    """
    grpc_server = None
    try:
        from .grpc_server import create_grpc_server
        grpc_server = await create_grpc_server()
        await grpc_server.start()
    except ImportError:
        pass

    yield

    if grpc_server is not None:
        await grpc_server.stop(grace=5)  # корректно гасим gRPC при остановке


# FastAPI-приложение; HTTP-роуты подключаются через роутер.
app = FastAPI(title="Catalog Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["health"])
async def health():
    """Health-check для docker healthcheck и локальной проверки."""
    return {"status": "ok"}
