from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import require_admin, CurrentUser
from .schemas import (
    StockResponse, TopUpRequest,
    CreatePurchaseRequest,
)
from ..domain.purchase import PurchaseItem
from ..infrastructure.db import (
    SessionLocal, SqlStockRepository, SqlPurchaseRepository,
)
from ..application.use_cases import (
    ListStock, GetStock, TopUpStock, CreatePurchase,
)

router = APIRouter()


async def get_session():
    """FastAPI-зависимость: сессия SQLAlchemy на время запроса."""
    async with SessionLocal() as session:
        yield session


def _to_response(s) -> StockResponse:
    """Маппинг домена в HTTP-схему: available вычисляется из quantity-reserved."""
    return StockResponse(
        book_id=s.book_id, quantity=s.quantity,
        reserved=s.reserved, available=s.available,
    )


@router.get("/stock", response_model=list[StockResponse], tags=["stock"])
async def list_stock(session: AsyncSession = Depends(get_session)):
    """Список остатков по всем книгам (публичный)."""
    items = await ListStock(SqlStockRepository(session)).execute()
    return [_to_response(s) for s in items]


@router.get("/stock/{book_id}", response_model=StockResponse, tags=["stock"])
async def get_stock(book_id: int, session: AsyncSession = Depends(get_session)):
    """Остаток конкретной книги."""
    item = await GetStock(SqlStockRepository(session)).execute(book_id)
    if item is None:
        raise HTTPException(status_code=404, detail="stock not found")
    return _to_response(item)


@router.post("/stock/{book_id}/top-up", response_model=StockResponse, tags=["stock"])
async def top_up(book_id: int, body: TopUpRequest,
                 _: CurrentUser = Depends(require_admin),  # только админ
                 session: AsyncSession = Depends(get_session)):
    """Пополнение остатков книги (admin). Нужно для тестов саги."""
    try:
        item = await TopUpStock(SqlStockRepository(session)).execute(book_id, body.amount)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_response(item)


@router.post("/purchases", status_code=status.HTTP_201_CREATED, tags=["purchases"])
async def create_purchase(body: CreatePurchaseRequest,
                          _: CurrentUser = Depends(require_admin),  # только админ
                          session: AsyncSession = Depends(get_session)):
    """Оформить закупку у поставщика (admin). Увеличивает остатки."""
    items = [PurchaseItem(book_id=i.book_id, quantity=i.quantity) for i in body.items]
    try:
        p = await CreatePurchase(
            SqlPurchaseRepository(session), SqlStockRepository(session),
        ).execute(body.supplier_id, body.total_cost, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": p.id, "supplier_id": p.supplier_id, "total_cost": p.total_cost}


@router.get("/suppliers", tags=["reference"])
async def list_suppliers(session: AsyncSession = Depends(get_session)):
    """Справочник поставщиков."""
    rows = (await session.execute(
        text("SELECT id, name FROM inventory.suppliers ORDER BY id")
    )).all()
    return [{"id": r[0], "name": r[1]} for r in rows]
