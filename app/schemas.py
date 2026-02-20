import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None


class UserUpdateMe(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int


class Message(BaseModel):
    message: str
