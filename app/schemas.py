import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


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


# ── Printer schemas ──────────────────────────────────────────────


_IP_PATTERN = r"^(\d{1,3}\.){3}\d{1,3}$"


def _validate_ip(v: str) -> str:
    import re
    if not re.match(_IP_PATTERN, v):
        raise ValueError("Invalid IP address format")
    parts = v.split(".")
    if any(int(p) > 255 for p in parts):
        raise ValueError("IP address octets must be 0-255")
    return v


class PrinterCreate(BaseModel):
    store_name: str
    model: str
    ip_address: str
    snmp_community: str = "public"

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip(v)


class PrinterUpdate(BaseModel):
    store_name: str | None = None
    model: str | None = None
    ip_address: str | None = None
    snmp_community: str | None = None

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip(v)
        return v


class PrinterPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_name: str
    model: str
    ip_address: str
    is_online: bool | None = None
    status: str | None = None
    toner_black: int | None = None
    toner_cyan: int | None = None
    toner_magenta: int | None = None
    toner_yellow: int | None = None
    last_polled_at: datetime | None = None
    created_at: datetime


class PrintersPublic(BaseModel):
    data: list[PrinterPublic]
    count: int


class PrinterStatusResponse(BaseModel):
    is_online: bool
    status: str
    toner_black: int | None = None
    toner_cyan: int | None = None
    toner_magenta: int | None = None
    toner_yellow: int | None = None
    sys_description: str | None = None
