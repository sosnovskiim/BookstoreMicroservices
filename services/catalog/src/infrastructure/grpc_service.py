from .db import SessionLocal, SqlBookRepository
from ..grpc_gen import catalog_pb2, catalog_pb2_grpc


class CatalogServicer(catalog_pb2_grpc.CatalogServiceServicer):
    """
    gRPC-сервер: быстрый lookup книг для Sales (требование 10).
    Работает в том же asyncio-цикле, что и FastAPI (grpc.aio).
    """

    async def GetBooksByIds(self, request, context):
        ids = list(request.ids)
        async with SessionLocal() as session:
            books = await SqlBookRepository(session).get_by_ids(ids)

        response = catalog_pb2.BooksByIdsResponse()
        found_ids = set()
        for book in books:
            response.books.add(
                id=book.id, name=book.name, price=book.price, exists=True
            )
            found_ids.add(book.id)
        # Книги, которых нет в каталоге, возвращаем с exists=False —
        # чтобы клиент явно видел, какой ID не найден.
        for book_id in ids:
            if book_id not in found_ids:
                response.books.add(id=book_id, name="", price=0, exists=False)
        return response
