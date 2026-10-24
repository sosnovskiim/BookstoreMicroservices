from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import get_current_user, CurrentUser
from .schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from ..infrastructure.db import SessionLocal, SqlUserRepository
from ..infrastructure.security import BcryptHasher, JwtIssuer
from ..application.use_cases import RegisterUser, AuthenticateUser

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_session():
    """FastAPI-зависимость: открывает сессию SQLAlchemy на время запроса."""
    async with SessionLocal() as session:
        yield session


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    # Собираем use case из инфраструктурных реализаций портов.
    uc = RegisterUser(SqlUserRepository(session), BcryptHasher())
    try:
        user = await uc.execute(body.email, body.password)
    except ValueError:
        raise HTTPException(status_code=409, detail="user already exists")
    return UserResponse(id=user.id, email=user.email, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    uc = AuthenticateUser(SqlUserRepository(session), BcryptHasher(), JwtIssuer())
    try:
        token = await uc.execute(body.email, body.password)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser = Depends(get_current_user),
             session: AsyncSession = Depends(get_session)):
    """Проверка токена: возвращает данные текущего пользователя."""
    db_user = await SqlUserRepository(session).get_by_id(user.user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserResponse(id=db_user.id, email=db_user.email, role=db_user.role)
