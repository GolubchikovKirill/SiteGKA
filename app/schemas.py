import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    jti: str | None = None


def _validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v) > 128:
        raise ValueError("Password must be at most 128 characters")
    if v.isdigit() or v.isalpha():
        raise ValueError("Password must contain both letters and numbers")
    return v


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    is_superuser: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None


class UserUpdateMe(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


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
    if not re.match(_IP_PATTERN, v):
        raise ValueError("Invalid IP address format")
    parts = v.split(".")
    if any(int(p) > 255 for p in parts):
        raise ValueError("IP address octets must be 0-255")
    return v


class PrinterCreate(BaseModel):
    printer_type: str = "laser"
    connection_type: str = "ip"
    store_name: str
    model: str
    ip_address: str | None = None
    snmp_community: str = "public"
    host_pc: str | None = None

    @field_validator("store_name")
    @classmethod
    def validate_store_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("store_name must be 1-255 characters")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("model must be 1-255 characters")
        return v

    @field_validator("snmp_community")
    @classmethod
    def validate_community(cls, v: str) -> str:
        if len(v) > 255:
            raise ValueError("snmp_community must be <= 255 characters")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip(v)
        return v

    @field_validator("printer_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("laser", "label"):
            raise ValueError("printer_type must be 'laser' or 'label'")
        return v

    @field_validator("connection_type")
    @classmethod
    def validate_connection_type(cls, v: str) -> str:
        if v not in ("ip", "usb"):
            raise ValueError("connection_type must be 'ip' or 'usb'")
        return v

    @field_validator("host_pc")
    @classmethod
    def validate_host_pc(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("host_pc must be <= 255 characters")
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def check_ip_required_for_ip_type(self) -> "PrinterCreate":
        if self.connection_type == "ip" and not self.ip_address:
            raise ValueError("ip_address is required when connection_type is 'ip'")
        return self


class PrinterUpdate(BaseModel):
    store_name: str | None = None
    model: str | None = None
    ip_address: str | None = None
    snmp_community: str | None = None
    host_pc: str | None = None

    @field_validator("store_name")
    @classmethod
    def validate_store_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 255:
                raise ValueError("store_name must be 1-255 characters")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 255:
                raise ValueError("model must be 1-255 characters")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip(v)
        return v

    @field_validator("host_pc")
    @classmethod
    def validate_host_pc(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("host_pc must be <= 255 characters")
            if not v:
                return None
        return v


class PrinterPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    printer_type: str = "laser"
    connection_type: str = "ip"
    store_name: str
    model: str
    ip_address: str | None = None
    mac_address: str | None = None
    mac_status: str | None = None
    host_pc: str | None = None
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


# ── Scanner schemas ──────────────────────────────────────────────


class ScanRequest(BaseModel):
    subnet: str
    ports: str = "9100,631,80,443"

    @field_validator("subnet")
    @classmethod
    def validate_subnet(cls, v: str) -> str:
        import ipaddress
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if not parts:
            raise ValueError("At least one subnet is required")
        if len(parts) > 10:
            raise ValueError("Maximum 10 subnets allowed")
        for part in parts:
            try:
                net = ipaddress.ip_network(part, strict=False)
                if net.prefixlen < 16:
                    raise ValueError(f"Subnet {part} too large (min /16)")
            except ValueError as e:
                if "too large" in str(e):
                    raise
                raise ValueError(f"Invalid subnet: {part} (expected CIDR, e.g. 10.10.98.0/24)")
        return v

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, v: str) -> str:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if not parts:
            raise ValueError("At least one port is required")
        if len(parts) > 20:
            raise ValueError("Maximum 20 ports allowed")
        for part in parts:
            try:
                port = int(part)
                if port < 1 or port > 65535:
                    raise ValueError(f"Port {port} out of range (1-65535)")
            except ValueError as e:
                if "out of range" in str(e):
                    raise
                raise ValueError(f"Invalid port: {part} (must be integer)")
        return v


class DiscoveredDevice(BaseModel):
    ip: str
    mac: str | None = None
    open_ports: list[int] = []
    hostname: str | None = None
    is_known: bool = False
    known_printer_id: str | None = None
    ip_changed: bool = False
    old_ip: str | None = None


class ScanProgress(BaseModel):
    status: str  # "idle" | "running" | "done" | "error"
    scanned: int = 0
    total: int = 0
    found: int = 0
    message: str | None = None


class ScanResults(BaseModel):
    progress: ScanProgress
    devices: list[DiscoveredDevice] = []


# ── MediaPlayer schemas ─────────────────────────────────────────


_HOSTNAME_PATTERN = r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$"


def _validate_ip_or_hostname(v: str) -> str:
    v = v.strip()
    if not v or len(v) > 255:
        raise ValueError("Address must be 1-255 characters")
    if re.match(_IP_PATTERN, v):
        parts = v.split(".")
        if any(int(p) > 255 for p in parts):
            raise ValueError("IP address octets must be 0-255")
        return v
    if re.match(_HOSTNAME_PATTERN, v):
        return v
    raise ValueError("Must be a valid IP address or hostname")


class MediaPlayerCreate(BaseModel):
    device_type: str
    name: str
    model: str = ""
    ip_address: str
    mac_address: str | None = None

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        if v not in ("nettop", "iconbit", "twix"):
            raise ValueError("device_type must be 'nettop', 'iconbit', or 'twix'")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("name must be 1-255 characters")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 255:
            raise ValueError("model must be <= 255 characters")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip_or_hostname(v)

    @model_validator(mode="after")
    def set_default_model(self) -> "MediaPlayerCreate":
        if not self.model:
            defaults = {"nettop": "Неттоп", "iconbit": "Iconbit", "twix": "Twix"}
            self.model = defaults.get(self.device_type, self.device_type)
        return self


class MediaPlayerUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 255:
                raise ValueError("name must be 1-255 characters")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("model must be <= 255 characters")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip_or_hostname(v)
        return v


class MediaPlayerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_type: str
    name: str
    model: str
    ip_address: str
    mac_address: str | None = None
    is_online: bool | None = None
    hostname: str | None = None
    os_info: str | None = None
    uptime: str | None = None
    open_ports: str | None = None
    last_polled_at: datetime | None = None
    created_at: datetime


class MediaPlayersPublic(BaseModel):
    data: list[MediaPlayerPublic]
    count: int
