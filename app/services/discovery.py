from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from time import perf_counter

import httpx

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DISCOVERY_TTL = 600
_DISCOVERY_TCP_SEMAPHORE = asyncio.Semaphore(max(settings.SCAN_TCP_CONCURRENCY, 1))
_DISCOVERY_HTTP_TIMEOUT = 2.0


@dataclass
class DiscoveredNetworkDevice:
    ip: str
    mac: str | None = None
    open_ports: list[int] = field(default_factory=list)
    hostname: str | None = None
    model_info: str | None = None
    vendor: str | None = None
    device_kind: str | None = None
    is_known: bool = False
    known_device_id: str | None = None
    ip_changed: bool = False
    old_ip: str | None = None


def _progress_key(kind: str) -> str:
    return f"discover:{kind}:progress"


def _results_key(kind: str) -> str:
    return f"discover:{kind}:results"


def _lock_key(kind: str) -> str:
    return f"discover:{kind}:lock"


def _parse_subnets(subnet_str: str) -> list[str]:
    all_ips: list[str] = []
    seen: set[str] = set()
    max_hosts = max(settings.SCAN_MAX_HOSTS, 1)
    for part in subnet_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            network = ipaddress.ip_network(part, strict=False)
            for ip in network.hosts():
                ip_str = str(ip)
                if ip_str in seen:
                    continue
                seen.add(ip_str)
                all_ips.append(ip_str)
                if len(all_ips) > max_hosts:
                    raise ValueError(
                        f"Too many hosts to scan ({len(all_ips)}). "
                        f"Limit is {max_hosts}; split subnet ranges."
                    )
        except ValueError as exc:
            if "Too many hosts" in str(exc):
                raise
            logger.warning("Invalid discovery subnet: %s", part)
    return all_ips


def _parse_ports(ports_str: str) -> list[int]:
    ports: list[int] = []
    seen: set[int] = set()
    for raw in ports_str.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            port = int(raw)
        except ValueError:
            logger.warning("Invalid discovery port: %s", raw)
            continue
        if not (1 <= port <= 65535):
            logger.warning("Discovery port out of range: %s", raw)
            continue
        if port in seen:
            continue
        seen.add(port)
        ports.append(port)
    return ports


async def _tcp_check(ip: str, port: int) -> bool:
    timeout = max(settings.SCAN_TCP_TIMEOUT, 0.1)
    retries = max(settings.SCAN_TCP_RETRIES, 0)
    for attempt in range(retries + 1):
        try:
            async with _DISCOVERY_TCP_SEMAPHORE:
                _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
                writer.close()
                await writer.wait_closed()
                return True
        except (TimeoutError, OSError):
            if attempt < retries:
                await asyncio.sleep(0.05 * (attempt + 1))
    return False


async def _check_ports(ip: str, ports: list[int]) -> list[int]:
    tasks = [_tcp_check(ip, port) for port in ports]
    results = await asyncio.gather(*tasks)
    return [port for port, is_open in zip(ports, results) if is_open]


def _normalize_vendor(value: str | None) -> str | None:
    if not value:
        return None
    low = value.lower()
    if "cisco" in low or "ios" in low or "catalyst" in low:
        return "cisco"
    if "d-link" in low or "dlink" in low:
        return "dlink"
    if "mikrotik" in low:
        return "mikrotik"
    if "hp" in low or "aruba" in low:
        return "aruba"
    return "generic"


async def _snmp_switch_fingerprint(ip: str, community: str = "public") -> dict[str, str | None]:
    try:
        from pysnmp.hlapi.asyncio import CommunityData, ContextData, ObjectIdentity, ObjectType, SnmpEngine, UdpTransportTarget
        from pysnmp.hlapi.asyncio.cmdgen import getCmd
    except Exception:
        return {}
    try:
        target = UdpTransportTarget((ip, 161), timeout=2, retries=0)
    except Exception:
        return {}
    engine = SnmpEngine()
    oid_sys_descr = "1.3.6.1.2.1.1.1.0"
    oid_sys_name = "1.3.6.1.2.1.1.5.0"
    try:
        err_indication, err_status, _, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            target,
            ContextData(),
            ObjectType(ObjectIdentity(oid_sys_descr)),
            ObjectType(ObjectIdentity(oid_sys_name)),
        )
        if err_indication or err_status:
            return {}
        values: dict[str, str | None] = {"model_info": None, "hostname": None}
        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val).strip()
            if oid_sys_descr in oid_str:
                values["model_info"] = val_str
            elif oid_sys_name in oid_str:
                values["hostname"] = val_str
        return values
    except Exception:
        return {}


async def _iconbit_fingerprint(ip: str) -> dict[str, str | None]:
    base = f"http://{ip}:8081"
    auth = ("admin", "admin")
    try:
        async with httpx.AsyncClient(timeout=_DISCOVERY_HTTP_TIMEOUT, follow_redirects=True, auth=auth) as client:
            main = await client.get(base)
            if main.status_code != 200:
                return {}
            text = main.text[:5000]
            hints = (
                "status.xml" in text
                or "/now" in text
                or "delete?file=" in text
                or "iconbit" in text.lower()
            )
            if not hints:
                status_xml = await client.get(f"{base}/status.xml")
                now = await client.get(f"{base}/now")
                hints = status_xml.status_code == 200 or now.status_code == 200
            if not hints:
                return {}
            model_match = re.search(r"<title>([^<]+)</title>", text, re.IGNORECASE)
            model = model_match.group(1).strip() if model_match else "Iconbit"
            return {"model_info": model, "device_kind": "iconbit"}
    except Exception:
        return {}
    return {}


async def _update_progress(kind: str, status: str, scanned: int, total: int, found: int, message: str | None = None) -> None:
    r = await get_redis()
    payload = {"status": status, "scanned": scanned, "total": total, "found": found, "message": message}
    await r.setex(_progress_key(kind), DISCOVERY_TTL, json.dumps(payload))


async def run_discovery_scan(kind: str, subnet: str, ports_str: str, known_devices: list[dict]) -> list[dict]:
    if kind not in {"iconbit", "switch"}:
        raise ValueError("Unsupported discovery kind")
    r = await get_redis()
    lock_key = _lock_key(kind)
    if await r.exists(lock_key):
        raise RuntimeError("Discovery scan already in progress")
    await r.setex(lock_key, 300, "1")
    started = perf_counter()
    try:
        all_ips = _parse_subnets(subnet)
        if not all_ips:
            raise ValueError("No valid IPs to scan")
        ports = _parse_ports(ports_str)
        if not ports:
            raise ValueError("No valid ports configured")

        known_by_ip = {d["ip_address"]: d for d in known_devices if d.get("ip_address")}
        known_by_mac = {d["mac_address"].lower(): d for d in known_devices if d.get("mac_address")}

        await _update_progress(kind, "running", 0, len(all_ips), 0)
        devices: list[DiscoveredNetworkDevice] = []
        batch_size = 64
        scanned = 0
        for i in range(0, len(all_ips), batch_size):
            batch = all_ips[i : i + batch_size]
            results = await asyncio.gather(*[_check_ports(ip, ports) for ip in batch])
            for ip, open_ports in zip(batch, results):
                if not open_ports:
                    continue
                device = DiscoveredNetworkDevice(ip=ip, open_ports=open_ports)
                if ip in known_by_ip:
                    device.is_known = True
                    device.known_device_id = str(known_by_ip[ip]["id"])
                devices.append(device)
            scanned += len(batch)
            await _update_progress(kind, "running", scanned, len(all_ips), len(devices))

        if devices:
            await _update_progress(kind, "running", len(all_ips), len(all_ips), len(devices), "Идентификация устройств…")
            if kind == "iconbit":
                for dev in devices:
                    if 8081 not in dev.open_ports:
                        continue
                    info = await _iconbit_fingerprint(dev.ip)
                    if not info:
                        continue
                    dev.device_kind = "iconbit"
                    dev.model_info = info.get("model_info")
            else:
                for dev in devices:
                    info = await _snmp_switch_fingerprint(dev.ip)
                    if not info:
                        continue
                    dev.hostname = info.get("hostname")
                    dev.model_info = info.get("model_info")
                    dev.device_kind = "switch"
                    dev.vendor = _normalize_vendor(dev.model_info)

            # Best-effort ARP enrich and known by MAC.
            from app.services.scanner import _parse_arp_table

            arp = await asyncio.to_thread(_parse_arp_table)
            for dev in devices:
                mac = arp.get(dev.ip)
                if mac:
                    dev.mac = mac
                    known = known_by_mac.get(mac.lower())
                    if known and not dev.is_known:
                        dev.is_known = True
                        dev.known_device_id = str(known["id"])
                        dev.ip_changed = True
                        dev.old_ip = known.get("ip_address")

        # Keep only confidently identified target devices.
        if kind == "iconbit":
            devices = [d for d in devices if d.device_kind == "iconbit"]
        else:
            devices = [d for d in devices if d.device_kind == "switch"]

        result = [asdict(d) for d in devices]
        await r.setex(_results_key(kind), DISCOVERY_TTL, json.dumps(result))
        await _update_progress(kind, "done", len(all_ips), len(all_ips), len(result))
        return result
    finally:
        await r.delete(lock_key)
        logger.info("Discovery scan '%s' completed in %.2fs", kind, max(perf_counter() - started, 0))


async def get_discovery_progress(kind: str) -> dict:
    r = await get_redis()
    data = await r.get(_progress_key(kind))
    if data:
        return json.loads(data)
    return {"status": "idle", "scanned": 0, "total": 0, "found": 0, "message": None}


async def get_discovery_results(kind: str) -> list[dict]:
    r = await get_redis()
    data = await r.get(_results_key(kind))
    if data:
        return json.loads(data)
    return []
