"""
Network scanner for discovering printers on the local network.

Works universally from Docker bridge network on Windows, macOS, and Linux.
TCP port scanning and SNMP identification work through Docker NAT.
MAC address resolution is best-effort (requires host network on Linux).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import platform
import re
import subprocess
from dataclasses import asdict, dataclass, field

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

SCAN_KEY_PROGRESS = "scan:progress"
SCAN_KEY_RESULTS = "scan:results"
SCAN_KEY_LOCK = "scan:lock"
SCAN_TTL = 600


@dataclass
class DiscoveredDevice:
    ip: str
    mac: str | None = None
    open_ports: list[int] = field(default_factory=list)
    hostname: str | None = None
    is_known: bool = False
    known_printer_id: str | None = None
    ip_changed: bool = False
    old_ip: str | None = None


def _parse_arp_table() -> dict[str, str]:
    """Read system ARP table. Cross-platform with graceful fallback."""
    result: dict[str, str] = {}
    system = platform.system()
    try:
        if system == "Linux":
            # Try /proc/net/arp first (fastest)
            try:
                with open("/proc/net/arp") as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                            result[parts[0]] = parts[3].lower()
            except FileNotFoundError:
                pass
            # Also try `ip neigh` which may have more entries
            if not result:
                try:
                    out = subprocess.run(
                        ["ip", "neigh"], capture_output=True, text=True, timeout=5
                    ).stdout
                    for line in out.splitlines():
                        parts = line.split()
                        if len(parts) >= 5 and parts[3] == "lladdr":
                            result[parts[0]] = parts[4].lower()
                except FileNotFoundError:
                    pass
        elif system == "Darwin":
            out = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            ).stdout
            for line in out.splitlines():
                m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)", line, re.I)
                if m and m.group(2) != "(incomplete)":
                    result[m.group(1)] = m.group(2).lower()
        elif system == "Windows":
            out = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            ).stdout
            for line in out.splitlines():
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([\da-f]{2}-[\da-f]{2}-[\da-f]{2}-[\da-f]{2}-[\da-f]{2}-[\da-f]{2})", line, re.I)
                if m:
                    mac = m.group(2).replace("-", ":").lower()
                    result[m.group(1)] = mac
    except Exception as e:
        logger.debug("ARP table read (best-effort): %s", e)
    return result


async def _tcp_check(ip: str, port: int, timeout: float = 1.0) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _check_ports(ip: str, ports: list[int]) -> list[int]:
    tasks = [_tcp_check(ip, port) for port in ports]
    results = await asyncio.gather(*tasks)
    return [port for port, is_open in zip(ports, results) if is_open]


@dataclass
class SnmpInfo:
    hostname: str | None = None
    mac: str | None = None


def _snmp_query_sync(ip: str) -> SnmpInfo:
    """Query sysDescr + ifPhysAddress via SNMP. Each call gets its own event loop.

    Sequential execution is intentional: pysnmp's UDP transport
    has global state that causes failures under concurrency.
    """
    import warnings
    warnings.filterwarnings("ignore", message=".*pysnmp-lextudio.*")

    OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    OID_IF_PHYS_ADDR = "1.3.6.1.2.1.2.2.1.6"

    async def _query() -> SnmpInfo:
        from pysnmp.hlapi.asyncio import (
            CommunityData, ContextData, ObjectIdentity,
            ObjectType, SnmpEngine, UdpTransportTarget,
        )
        from pysnmp.hlapi.asyncio.cmdgen import getCmd, walkCmd

        info = SnmpInfo()
        engine = SnmpEngine()
        target = UdpTransportTarget((ip, 161), timeout=2, retries=0)
        comm = CommunityData("public")
        ctx = ContextData()

        # sysDescr
        result = await getCmd(
            engine, comm, target, ctx,
            ObjectType(ObjectIdentity(OID_SYS_DESCR)),
        )
        error_indication, _, _, var_binds = result
        if not error_indication and var_binds:
            val = str(var_binds[0][1])
            if val:
                info.hostname = val

        # ifPhysAddress (walk to find first non-empty 6-byte MAC)
        try:
            async for err, _, _, vb in walkCmd(
                engine, comm, target, ctx,
                ObjectType(ObjectIdentity(OID_IF_PHYS_ADDR)),
            ):
                if err:
                    break
                for _, val in vb:
                    if hasattr(val, "asOctets"):
                        octets = val.asOctets()
                        if len(octets) == 6 and any(b != 0 for b in octets):
                            info.mac = ":".join(f"{b:02x}" for b in octets)
                            raise StopAsyncIteration
        except StopAsyncIteration:
            pass

        return info

    try:
        return asyncio.run(_query())
    except Exception:
        return SnmpInfo()


def _snmp_batch(ips: list[str]) -> dict[str, SnmpInfo]:
    """Query SNMP info for a list of IPs sequentially (~0.1s per device)."""
    results: dict[str, SnmpInfo] = {}
    for ip in ips:
        results[ip] = _snmp_query_sync(ip)
    return results


async def _update_progress(
    status: str, scanned: int, total: int, found: int, message: str | None = None
) -> None:
    r = await get_redis()
    progress = {
        "status": status,
        "scanned": scanned,
        "total": total,
        "found": found,
        "message": message,
    }
    await r.setex(SCAN_KEY_PROGRESS, SCAN_TTL, json.dumps(progress))


def _parse_subnets(subnet_str: str) -> list[str]:
    """Parse comma-separated subnets or IP ranges."""
    all_ips: list[str] = []
    for part in subnet_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            network = ipaddress.ip_network(part, strict=False)
            all_ips.extend(str(ip) for ip in network.hosts())
        except ValueError:
            logger.warning("Invalid subnet: %s", part)
    return all_ips


async def scan_subnet(subnet: str, ports_str: str, known_printers: list[dict]) -> list[dict]:
    """
    Scan subnet(s) for devices with open printer ports.
    Supports comma-separated subnets: "10.10.98.0/24, 10.10.99.0/24"
    """
    r = await get_redis()

    if await r.exists(SCAN_KEY_LOCK):
        raise RuntimeError("Scan already in progress")

    await r.setex(SCAN_KEY_LOCK, 300, "1")

    try:
        all_ips = _parse_subnets(subnet)
        if not all_ips:
            raise ValueError(f"No valid IPs in subnet: {subnet}")

        total = len(all_ips)
        ports = [int(p.strip()) for p in ports_str.split(",") if p.strip()]

        await _update_progress("running", 0, total, 0)

        known_by_ip = {p["ip_address"]: p for p in known_printers}
        known_by_mac = {}
        for p in known_printers:
            if p.get("mac_address"):
                known_by_mac[p["mac_address"].lower()] = p

        devices: list[DiscoveredDevice] = []
        batch_size = 50
        scanned = 0

        for i in range(0, total, batch_size):
            batch = all_ips[i : i + batch_size]
            tasks = [_check_ports(ip, ports) for ip in batch]
            results = await asyncio.gather(*tasks)

            for ip, open_ports in zip(batch, results):
                if open_ports:
                    dev = DiscoveredDevice(ip=ip, open_ports=open_ports)
                    if ip in known_by_ip:
                        dev.is_known = True
                        dev.known_printer_id = str(known_by_ip[ip]["id"])
                    devices.append(dev)

            scanned += len(batch)
            await _update_progress("running", min(scanned, total), total, len(devices))

        # SNMP identification + MAC detection for devices with printer ports
        printer_ports = {9100, 631}
        snmp_candidates = [d for d in devices if printer_ports & set(d.open_ports)]
        logger.info("SNMP: %d candidates out of %d found devices", len(snmp_candidates), len(devices))

        if snmp_candidates:
            await _update_progress("running", total, total, len(devices), "Идентификация устройств (SNMP)…")
            snmp_results = await asyncio.to_thread(_snmp_batch, [d.ip for d in snmp_candidates])
            identified = 0
            for dev in snmp_candidates:
                info = snmp_results.get(dev.ip)
                if info:
                    if info.hostname:
                        dev.hostname = info.hostname
                        identified += 1
                    if info.mac:
                        dev.mac = info.mac
                        if not dev.is_known and info.mac in known_by_mac:
                            kp = known_by_mac[info.mac]
                            dev.ip_changed = True
                            dev.old_ip = kp["ip_address"]
                            dev.known_printer_id = str(kp["id"])
            logger.info("SNMP done: %d/%d identified", identified, len(snmp_candidates))

        # ARP table for remaining devices without SNMP MAC (best-effort)
        arp = await asyncio.to_thread(_parse_arp_table)
        for dev in devices:
            if dev.mac:
                continue
            mac = arp.get(dev.ip)
            if mac:
                dev.mac = mac
                if not dev.is_known and mac in known_by_mac:
                    kp = known_by_mac[mac]
                    dev.ip_changed = True
                    dev.old_ip = kp["ip_address"]
                    dev.known_printer_id = str(kp["id"])

        result_dicts = [asdict(d) for d in devices]
        progress = {
            "status": "done",
            "scanned": total,
            "total": total,
            "found": len(devices),
            "message": None,
        }
        await r.setex(SCAN_KEY_PROGRESS, SCAN_TTL, json.dumps(progress))
        await r.setex(SCAN_KEY_RESULTS, SCAN_TTL, json.dumps(result_dicts))
        return result_dicts

    except Exception as e:
        logger.exception("Scan failed")
        await _update_progress("error", 0, 0, 0, str(e))
        raise
    finally:
        await r.delete(SCAN_KEY_LOCK)


async def get_scan_progress() -> dict:
    r = await get_redis()
    data = await r.get(SCAN_KEY_PROGRESS)
    if data:
        return json.loads(data)
    return {"status": "idle", "scanned": 0, "total": 0, "found": 0, "message": None}


async def get_scan_results() -> list[dict]:
    r = await get_redis()
    data = await r.get(SCAN_KEY_RESULTS)
    if data:
        return json.loads(data)
    return []
