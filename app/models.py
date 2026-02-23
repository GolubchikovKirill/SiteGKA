import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)


class Printer(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    printer_type: str = Field(default="laser", max_length=20, index=True)
    store_name: str = Field(max_length=255, index=True)
    model: str = Field(max_length=255)
    ip_address: str = Field(max_length=45, unique=True, index=True)
    mac_address: str | None = Field(default=None, max_length=17)
    mac_status: str | None = Field(default=None, max_length=20)
    snmp_community: str = Field(default="public", max_length=255)

    is_online: bool | None = Field(default=None)
    status: str | None = Field(default=None, max_length=50)
    toner_black: int | None = Field(default=None)
    toner_cyan: int | None = Field(default=None)
    toner_magenta: int | None = Field(default=None)
    toner_yellow: int | None = Field(default=None)
    last_polled_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)
