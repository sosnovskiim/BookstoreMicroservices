from pydantic import BaseModel, EmailStr


# Pydantic-схемы HTTP-слоя. Отделены от домена — при необходимости можно менять
# формат API, не трогая доменные сущности.

class RegisterRequest(BaseModel):
    email: EmailStr  # валидация формата email на входе (EmailStr отвергает .local и подобные)
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
