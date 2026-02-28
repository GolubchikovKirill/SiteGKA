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
    last_seen_at: datetime | None = None
    created_at: datetime


class UsersPublic(BaseModel):
    data: list[UserPublic]
    count: int


class Message(BaseModel):
    message: str


class EventLogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: str
    category: str
    event_type: str
    message: str
    device_kind: str | None = None
    device_name: str | None = None
    ip_address: str | None = None
    created_at: datetime


class EventLogsPublic(BaseModel):
    data: list[EventLogPublic]
    count: int


class MLTonerPredictionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    printer_id: uuid.UUID | None = None
    printer_name: str | None = None
    toner_color: str
    toner_model: str | None = None
    current_level: int | None = None
    days_to_replacement: float | None = None
    predicted_replacement_at: datetime | None = None
    confidence: float
    model_version: str
    created_at: datetime


class MLTonerPredictionsPublic(BaseModel):
    data: list[MLTonerPredictionPublic]
    count: int


class MLOfflineRiskPredictionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_kind: str
    device_id: uuid.UUID | None = None
    device_name: str | None = None
    address: str | None = None
    risk_score: float
    risk_level: str
    confidence: float
    model_version: str
    created_at: datetime


class MLOfflineRiskPredictionsPublic(BaseModel):
    data: list[MLOfflineRiskPredictionPublic]
    count: int


class MLModelStatusPublic(BaseModel):
    model_family: str
    version: str
    status: str
    train_rows: int
    metric_primary: float | None = None
    metric_secondary: float | None = None
    trained_at: datetime
    activated_at: datetime | None = None


class MLModelsStatusPublic(BaseModel):
    data: list[MLModelStatusPublic]
    count: int


class CashRegisterCreate(BaseModel):
    kkm_number: str
    store_code: str | None = None
    serial_number: str | None = None
    inventory_number: str | None = None
    terminal_id_rs: str | None = None
    terminal_id_sber: str | None = None
    windows_version: str | None = None
    kkm_type: str = "retail"
    cash_number: str | None = None
    hostname: str
    comment: str | None = None

    @field_validator("kkm_number", "hostname")
    @classmethod
    def validate_required_short_text(cls, v: str) -> str:
        value = v.strip()
        if not value or len(value) > 255:
            raise ValueError("Field must be 1-255 characters")
        return value

    @field_validator("kkm_type")
    @classmethod
    def validate_kkm_type(cls, v: str) -> str:
        value = v.strip().lower()
        if value not in {"retail", "shtrih"}:
            raise ValueError("kkm_type must be 'retail' or 'shtrih'")
        return value

    @field_validator(
        "store_code",
        "serial_number",
        "inventory_number",
        "terminal_id_rs",
        "terminal_id_sber",
        "windows_version",
        "cash_number",
        "comment",
    )
    @classmethod
    def normalize_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 1024:
            raise ValueError("Field is too long")
        return value


class CashRegisterUpdate(BaseModel):
    kkm_number: str | None = None
    store_code: str | None = None
    serial_number: str | None = None
    inventory_number: str | None = None
    terminal_id_rs: str | None = None
    terminal_id_sber: str | None = None
    windows_version: str | None = None
    kkm_type: str | None = None
    cash_number: str | None = None
    hostname: str | None = None
    comment: str | None = None

    @field_validator("kkm_number", "hostname")
    @classmethod
    def validate_required_short_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value or len(value) > 255:
            raise ValueError("Field must be 1-255 characters")
        return value

    @field_validator("kkm_type")
    @classmethod
    def validate_kkm_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip().lower()
        if value not in {"retail", "shtrih"}:
            raise ValueError("kkm_type must be 'retail' or 'shtrih'")
        return value

    @field_validator(
        "store_code",
        "serial_number",
        "inventory_number",
        "terminal_id_rs",
        "terminal_id_sber",
        "windows_version",
        "cash_number",
        "comment",
    )
    @classmethod
    def normalize_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 1024:
            raise ValueError("Field is too long")
        return value


class CashRegisterPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kkm_number: str
    store_code: str | None = None
    serial_number: str | None = None
    inventory_number: str | None = None
    terminal_id_rs: str | None = None
    terminal_id_sber: str | None = None
    windows_version: str | None = None
    kkm_type: str
    cash_number: str | None = None
    hostname: str
    comment: str | None = None
    is_online: bool | None = None
    reachability_reason: str | None = None
    last_polled_at: datetime | None = None
    created_at: datetime


class CashRegistersPublic(BaseModel):
    data: list[CashRegisterPublic]
    count: int


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
    toner_black_name: str | None = None
    toner_cyan_name: str | None = None
    toner_magenta_name: str | None = None
    toner_yellow_name: str | None = None

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

    @field_validator("toner_black_name", "toner_cyan_name", "toner_magenta_name", "toner_yellow_name")
    @classmethod
    def validate_toner_names(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 128:
            raise ValueError("toner name must be <= 128 characters")
        return value

    @model_validator(mode="after")
    def check_ip_required_for_ip_type(self) -> PrinterCreate:
        if self.connection_type == "ip" and not self.ip_address:
            raise ValueError("ip_address is required when connection_type is 'ip'")
        return self


class PrinterUpdate(BaseModel):
    store_name: str | None = None
    model: str | None = None
    ip_address: str | None = None
    snmp_community: str | None = None
    host_pc: str | None = None
    toner_black_name: str | None = None
    toner_cyan_name: str | None = None
    toner_magenta_name: str | None = None
    toner_yellow_name: str | None = None

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

    @field_validator("toner_black_name", "toner_cyan_name", "toner_magenta_name", "toner_yellow_name")
    @classmethod
    def validate_toner_names(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 128:
            raise ValueError("toner name must be <= 128 characters")
        return value


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
    toner_black_name: str | None = None
    toner_cyan_name: str | None = None
    toner_magenta_name: str | None = None
    toner_yellow_name: str | None = None
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


# ── Generic network discovery schemas ────────────────────────────


class DiscoveredNetworkDevice(BaseModel):
    ip: str
    mac: str | None = None
    open_ports: list[int] = []
    hostname: str | None = None
    model_info: str | None = None
    vendor: str | None = None
    device_kind: str | None = None
    is_known: bool = False
    known_device_id: str | None = None
    ip_changed: bool = False
    old_ip: str | None = None


class DiscoveryResults(BaseModel):
    progress: ScanProgress
    devices: list[DiscoveredNetworkDevice] = []


# ── NetworkSwitch schemas ───────────────────────────────────────


class NetworkSwitchCreate(BaseModel):
    name: str
    ip_address: str
    ssh_username: str = "admin"
    ssh_password: str = ""
    enable_password: str = ""
    ssh_port: int = 22
    ap_vlan: int = 20
    vendor: str = "cisco"
    management_protocol: str = "snmp+ssh"
    snmp_version: str = "2c"
    snmp_community_ro: str = "public"
    snmp_community_rw: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("name must be 1-255 characters")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        return _validate_ip(v)

    @field_validator("ssh_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if v < 1 or v > 65535:
            raise ValueError("ssh_port must be 1-65535")
        return v

    @field_validator("ap_vlan")
    @classmethod
    def validate_vlan(cls, v: int) -> int:
        if v < 1 or v > 4094:
            raise ValueError("ap_vlan must be 1-4094")
        return v

    @field_validator("vendor")
    @classmethod
    def validate_vendor(cls, v: str) -> str:
        normalized = v.strip().lower()
        allowed = {"cisco", "dlink", "generic"}
        if normalized not in allowed:
            raise ValueError("vendor must be one of: cisco, dlink, generic")
        return normalized

    @field_validator("management_protocol")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        normalized = v.strip().lower()
        allowed = {"snmp", "ssh", "snmp+ssh"}
        if normalized not in allowed:
            raise ValueError("management_protocol must be one of: snmp, ssh, snmp+ssh")
        return normalized

    @field_validator("snmp_version")
    @classmethod
    def validate_snmp_version(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in {"2c"}:
            raise ValueError("snmp_version currently supports only '2c'")
        return normalized

    @field_validator("snmp_community_ro")
    @classmethod
    def validate_snmp_ro(cls, v: str) -> str:
        value = v.strip()
        if not value or len(value) > 255:
            raise ValueError("snmp_community_ro must be 1-255 characters")
        return value

    @field_validator("snmp_community_rw")
    @classmethod
    def validate_snmp_rw(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if len(value) > 255:
            raise ValueError("snmp_community_rw must be <= 255 characters")
        return value or None


class NetworkSwitchUpdate(BaseModel):
    name: str | None = None
    ip_address: str | None = None
    ssh_username: str | None = None
    ssh_password: str | None = None
    enable_password: str | None = None
    ssh_port: int | None = None
    ap_vlan: int | None = None
    vendor: str | None = None
    management_protocol: str | None = None
    snmp_version: str | None = None
    snmp_community_ro: str | None = None
    snmp_community_rw: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 255:
                raise ValueError("name must be 1-255 characters")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_ip(v)
        return v

    @field_validator("vendor")
    @classmethod
    def validate_vendor(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        allowed = {"cisco", "dlink", "generic"}
        if normalized not in allowed:
            raise ValueError("vendor must be one of: cisco, dlink, generic")
        return normalized

    @field_validator("management_protocol")
    @classmethod
    def validate_protocol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        allowed = {"snmp", "ssh", "snmp+ssh"}
        if normalized not in allowed:
            raise ValueError("management_protocol must be one of: snmp, ssh, snmp+ssh")
        return normalized

    @field_validator("snmp_version")
    @classmethod
    def validate_snmp_version(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        if normalized not in {"2c"}:
            raise ValueError("snmp_version currently supports only '2c'")
        return normalized

    @field_validator("snmp_community_ro", "snmp_community_rw")
    @classmethod
    def validate_communities(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if len(value) > 255:
            raise ValueError("SNMP community must be <= 255 characters")
        return value or None


class NetworkSwitchPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    ip_address: str
    ssh_username: str
    ssh_port: int = 22
    ap_vlan: int = 20
    vendor: str = "cisco"
    management_protocol: str = "snmp+ssh"
    snmp_version: str = "2c"
    snmp_community_ro: str = "public"
    snmp_community_rw: str | None = None
    model_info: str | None = None
    ios_version: str | None = None
    hostname: str | None = None
    uptime: str | None = None
    is_online: bool | None = None
    last_polled_at: datetime | None = None
    created_at: datetime


class NetworkSwitchesPublic(BaseModel):
    data: list[NetworkSwitchPublic]
    count: int


class AccessPointInfo(BaseModel):
    mac_address: str
    port: str
    vlan: int
    ip_address: str | None = None
    cdp_name: str | None = None
    cdp_platform: str | None = None
    poe_power: str | None = None
    poe_status: str | None = None


class SwitchPortInfo(BaseModel):
    port: str
    if_index: int
    description: str | None = None
    admin_status: str | None = None
    oper_status: str | None = None
    status_text: str | None = None
    vlan_text: str | None = None
    duplex_text: str | None = None
    speed_text: str | None = None
    media_type: str | None = None
    speed_mbps: int | None = None
    duplex: str | None = None
    vlan: int | None = None
    port_mode: str | None = None
    access_vlan: int | None = None
    trunk_native_vlan: int | None = None
    trunk_allowed_vlans: str | None = None
    poe_enabled: bool | None = None
    poe_power_w: float | None = None
    mac_count: int | None = None


class SwitchPortsPublic(BaseModel):
    data: list[SwitchPortInfo]
    count: int


class SwitchPortAdminStateUpdate(BaseModel):
    admin_state: str

    @field_validator("admin_state")
    @classmethod
    def validate_admin_state(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in {"up", "down"}:
            raise ValueError("admin_state must be 'up' or 'down'")
        return normalized


class SwitchPortDescriptionUpdate(BaseModel):
    description: str

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        value = v.strip()
        if len(value) > 255:
            raise ValueError("description must be <= 255 characters")
        return value


class SwitchPortVlanUpdate(BaseModel):
    vlan: int

    @field_validator("vlan")
    @classmethod
    def validate_vlan(cls, v: int) -> int:
        if v < 1 or v > 4094:
            raise ValueError("vlan must be 1-4094")
        return v


class SwitchPortPoeUpdate(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in {"on", "off", "cycle"}:
            raise ValueError("action must be one of: on, off, cycle")
        return normalized


class SwitchPortModeUpdate(BaseModel):
    mode: str
    access_vlan: int | None = None
    native_vlan: int | None = None
    allowed_vlans: str | None = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in {"access", "trunk"}:
            raise ValueError("mode must be one of: access, trunk")
        return normalized

    @field_validator("access_vlan", "native_vlan")
    @classmethod
    def validate_vlan_fields(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 1 or v > 4094:
            raise ValueError("VLAN must be 1-4094")
        return v

    @field_validator("allowed_vlans")
    @classmethod
    def validate_allowed_vlans(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 255:
            raise ValueError("allowed_vlans must be <= 255 characters")
        if not re.match(r"^[0-9,\-\s]+$", value):
            raise ValueError("allowed_vlans supports digits, commas, spaces and hyphens only")
        return value


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
    hostname: str | None = None
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

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 255:
            raise ValueError("hostname must be <= 255 characters")
        if not re.match(_HOSTNAME_PATTERN, value):
            raise ValueError("hostname format is invalid")
        return value

    @model_validator(mode="after")
    def set_default_model(self) -> MediaPlayerCreate:
        if not self.model:
            defaults = {"nettop": "Неттоп", "iconbit": "Iconbit", "twix": "Twix"}
            self.model = defaults.get(self.device_type, self.device_type)
        return self


class MediaPlayerUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    ip_address: str | None = None
    hostname: str | None = None
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

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if len(value) > 255:
            raise ValueError("hostname must be <= 255 characters")
        if not re.match(_HOSTNAME_PATTERN, value):
            raise ValueError("hostname format is invalid")
        return value


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
