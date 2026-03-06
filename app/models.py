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
    last_seen_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)


class Printer(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    printer_type: str = Field(default="laser", max_length=20, index=True)
    connection_type: str = Field(default="ip", max_length=10)
    store_name: str = Field(max_length=255, index=True)
    model: str = Field(max_length=255)
    ip_address: str | None = Field(default=None, max_length=45, index=True)
    mac_address: str | None = Field(default=None, max_length=17)
    mac_status: str | None = Field(default=None, max_length=20)
    snmp_community: str = Field(default="public", max_length=255)
    host_pc: str | None = Field(default=None, max_length=255)

    is_online: bool | None = Field(default=None)
    status: str | None = Field(default=None, max_length=50)
    toner_black: int | None = Field(default=None)
    toner_cyan: int | None = Field(default=None)
    toner_magenta: int | None = Field(default=None)
    toner_yellow: int | None = Field(default=None)
    toner_black_name: str | None = Field(default=None, max_length=128)
    toner_cyan_name: str | None = Field(default=None, max_length=128)
    toner_magenta_name: str | None = Field(default=None, max_length=128)
    toner_yellow_name: str | None = Field(default=None, max_length=128)
    last_polled_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)


class NetworkSwitch(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, index=True)
    ip_address: str = Field(max_length=45, unique=True, index=True)
    ssh_username: str = Field(max_length=128, default="admin")
    ssh_password: str = Field(max_length=255, default="")
    enable_password: str = Field(max_length=255, default="")
    ssh_port: int = Field(default=22)
    ap_vlan: int = Field(default=20)
    vendor: str = Field(default="cisco", max_length=32, index=True)
    management_protocol: str = Field(default="snmp+ssh", max_length=32)
    snmp_version: str = Field(default="2c", max_length=10)
    snmp_community_ro: str = Field(default="public", max_length=255)
    snmp_community_rw: str | None = Field(default=None, max_length=255)

    model_info: str | None = Field(default=None, max_length=255)
    ios_version: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    uptime: str | None = Field(default=None, max_length=255)
    is_online: bool | None = Field(default=None)
    last_polled_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)


class MediaPlayer(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_type: str = Field(max_length=20, index=True)
    name: str = Field(max_length=255, index=True)
    model: str = Field(max_length=255)
    ip_address: str = Field(max_length=45, unique=True, index=True)
    mac_address: str | None = Field(default=None, max_length=17)

    is_online: bool | None = Field(default=None)
    hostname: str | None = Field(default=None, max_length=255)
    os_info: str | None = Field(default=None, max_length=255)
    uptime: str | None = Field(default=None, max_length=100)
    open_ports: str | None = Field(default=None, max_length=500)
    last_polled_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)


class EventLog(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    severity: str = Field(default="info", max_length=16, index=True)
    category: str = Field(default="system", max_length=64, index=True)
    event_type: str = Field(max_length=128, index=True)
    message: str = Field(max_length=1024)
    device_kind: str | None = Field(default=None, max_length=32, index=True)
    device_name: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=255, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class CashRegister(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    kkm_number: str = Field(max_length=64, index=True)
    store_code: str | None = Field(default=None, max_length=64, index=True)
    serial_number: str | None = Field(default=None, max_length=128, index=True)
    inventory_number: str | None = Field(default=None, max_length=128, index=True)
    terminal_id_rs: str | None = Field(default=None, max_length=128, index=True)
    terminal_id_sber: str | None = Field(default=None, max_length=128, index=True)
    windows_version: str | None = Field(default=None, max_length=128)
    kkm_type: str = Field(default="retail", max_length=16, index=True)
    cash_number: str | None = Field(default=None, max_length=64, index=True)
    hostname: str = Field(max_length=255, index=True)
    comment: str | None = Field(default=None, max_length=1024)

    is_online: bool | None = Field(default=None, index=True)
    reachability_reason: str | None = Field(default=None, max_length=64)
    last_polled_at: datetime | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime | None = Field(default=None)


class MLFeatureSnapshot(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_kind: str = Field(max_length=32, index=True)
    device_id: uuid.UUID | None = Field(default=None, index=True)
    device_name: str | None = Field(default=None, max_length=255, index=True)
    address: str | None = Field(default=None, max_length=255, index=True)
    is_online: bool | None = Field(default=None, index=True)
    toner_color: str | None = Field(default=None, max_length=16, index=True)
    toner_level: int | None = Field(default=None)
    toner_model: str | None = Field(default=None, max_length=128, index=True)
    source: str = Field(default="poll", max_length=32, index=True)
    hour_of_day: int = Field(default=0, index=True)
    day_of_week: int = Field(default=0, index=True)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class MLModelRegistry(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_family: str = Field(max_length=32, index=True)
    version: str = Field(max_length=64, index=True)
    status: str = Field(default="candidate", max_length=32, index=True)
    train_rows: int = Field(default=0)
    metric_primary: float | None = Field(default=None)
    metric_secondary: float | None = Field(default=None)
    metadata_json: str | None = Field(default=None, max_length=16000)
    trained_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    activated_at: datetime | None = Field(default=None, index=True)


class MLTonerPrediction(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    printer_id: uuid.UUID | None = Field(default=None, index=True)
    printer_name: str | None = Field(default=None, max_length=255, index=True)
    toner_color: str = Field(max_length=16, index=True)
    toner_model: str | None = Field(default=None, max_length=128)
    current_level: int | None = Field(default=None)
    days_to_replacement: float | None = Field(default=None, index=True)
    predicted_replacement_at: datetime | None = Field(default=None, index=True)
    confidence: float = Field(default=0.5)
    model_version: str = Field(max_length=64, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class MLOfflineRiskPrediction(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_kind: str = Field(max_length=32, index=True)
    device_id: uuid.UUID | None = Field(default=None, index=True)
    device_name: str | None = Field(default=None, max_length=255, index=True)
    address: str | None = Field(default=None, max_length=255, index=True)
    risk_score: float = Field(default=0.0, index=True)
    risk_level: str = Field(default="low", max_length=16, index=True)
    confidence: float = Field(default=0.5)
    model_version: str = Field(max_length=64, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
