import asyncio
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy import or_
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.redis import get_redis
from app.models import Printer
from app.observability.metrics import printer_polls_total, set_device_counts
from app.schemas import (
    Message,
    PrinterCreate,
    PrinterPublic,
    PrintersPublic,
    PrinterUpdate,
)
from app.services.ping import check_port
from app.services.poll_resilience import apply_poll_outcome, is_circuit_open, poll_jitter_sync
from app.services.snmp import get_snmp_mac, poll_printer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["printers"])

MAX_POLL_WORKERS = 20
CACHE_TTL = 30

_CYR_TO_LAT = str.maketrans("АВЕКМНОРСТХавекмнорстх", "ABEKMHOPCTXabekmhopctx")


def _normalize(text: str) -> str:
    return text.translate(_CYR_TO_LAT)


def _search_filter(column, query: str):
    normalized = _normalize(query)
    return or_(
        sa_func.translate(column, "АВЕКМНОРСТХаверкмнорстх", "ABEKMHOPCTXabekmhopctx").ilike(f"%{normalized}%"),
        column.ilike(f"%{query}%"),
    )


async def _invalidate_printer_cache() -> None:
    try:
        r = await get_redis()
        keys = []
        async for key in r.scan_iter("printers:*"):
            keys.append(key)
        if keys:
            await r.delete(*keys)
    except Exception as e:
        logger.warning("Cache invalidation failed: %s", e)


@router.get("/", response_model=PrintersPublic)
async def read_printers(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, le=500),
    store_name: str | None = None,
    printer_type: str = Query(default="laser"),
) -> PrintersPublic:
    cache_key = f"printers:{printer_type}:{store_name or ''}:{skip}:{limit}"
    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            return PrintersPublic(**json.loads(cached))
    except Exception:
        pass

    statement = select(Printer).where(Printer.printer_type == printer_type)
    count_stmt = select(func.count()).select_from(Printer).where(Printer.printer_type == printer_type)
    if store_name:
        flt = _search_filter(Printer.store_name, store_name)
        statement = statement.where(flt)
        count_stmt = count_stmt.where(flt)
    count = session.exec(count_stmt).one()
    printers = session.exec(statement.offset(skip).limit(limit).order_by(Printer.store_name)).all()
    result = PrintersPublic(data=printers, count=count)

    try:
        r = await get_redis()
        await r.setex(cache_key, CACHE_TTL, result.model_dump_json())
    except Exception:
        pass

    return result


@router.post("/", response_model=PrinterPublic, dependencies=[Depends(get_current_active_superuser)])
async def create_printer(session: SessionDep, printer_in: PrinterCreate) -> Printer:
    if printer_in.connection_type == "ip" and printer_in.ip_address:
        existing = session.exec(select(Printer).where(Printer.ip_address == printer_in.ip_address)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Printer with this IP already exists")
    printer = Printer(**printer_in.model_dump())
    session.add(printer)
    session.commit()
    session.refresh(printer)
    await _invalidate_printer_cache()
    return printer


@router.get("/{printer_id}", response_model=PrinterPublic)
def read_printer(printer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Printer:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


@router.patch("/{printer_id}", response_model=PrinterPublic, dependencies=[Depends(get_current_active_superuser)])
async def update_printer(session: SessionDep, printer_id: uuid.UUID, printer_in: PrinterUpdate) -> Printer:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    update_data = printer_in.model_dump(exclude_unset=True)
    if "ip_address" in update_data and update_data["ip_address"] is not None:
        existing = session.exec(
            select(Printer).where(
                Printer.ip_address == update_data["ip_address"],
                Printer.id != printer_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Printer with this IP already exists")
    printer.updated_at = datetime.now(UTC)
    printer.sqlmodel_update(update_data)
    session.add(printer)
    session.commit()
    session.refresh(printer)
    await _invalidate_printer_cache()
    return printer


@router.delete("/{printer_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_printer(session: SessionDep, printer_id: uuid.UUID) -> Message:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    session.delete(printer)
    session.commit()
    await _invalidate_printer_cache()
    return Message(message="Printer deleted")


# ── Polling helpers ──────────────────────────────────────────────


def _poll_one(printer: Printer) -> tuple[str, object | None, str | None]:
    if printer.connection_type == "usb" or not printer.ip_address:
        return "", None, None
    ip = printer.ip_address
    try:
        poll_jitter_sync()
        if printer.printer_type == "label":
            online = check_port(ip)
            return ip, {"is_online": online}, None
        else:
            result = poll_printer(ip, printer.snmp_community)
            current_mac = None
            if result.is_online:
                current_mac = get_snmp_mac(ip, printer.snmp_community)
            return ip, result, current_mac
    except Exception as e:
        logger.warning("Poll failed for %s: %s", ip, e)
        return ip, None, None


def _probe_ip_for_mac(ip: str, community: str = "public") -> tuple[str, str | None]:
    """Check if IP responds to SNMP and return its MAC."""
    try:
        mac = get_snmp_mac(ip, community)
        return ip, mac
    except Exception:
        return ip, None


def _verify_mac(printer: Printer, current_mac: str | None) -> str | None:
    """Compare stored MAC with detected MAC, auto-save on first detection."""
    if current_mac is None:
        return "unavailable"
    if not printer.mac_address:
        printer.mac_address = current_mac
        return "verified"
    if printer.mac_address.lower() == current_mac.lower():
        return "verified"
    return "mismatch"


def _do_poll_all(printers: list[Printer]) -> dict[str, tuple[object | None, str | None]]:
    """Run all polls in a thread pool."""
    results: dict[str, tuple[object | None, str | None]] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_POLL_WORKERS, len(printers))) as pool:
        futures = {pool.submit(_poll_one, p): p.ip_address for p in printers}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                _, result, mac = future.result()
            except Exception as e:
                logger.warning("Poll failed for %s: %s", ip, e)
                result, mac = None, None
            results[ip] = (result, mac)
    return results


async def _find_by_mac_in_scan_cache(mac: str) -> str | None:
    """Look up MAC in last scan results from Redis. Returns new IP or None."""
    try:
        r = await get_redis()
        data = await r.get("scan:results")
        if not data:
            return None
        import json as _json
        devices = _json.loads(data)
        mac_lower = mac.lower()
        for dev in devices:
            if dev.get("mac") and dev["mac"].lower() == mac_lower:
                return dev["ip"]
    except Exception:
        pass
    return None


def _resolve_offline_printers(
    offline_printers: list[Printer],
    online_macs: dict[str, str],
) -> dict[str, str]:
    """For offline printers with known MAC, check if any online printer
    reported the same MAC at a different IP (IP swap detection).
    Returns {printer_ip: new_ip} mapping."""
    reassigned: dict[str, str] = {}
    mac_to_new_ip = {mac.lower(): ip for ip, mac in online_macs.items()}
    for p in offline_printers:
        if p.mac_address:
            new_ip = mac_to_new_ip.get(p.mac_address.lower())
            if new_ip and new_ip != p.ip_address:
                reassigned[p.ip_address] = new_ip
    return reassigned


# ── Poll endpoints ───────────────────────────────────────────────


@router.post("/{printer_id}/poll", response_model=PrinterPublic)
async def poll_single_printer(printer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Printer:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    if printer.connection_type == "usb" or not printer.ip_address:
        printer_polls_total.labels(mode="single", printer_type=printer.printer_type, result="unsupported").inc()
        raise HTTPException(status_code=400, detail="USB printers cannot be polled")

    if printer.printer_type == "label":
        online = await asyncio.to_thread(check_port, printer.ip_address)
        printer.is_online = online
        printer.status = "online" if online else "offline"
        printer.mac_status = None
        printer_polls_total.labels(
            mode="single",
            printer_type=printer.printer_type,
            result="online" if online else "offline",
        ).inc()
    else:
        _, result, current_mac = await asyncio.to_thread(_poll_one, printer)
        if result is None or not result.is_online:
            # Printer offline at stored IP — try to find by MAC
            if printer.mac_address:
                new_ip = await _find_by_mac_in_scan_cache(printer.mac_address)
                if new_ip and new_ip != printer.ip_address:
                    logger.info(
                        "Printer %s (%s) found at new IP %s (was %s)",
                        printer.store_name, printer.mac_address, new_ip, printer.ip_address,
                    )
                    conflict = session.exec(
                        select(Printer).where(
                            Printer.ip_address == new_ip,
                            Printer.id != printer.id,
                        )
                    ).first()
                    if not conflict:
                        printer.ip_address = new_ip
                        _, result, current_mac = await asyncio.to_thread(_poll_one, printer)

            if result is None:
                printer.is_online = False
                printer.status = "error"
                printer.mac_status = "unavailable"
                printer_polls_total.labels(mode="single", printer_type=printer.printer_type, result="error").inc()
            elif not result.is_online:
                printer.is_online = False
                printer.status = "offline"
                printer.mac_status = "unavailable"
                printer_polls_total.labels(mode="single", printer_type=printer.printer_type, result="offline").inc()
            else:
                printer.is_online = result.is_online
                printer.status = result.status
                printer.toner_black = result.toner_black
                printer.toner_cyan = result.toner_cyan
                printer.toner_magenta = result.toner_magenta
                printer.toner_yellow = result.toner_yellow
                printer.mac_status = _verify_mac(printer, current_mac)
                printer_polls_total.labels(mode="single", printer_type=printer.printer_type, result="online").inc()
        else:
            printer.is_online = result.is_online
            printer.status = result.status
            printer.toner_black = result.toner_black
            printer.toner_cyan = result.toner_cyan
            printer.toner_magenta = result.toner_magenta
            printer.toner_yellow = result.toner_yellow
            printer.mac_status = _verify_mac(printer, current_mac)
            printer_polls_total.labels(mode="single", printer_type=printer.printer_type, result="online").inc()

    printer.last_polled_at = datetime.now(UTC)
    session.add(printer)
    session.commit()
    session.refresh(printer)
    await _invalidate_printer_cache()
    return printer


@router.post("/poll-all", response_model=PrintersPublic)
async def poll_all_printers(
    session: SessionDep,
    current_user: CurrentUser,
    printer_type: str = Query(default="laser"),
) -> PrintersPublic:
    lock_key = f"lock:poll-all:printers:{printer_type}"
    lock_acquired = True
    try:
        r = await get_redis()
        lock_acquired = bool(await r.set(lock_key, "1", ex=45, nx=True))
    except Exception:
        lock_acquired = True

    all_printers = session.exec(select(Printer).where(Printer.printer_type == printer_type)).all()
    set_device_counts(
        kind="printer",
        total=len(all_printers),
        online=sum(1 for p in all_printers if p.is_online),
    )
    if not lock_acquired:
        logger.info("Skipping duplicate poll-all request for printers (%s): lock busy", printer_type)
        return PrintersPublic(data=all_printers, count=len(all_printers))
    if not all_printers:
        return PrintersPublic(data=[], count=0)

    printers = [p for p in all_printers if p.connection_type != "usb" and p.ip_address]
    if not printers:
        return PrintersPublic(data=all_printers, count=len(all_printers))

    poll_targets: list[Printer] = []
    for printer in printers:
        if await is_circuit_open("printer", str(printer.id)):
            printer_polls_total.labels(mode="all", printer_type=printer.printer_type, result="skipped").inc()
            continue
        poll_targets.append(printer)

    printer_map = {p.ip_address: p for p in poll_targets}
    try:
        poll_results = await asyncio.to_thread(_do_poll_all, poll_targets) if poll_targets else {}

        # Phase 1: apply poll results, collect online MACs and offline printers
        online_macs: dict[str, str] = {}
        offline_with_mac: list[Printer] = []

        for ip, (result, current_mac) in poll_results.items():
            p = printer_map[ip]
            previous_online = bool(p.is_online)
            raw_online = bool(result and ((isinstance(result, dict) and result.get("is_online")) or (hasattr(result, "is_online") and result.is_online)))
            effective_online = await apply_poll_outcome(
                kind="printer",
                entity_id=str(p.id),
                previous_effective_online=previous_online,
                probed_online=raw_online,
                probed_error=result is None,
            )
            if result is None:
                p.is_online = effective_online
                p.status = "error" if not effective_online else (p.status or "online")
                p.mac_status = "unavailable"
                printer_polls_total.labels(
                    mode="all",
                    printer_type=p.printer_type,
                    result="error" if not effective_online else "offline_pending",
                ).inc()
                if (not effective_online) and p.mac_address:
                    offline_with_mac.append(p)
            elif isinstance(result, dict):
                p.is_online = effective_online
                p.status = "online" if effective_online else "offline"
                p.mac_status = None
                printer_polls_total.labels(
                    mode="all",
                    printer_type=p.printer_type,
                    result="online" if effective_online else "offline",
                ).inc()
                if (not effective_online) and p.mac_address:
                    offline_with_mac.append(p)
            else:
                p.is_online = effective_online
                if effective_online:
                    p.status = result.status
                    p.toner_black = result.toner_black
                    p.toner_cyan = result.toner_cyan
                    p.toner_magenta = result.toner_magenta
                    p.toner_yellow = result.toner_yellow
                else:
                    p.status = "offline"
                p.mac_status = _verify_mac(p, current_mac)
                printer_polls_total.labels(
                    mode="all",
                    printer_type=p.printer_type,
                    result="online" if effective_online else "offline",
                ).inc()
                if effective_online and current_mac:
                    online_macs[ip] = current_mac
                elif (not effective_online) and p.mac_address:
                    offline_with_mac.append(p)
            p.last_polled_at = datetime.now(UTC)
            session.add(p)

        # Phase 2: try to relocate offline printers by MAC
        if offline_with_mac:
            # Check scan cache for known MACs at new IPs
            for p in offline_with_mac:
                new_ip = await _find_by_mac_in_scan_cache(p.mac_address)
                if new_ip and new_ip != p.ip_address:
                    conflict = session.exec(
                        select(Printer).where(
                            Printer.ip_address == new_ip,
                            Printer.id != p.id,
                        )
                    ).first()
                    if not conflict:
                        old_ip = p.ip_address
                        p.ip_address = new_ip
                        # Re-poll at new IP
                        _, new_result, new_mac = await asyncio.to_thread(_poll_one, p)
                        if new_result and (isinstance(new_result, dict) and new_result.get("is_online") or hasattr(new_result, 'is_online') and new_result.is_online):
                            if not isinstance(new_result, dict):
                                p.is_online = True
                                p.status = new_result.status
                                p.toner_black = new_result.toner_black
                                p.toner_cyan = new_result.toner_cyan
                                p.toner_magenta = new_result.toner_magenta
                                p.toner_yellow = new_result.toner_yellow
                            else:
                                p.is_online = new_result["is_online"]
                                p.status = "online"
                            p.mac_status = _verify_mac(p, new_mac)
                            logger.info(
                                "Auto-relocated %s: %s -> %s (MAC %s)",
                                p.store_name, old_ip, new_ip, p.mac_address,
                            )
                        else:
                            p.ip_address = old_ip
                        session.add(p)

        session.commit()
        # Re-fetch all printers (including USB) for the response
        result_printers = session.exec(select(Printer).where(Printer.printer_type == printer_type)).all()
        set_device_counts(
            kind="printer",
            total=len(result_printers),
            online=sum(1 for p in result_printers if p.is_online),
        )

        await _invalidate_printer_cache()
        return PrintersPublic(data=result_printers, count=len(result_printers))
    finally:
        if lock_acquired:
            try:
                r = await get_redis()
                await r.delete(lock_key)
            except Exception:
                pass
