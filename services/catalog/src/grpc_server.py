import grpc
from .config import settings
from .grpc_gen import catalog_pb2_grpc
from .infrastructure.grpc_service import CatalogServicer


async def create_grpc_server():
    """Создаёт asyncio gRPC-сервер (grpc.aio). Запускается из lifespan FastAPI."""
    server = grpc.aio.server()
    catalog_pb2_grpc.add_CatalogServiceServicer_to_server(CatalogServicer(), server)
    server.add_insecure_port(f"[::]:{settings.grpc_port}")
    return server
