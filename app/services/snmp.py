"""
SNMP service for querying printer status and toner levels.

What must be configured on each printer:
  1. SNMP v1/v2c must be ENABLED
     (Network > Protocol Settings, or Admin > Security > SNMP)
  2. Community string must be "public" (read-only) or match what you set in the app
  3. UDP port 161 must be reachable from this server — no firewall blocking it

Supported vendors (standard Printer MIB — RFC 3805):
  HP, Ricoh, Kyocera, Xerox, Canon, Lexmark, Samsung, OKI, Konica Minolta, Epson business

Additional vendor-specific fallback:
  Brother — uses proprietary OIDs when standard MIB returns no data

Printers that will NOT work:
  - Consumer inkjet printers without SNMP (Epson home, HP DeskJet basic models)
  - Very old printers (pre-2000) without Printer MIB support
"""

from __future__ import annotations

import asyncio
import logging
import warnings
from dataclasses import dataclass, field

warnings.filterwarnings("ignore", message=".*pysnmp-lextudio.*")

from pysnmp.hlapi.asyncio import (  # noqa: E402
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
)
from pysnmp.hlapi.asyncio.cmdgen import getCmd, nextCmd  # noqa: E402

logger = logging.getLogger(__name__)

# ── MIB-2 System OIDs ──────────────────────────────────────────────────────
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME  = "1.3.6.1.2.1.1.5.0"

# ── Host Resources MIB — printer status (walk to find any hrDeviceIndex) ───
OID_PRINTER_STATUS_BASE = "1.3.6.1.2.1.25.3.5.1.1"

# ── Printer MIB (RFC 3805) — marker supply OIDs ────────────────────────────
# Walk from base WITHOUT device index so we catch all hrDeviceIndex values.
# Some printers use index 1, others use 2 — walking the base handles both.
OID_MARKER_DESCR = "1.3.6.1.2.1.43.11.1.1.6"   # prtMarkerSuppliesDescription
OID_MARKER_TYPE  = "1.3.6.1.2.1.43.11.1.1.5"   # prtMarkerSuppliesType
OID_MARKER_MAX   = "1.3.6.1.2.1.43.11.1.1.8"   # prtMarkerSuppliesMaxCapacity
OID_MARKER_LEVEL = "1.3.6.1.2.1.43.11.1.1.9"   # prtMarkerSuppliesLevel

# RFC 3805 prtMarkerSuppliesType values
SUPPLY_TYPE_TONER     = 3
SUPPLY_TYPE_INK       = 4
SUPPLY_TYPE_DEVELOPER = 7   # liquid developer — consumable like toner

# ── Brother proprietary OIDs ────────────────────────────────────────────────
# Returns toner remaining as integer percentage (0-100).
# Last OID segment: 1=Black, 2=Cyan, 3=Magenta, 4=Yellow
BROTHER_TONER_BASE = "1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.10.0.1"
BROTHER_COLOR_MAP: dict[str, str] = {
    "1": "black",
    "2": "cyan",
    "3": "magenta",
    "4": "yellow",
}

PRINTER_STATUS_MAP: dict[int, str] = {
    1: "other",
    2: "unknown",
    3: "idle",
    4: "printing",
    5: "warmup",
}

# Supply description keywords → canonical color name.
# Padded with spaces so " bk " matches as a word, not substring of "black".
COLOR_KEYWORDS: dict[str, str] = {
    # English
    "black":       "black",
    "cyan":        "cyan",
    "magenta":     "magenta",
    "yellow":      "yellow",
    "photo black": "black",
    "matte black": "black",
    # Abbreviations (space-padded for word boundary)
    " bk ":  "black",
    "-bk ":  "black",
    " bk\n": "black",
    " k ":   "black",
    " c ":   "cyan",
    " m ":   "magenta",
    " y ":   "yellow",
    # German
    "schwarz": "black",
    "gelb":    "yellow",
    # French
    "noir":   "black",
    "jaune":  "yellow",
    # Russian
    "чёрный":   "black",
    "черный":   "black",
    "голубой":  "cyan",
    "пурпурный":"magenta",
    "жёлтый":  "yellow",
    "желтый":  "yellow",
}

# Words that indicate a supply is NOT toner (drum, maintenance, waste, etc.)
NON_TONER_KEYWORDS: frozenset[str] = frozenset({
    "drum", "kit", "maintenance", "fuser", "waste",
    "belt", "transfer", "roller", "cleaner", "filter",
})

SNMP_TIMEOUT = 3
SNMP_RETRIES = 1


@dataclass
class TonerLevel:
    description: str
    color: str | None
    level_pct: int | None
    max_capacity: int
    current_level: int


@dataclass
class PrinterStatus:
    is_online: bool
    status: str
    toners: list[TonerLevel] = field(default_factory=list)
    toner_black: int | None = None
    toner_cyan: int | None = None
    toner_magenta: int | None = None
    toner_yellow: int | None = None
    sys_description: str | None = None
    vendor: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _detect_color(description: str) -> str | None:
    # Pad with spaces for word-boundary matching on short abbreviations
    desc = " " + description.lower() + " "
    for keyword, color in COLOR_KEYWORDS.items():
        if keyword in desc:
            return color
    return None


def _is_toner_supply(description: str, supply_type: int | None) -> bool:
    """Return True if the supply is toner/ink, not a drum or maintenance kit."""
    if supply_type is not None and supply_type != 0:
        return supply_type in (SUPPLY_TYPE_TONER, SUPPLY_TYPE_INK, SUPPLY_TYPE_DEVELOPER)
    desc_lower = description.lower()
    return not any(kw in desc_lower for kw in NON_TONER_KEYWORDS)


def _detect_vendor(sys_descr: str) -> str | None:
    d = sys_descr.lower()
    if "brother" in d:
        return "brother"
    if "hewlett" in d or " hp " in d or "laserjet" in d or "officejet" in d:
        return "hp"
    if "ricoh" in d or "aficio" in d or "savin" in d or "gestetner" in d or "lanier" in d:
        return "ricoh"
    if "kyocera" in d or "mita" in d:
        return "kyocera"
    if "canon" in d:
        return "canon"
    if "xerox" in d:
        return "xerox"
    if "lexmark" in d:
        return "lexmark"
    if "epson" in d:
        return "epson"
    if "samsung" in d:
        return "samsung"
    if "oki" in d or "okidata" in d:
        return "oki"
    if "konica" in d or "minolta" in d or "bizhub" in d:
        return "konica"
    return None


def _extract_supply_key(oid: str) -> str:
    """Extract the last two OID segments as a correlation key.

    Example: '1.3.6.1.2.1.43.11.1.1.6.1.3' → '1.3'
             hrDeviceIndex=1, supplyIndex=3
    This lets us correctly match description/type/max/level rows
    even when a printer has multiple device instances.
    """
    parts = oid.rsplit(".", 2)
    return f"{parts[-2]}.{parts[-1]}" if len(parts) >= 3 else parts[-1]


# ── SNMP primitives ────────────────────────────────────────────────────────

async def _snmp_get(
    engine: SnmpEngine,
    target: UdpTransportTarget,
    community: CommunityData,
    oid: str,
) -> str | None:
    error_indication, error_status, _error_index, var_binds = await getCmd(
        engine, community, target, ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )
    if error_indication or error_status:
        return None
    for _oid, val in var_binds:
        return str(val)
    return None


async def _snmp_walk(
    engine: SnmpEngine,
    target: UdpTransportTarget,
    community: CommunityData,
    oid: str,
) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    async for error_indication, error_status, _error_index, var_binds in nextCmd(
        engine, community, target, ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            break
        for oid_result, val in var_binds:
            results.append((str(oid_result), str(val)))
    return results


# ── Toner strategies ───────────────────────────────────────────────────────

async def _get_standard_toners(
    engine: SnmpEngine,
    target: UdpTransportTarget,
    comm: CommunityData,
) -> list[TonerLevel]:
    """Standard Printer MIB (RFC 3805). Works on HP, Ricoh, Kyocera, Canon, Xerox, etc."""
    descriptions = await _snmp_walk(engine, target, comm, OID_MARKER_DESCR)
    if not descriptions:
        return []

    # Fetch type, max, level — correlate by OID key (hrDeviceIndex.supplyIndex)
    # rather than by list position, which breaks if walks return different counts.
    types_raw = await _snmp_walk(engine, target, comm, OID_MARKER_TYPE)
    max_raw   = await _snmp_walk(engine, target, comm, OID_MARKER_MAX)
    level_raw = await _snmp_walk(engine, target, comm, OID_MARKER_LEVEL)

    types_map = {_extract_supply_key(oid): val for oid, val in types_raw}
    max_map   = {_extract_supply_key(oid): val for oid, val in max_raw}
    level_map = {_extract_supply_key(oid): val for oid, val in level_raw}

    toners: list[TonerLevel] = []
    for oid_d, desc in descriptions:
        key = _extract_supply_key(oid_d)

        supply_type: int | None = None
        try:
            supply_type = int(types_map[key]) if key in types_map else None
        except (ValueError, TypeError):
            pass

        if not _is_toner_supply(desc, supply_type):
            continue

        try:
            max_val = int(max_map.get(key, 0))
        except (ValueError, TypeError):
            max_val = 0

        try:
            cur_val = int(level_map.get(key, 0))
        except (ValueError, TypeError):
            cur_val = 0

        # RFC 3805 §4.4: negative values have special meaning
        # -3 = "some remaining", -2 = "unknown", -1 = "no restriction"
        if cur_val < 0:
            pct = None
        elif max_val > 0:
            pct = max(0, min(100, round(cur_val / max_val * 100)))
        else:
            pct = None

        toners.append(TonerLevel(
            description=desc,
            color=_detect_color(desc),
            level_pct=pct,
            max_capacity=max_val,
            current_level=cur_val,
        ))

    return toners


async def _get_brother_toners(
    engine: SnmpEngine,
    target: UdpTransportTarget,
    comm: CommunityData,
) -> list[TonerLevel]:
    """Brother proprietary toner OIDs. Returns percentage directly (0-100)."""
    raw = await _snmp_walk(engine, target, comm, BROTHER_TONER_BASE)
    if not raw:
        return []

    toners: list[TonerLevel] = []
    for oid, val in raw:
        color_idx = oid.rsplit(".", 1)[-1]
        color = BROTHER_COLOR_MAP.get(color_idx)
        try:
            pct = max(0, min(100, int(val)))
        except (ValueError, TypeError):
            pct = None

        toners.append(TonerLevel(
            description=f"{color or 'unknown'} toner",
            color=color,
            level_pct=pct,
            max_capacity=100,
            current_level=pct if pct is not None else 0,
        ))
    return toners


# ── Main poller ────────────────────────────────────────────────────────────

async def _poll_printer_async(ip_address: str, community: str = "public") -> PrinterStatus:
    engine = SnmpEngine()
    try:
        target = UdpTransportTarget((ip_address, 161), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES)
    except Exception as e:
        logger.debug("Cannot create SNMP target for %s: %s", ip_address, e)
        return PrinterStatus(is_online=False, status="unreachable")

    comm = CommunityData(community)

    # Basic reachability: sysDescr (OID present on every SNMP-capable device)
    sys_descr = await _snmp_get(engine, target, comm, OID_SYS_DESCR)
    if sys_descr is None:
        logger.debug("%s: no SNMP response (offline or wrong community)", ip_address)
        return PrinterStatus(is_online=False, status="offline")

    vendor = _detect_vendor(sys_descr)
    logger.debug("Polling %s — vendor: %s, descr: %.60s", ip_address, vendor or "unknown", sys_descr)

    # Printer status: walk instead of get to handle any hrDeviceIndex
    status_text = "unknown"
    status_rows = await _snmp_walk(engine, target, comm, OID_PRINTER_STATUS_BASE)
    if status_rows:
        try:
            status_text = PRINTER_STATUS_MAP.get(int(status_rows[0][1]), "unknown")
        except (ValueError, TypeError):
            pass

    # Strategy 1: standard Printer MIB (RFC 3805)
    toners = await _get_standard_toners(engine, target, comm)

    # Strategy 2: vendor-specific fallback
    if not toners:
        if vendor == "brother":
            logger.debug("%s: standard MIB empty, trying Brother proprietary OIDs", ip_address)
            toners = await _get_brother_toners(engine, target, comm)

    if not toners:
        logger.info(
            "%s (%s): no toner data — printer may not support Printer MIB "
            "or SNMP community is restricted",
            ip_address, vendor or "unknown",
        )

    result = PrinterStatus(
        is_online=True,
        status=status_text,
        toners=toners,
        sys_description=sys_descr,
        vendor=vendor,
    )
    for toner in toners:
        match toner.color:
            case "black":
                result.toner_black = toner.level_pct
            case "cyan":
                result.toner_cyan = toner.level_pct
            case "magenta":
                result.toner_magenta = toner.level_pct
            case "yellow":
                result.toner_yellow = toner.level_pct

    return result


def poll_printer(ip_address: str, community: str = "public") -> PrinterStatus:
    """Synchronous wrapper — runs the async poller in a new event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _poll_printer_async(ip_address, community)).result()
    else:
        return asyncio.run(_poll_printer_async(ip_address, community))
