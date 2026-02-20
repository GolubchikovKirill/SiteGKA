"""
SNMP service for querying printer status and toner levels.

Uses standard Printer MIB OIDs supported by HP, Ricoh, Kyocera, etc.
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

# Standard Printer MIB OIDs
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"

# Supply OIDs (walk these — index varies per supply slot)
OID_MARKER_DESCR = "1.3.6.1.2.1.43.11.1.1.6.1"
OID_MARKER_MAX = "1.3.6.1.2.1.43.11.1.1.8.1"
OID_MARKER_LEVEL = "1.3.6.1.2.1.43.11.1.1.9.1"

PRINTER_STATUS_MAP = {
    1: "other",
    2: "unknown",
    3: "idle",
    4: "printing",
    5: "warmup",
}

COLOR_KEYWORDS = {
    "black": "black",
    "cyan": "cyan",
    "magenta": "magenta",
    "yellow": "yellow",
    "schwarz": "black",
    "noir": "black",
}

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


def _detect_color(description: str) -> str | None:
    desc_lower = description.lower()
    for keyword, color in COLOR_KEYWORDS.items():
        if keyword in desc_lower:
            return color
    return None


async def _snmp_get(engine: SnmpEngine, target: UdpTransportTarget, community: CommunityData, oid: str) -> str | None:
    error_indication, error_status, _error_index, var_binds = await getCmd(
        engine,
        community,
        target,
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )
    if error_indication or error_status:
        return None
    for _oid, val in var_binds:
        return str(val)
    return None


async def _snmp_walk(
    engine: SnmpEngine, target: UdpTransportTarget, community: CommunityData, oid: str
) -> list[tuple[str, str]]:
    results = []
    async for error_indication, error_status, _error_index, var_binds in nextCmd(
        engine,
        community,
        target,
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            break
        for oid_result, val in var_binds:
            results.append((str(oid_result), str(val)))
    return results


async def _poll_printer_async(ip_address: str, community: str = "public") -> PrinterStatus:
    engine = SnmpEngine()
    try:
        target = UdpTransportTarget((ip_address, 161), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES)
    except Exception:
        return PrinterStatus(is_online=False, status="unreachable")

    comm = CommunityData(community)

    sys_descr = await _snmp_get(engine, target, comm, OID_SYS_DESCR)
    if sys_descr is None:
        return PrinterStatus(is_online=False, status="offline")

    raw_status = await _snmp_get(engine, target, comm, OID_PRINTER_STATUS)
    status_text = "unknown"
    if raw_status is not None:
        try:
            status_text = PRINTER_STATUS_MAP.get(int(raw_status), "unknown")
        except (ValueError, TypeError):
            pass

    descriptions = await _snmp_walk(engine, target, comm, OID_MARKER_DESCR)
    max_levels = await _snmp_walk(engine, target, comm, OID_MARKER_MAX)
    cur_levels = await _snmp_walk(engine, target, comm, OID_MARKER_LEVEL)

    toners: list[TonerLevel] = []
    for i, (oid_d, desc) in enumerate(descriptions):
        max_val = int(max_levels[i][1]) if i < len(max_levels) else 0
        cur_val = int(cur_levels[i][1]) if i < len(cur_levels) else 0

        # Level -3 means "some remaining" per RFC 3805, -2 means unknown
        if cur_val < 0:
            pct = None
        elif max_val > 0:
            pct = max(0, min(100, round(cur_val / max_val * 100)))
        else:
            pct = None

        color = _detect_color(desc)
        toners.append(
            TonerLevel(
                description=desc,
                color=color,
                level_pct=pct,
                max_capacity=max_val,
                current_level=cur_val,
            )
        )

    result = PrinterStatus(
        is_online=True,
        status=status_text,
        toners=toners,
        sys_description=sys_descr,
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
