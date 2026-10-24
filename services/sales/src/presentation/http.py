from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_current_user, CurrentUser
from .schemas import CreateOrderRequest, OrderResponse, OrderItemResponse
from ..infrastructure.db import (
    SessionLocal, SqlOrderRepository, SqlOutbox,
)
from ..application.use_cases import CreateOrder, GetOrder, ListOrders

router = APIRouter()


async def get_session():
    """FastAPI-зависимость: сессия SQLAlchemy на время запроса."""
    async with SessionLocal() as session:
        yield session


def _to_response(o) -> OrderResponse:
    """Маппинг домена в HTTP-схему."""
    return OrderResponse(
        id=o.id, customer_id=o.customer_id,
        payment_method_id=o.payment_method_id, delivery_id=o.delivery_id,
        total_cost=o.total_cost, status=o.status.value if hasattr(o.status, "value") else o.status,
        time=o.time,
        items=[OrderItemResponse(book_id=i.book_id, quantity=i.quantity) for i in o.items],
    )


@router.post("/orders", response_model=OrderResponse,
             status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_order(body: CreateOrderRequest, request: Request,
                       user: CurrentUser = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    """
    Создать заказ. gRPC-вызов в Catalog (требование 10),
    outbox sales.order.created (требование 8).
    """
    catalog = request.app.state.grpc_client  # проброшен из lifespan
    uc = CreateOrder(
        orders=SqlOrderRepository(session),
        outbox=SqlOutbox(session),
        catalog=catalog,
        commit=session.commit,
    )
    try:
        order = await uc.execute(
            customer_id=user.user_id,
            payment_method_id=body.payment_method_id,
            delivery_id=body.delivery_id,
            items=[it.model_dump() for it in body.items],
        )
    except RuntimeError as e:
        # Catalog недоступен — не наша ошибка, отдаём 503.
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        msg = str(e)
        # Клиент не найден в sales.customers → 400, а не 500 при FK.
        if msg == "customer_not_registered":
            raise HTTPException(
                status_code=400,
                detail="customer is not registered in sales; use a seeded customer",
            )
        if msg.startswith("books_not_found"):
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="order integrity violation")
    return _to_response(order)


@router.get("/orders/{order_id}", response_model=OrderResponse, tags=["orders"])
async def get_order(order_id: int, user: CurrentUser = Depends(get_current_user),
                    session: AsyncSession = Depends(get_session)):
    """Заказ по id. Доступен только владельцу (или админу)."""
    order = await GetOrder(SqlOrderRepository(session)).execute(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if order.customer_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="access denied")
    return _to_response(order)


@router.get("/orders", response_model=list[OrderResponse], tags=["orders"])
async def list_my_orders(user: CurrentUser = Depends(get_current_user),
                         session: AsyncSession = Depends(get_session)):
    """Мои заказы (по customer_id из JWT)."""
    orders = await ListOrders(SqlOrderRepository(session)).execute(user.user_id)
    return [_to_response(o) for o in orders]
