"""Polling service for media players and generic network devices.

Collects: online status, hostname, OS info, uptime, MAC address, open ports.
Uses SNMP where available, with TCP port scan and ARP fallback.
"""

from __future__ import annotations

import asyncio
import logging
import socket
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
from pysnmp.hlapi.asyncio.cmdgen import getCmd, walkCmd  # noqa: E402

logger = logging.getLogger(__name__)

SNMP_TIMEOUT = 3
SNMP_RETRIES = 1

OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_IF_PHYS_ADDR = "1.3.6.1.2.1.2.2.1.6"

SCAN_PORTS = [22, 80, 135, 139, 443, 445, 554, 3389, 8080, 9090]
TCP_TIMEOUT = 1.5


@dataclass
class DeviceStatus:
    is_online: bool = False
    hostname: str | None = None
    os_info: str | None = None
    uptime: str | None = None
    mac_address: str | None = None
    open_ports: list[int] = field(default_factory=list)


def _format_uptime(ticks: int) -> str:
    seconds = ticks // 100
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    return " ".join(parts)


async def _check_port(ip: str, port: int) -> int | None:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=TCP_TIMEOUT,
        )
        writer.close()
        await writer.wait_closed()
        return port
    except (OSError, asyncio.TimeoutError):
        return None


async def _scan_ports(ip: str) -> list[int]:
    tasks = [_check_port(ip, port) for port in SCAN_PORTS]
    results = await asyncio.gather(*tasks)
    return sorted(p for p in results if p is not None)


async def _get_snmp_info(ip: str, community: str = "public") -> dict:
    """Retrieve sysDescr, sysName, sysUpTime via SNMP GET."""
    engine = SnmpEngine()
    try:
        target = UdpTransportTarget((ip, 161), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES)
    except Exception:
        return {}

    comm = CommunityData(community)
    result = {}

    try:
        err_indication, err_status, _, var_binds = await getCmd(
            engine, comm, target, ContextData(),
            ObjectType(ObjectIdentity(OID_SYS_DESCR)),
            ObjectType(ObjectIdentity(OID_SYS_NAME)),
            ObjectType(ObjectIdentity(OID_SYS_UPTIME)),
        )
        if err_indication or err_status:
            return {}

        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val).strip()
            if not val_str:
                continue
            if OID_SYS_DESCR in oid_str:
                result["os_info"] = val_str[:255]
            elif OID_SYS_NAME in oid_str:
                result["hostname"] = val_str[:255]
            elif OID_SYS_UPTIME in oid_str:
                try:
                    ticks = int(val)
                    result["uptime"] = _format_uptime(ticks)
                except (ValueError, TypeError):
                    result["uptime"] = val_str
    except Exception as e:
        logger.debug("SNMP GET failed for %s: %s", ip, e)

    return result


async def _get_snmp_mac(ip: str, community: str = "public") -> str | None:
    engine = SnmpEngine()
    try:
        target = UdpTransportTarget((ip, 161), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES)
    except Exception:
        return None

    comm = CommunityData(community)
    try:
        async for err, _, _, vb in walkCmd(
            engine, comm, target, ContextData(),
            ObjectType(ObjectIdentity(OID_IF_PHYS_ADDR)),
            lexicographicMode=False,
        ):
            if err:
                break
            for _, val in vb:
                if hasattr(val, "asOctets"):
                    octets = val.asOctets()
                    if len(octets) == 6 and any(b != 0 for b in octets):
                        return ":".join(f"{b:02x}" for b in octets)
    except Exception:
        pass
    return None


def _get_mac_from_arp(ip: str) -> str | None:
    import subprocess
    try:
        subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        with open("/proc/net/arp") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip:
                    mac = parts[3].lower()
                    if mac != "00:00:00:00:00:00" and len(mac) == 17:
                        return mac
    except (FileNotFoundError, PermissionError):
        pass

    try:
        out = subprocess.run(
            ["ip", "neigh", "show", ip],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        if "lladdr" in out:
            parts = out.split()
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                mac = parts[idx + 1].lower()
                if len(mac) == 17:
                    return mac
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


async def poll_device(ip: str, community: str = "public") -> DeviceStatus:
    """Poll a network device for status information."""
    status = DeviceStatus()

    ports_task = _scan_ports(ip)
    snmp_task = _get_snmp_info(ip, community)
    mac_task = _get_snmp_mac(ip, community)

    open_ports, snmp_info, mac = await asyncio.gather(
        ports_task, snmp_task, mac_task,
    )

    status.open_ports = open_ports
    status.is_online = bool(open_ports) or bool(snmp_info)

    if snmp_info:
        status.hostname = snmp_info.get("hostname")
        status.os_info = snmp_info.get("os_info")
        status.uptime = snmp_info.get("uptime")

    status.mac_address = mac
    if not mac:
        arp_mac = await asyncio.to_thread(_get_mac_from_arp, ip)
        if arp_mac:
            status.mac_address = arp_mac

    return status


def poll_device_sync(ip: str, community: str = "public") -> DeviceStatus:
    """Synchronous wrapper for poll_device."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, poll_device(ip, community)).result()
    else:
        return asyncio.run(poll_device(ip, community))
