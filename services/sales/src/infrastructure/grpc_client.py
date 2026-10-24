import grpc

from ..grpc_gen import catalog_pb2, catalog_pb2_grpc


class CatalogGrpcClient:
    """
    Синхронный клиент Catalog через gRPC (требование 10).
    grpc.aio — неблокирующий канал, совместим с asyncio FastAPI.
    """

    def __init__(self, host: str, port: int):
        self.address = f"{host}:{port}"
        self.channel = None
        self.stub = None

    async def connect(self) -> None:
        # wait_for_ready=True с таймаутом — даём Catalog'у время подняться.
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub = catalog_pb2_grpc.CatalogServiceStub(self.channel)
        await self.channel.channel_ready()

    async def close(self) -> None:
        if self.channel is not None:
            await self.channel.close()

    async def get_prices(self, book_ids: list[int]) -> dict[int, int]:
        """
        Возвращает {book_id: price} для книг, которые существуют.
        Если Catalog недоступен — бросает RuntimeError, HTTP-слой вернёт 503.
        """
        if not book_ids:
            return {}
        try:
            response = await self.stub.GetBooksByIds(
                catalog_pb2.BooksByIdsRequest(ids=book_ids), timeout=3.0,
            )
        except grpc.aio.AioRpcError as e:
            raise RuntimeError(f"catalog_unavailable:{e.code()}") from e

        # exists=False означает, что книги нет — такие id не попадут в результат.
        return {b.id: b.price for b in response.books if b.exists}
