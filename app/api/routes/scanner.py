import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.models import Printer
from app.schemas import (
    PrinterCreate,
    PrinterPublic,
    ScanProgress,
    ScanRequest,
    ScanResults,
)
from app.services.event_log import write_event_log
from app.services.internal_services import _proxy_request
from app.services.scanner import get_scan_progress, get_scan_results, scan_subnet

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scanner"])


async def _run_scan(subnet: str, ports: str, known_printers: list[dict]) -> None:
    try:
        await scan_subnet(subnet, ports, known_printers)
    except Exception as e:
        logger.error("Scan failed: %s", e)


@router.post(
    "/scan",
    response_model=ScanProgress,
    dependencies=[Depends(get_current_active_superuser)],
)
async def start_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> dict:
    """Start a network scan (runs in background)."""
    printers = session.exec(select(Printer)).all()
    known = [
        {
            "id": str(p.id),
            "ip_address": p.ip_address,
            "mac_address": p.mac_address,
            "store_name": p.store_name,
        }
        for p in printers
    ]
    if settings.DISCOVERY_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.DISCOVERY_SERVICE_URL,
            method="POST",
            path="/discover/printers/scan",
            json_body={
                "subnet": body.subnet,
                "ports": body.ports,
                "known_printers": known,
            },
        )
    background_tasks.add_task(_run_scan, body.subnet, body.ports, known)
    return {"status": "running", "scanned": 0, "total": 0, "found": 0, "message": None}


@router.get("/status", response_model=ScanProgress)
async def scan_status(current_user: CurrentUser) -> dict:
    """Get current scan progress."""
    if settings.DISCOVERY_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.DISCOVERY_SERVICE_URL,
            method="GET",
            path="/discover/printers/status",
        )
    return await get_scan_progress()


@router.get("/results", response_model=ScanResults)
async def scan_results(current_user: CurrentUser) -> dict:
    """Get results of the last scan."""
    if settings.DISCOVERY_SERVICE_ENABLED:
        payload = await _proxy_request(
            base_url=settings.DISCOVERY_SERVICE_URL,
            method="GET",
            path="/discover/printers/results",
        )
        return ScanResults.model_validate(payload).model_dump()
    progress = await get_scan_progress()
    devices = await get_scan_results()
    return {"progress": progress, "devices": devices}


@router.post(
    "/add",
    response_model=PrinterPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def add_discovered_printer(
    body: PrinterCreate,
    session: SessionDep,
) -> Printer:
    """Add a discovered device as a monitored printer."""
    existing = session.exec(select(Printer).where(Printer.ip_address == body.ip_address)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Printer with this IP already exists")
    printer = Printer(**body.model_dump())
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return printer


@router.post(
    "/update-ip/{printer_id}",
    response_model=PrinterPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_printer_ip(
    printer_id: str,
    session: SessionDep,
    new_ip: str = "",
    new_mac: str | None = None,
) -> Printer:
    """Update printer IP (when DHCP changed it)."""
    import uuid

    printer = session.get(Printer, uuid.UUID(printer_id))
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    old_ip = printer.ip_address
    if new_ip:
        conflict = session.exec(
            select(Printer).where(Printer.ip_address == new_ip, Printer.id != printer.id)
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Another printer already has this IP")
        printer.ip_address = new_ip
        if old_ip != new_ip:
            write_event_log(
                session,
                category="network",
                event_type="ip_changed",
                severity="warning",
                device_kind="printer",
                device_name=printer.store_name,
                ip_address=new_ip,
                message=f"Printer '{printer.store_name}' moved IP: {old_ip} -> {new_ip}",
            )
    if new_mac:
        printer.mac_address = new_mac
    printer.updated_at = datetime.now(UTC)
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return printer


@router.get("/settings")
async def get_scanner_settings(current_user: CurrentUser) -> dict:
    """Get default scanner settings."""
    return {
        "subnet": settings.SCAN_SUBNET,
        "ports": settings.SCAN_PORTS,
        "max_hosts": settings.SCAN_MAX_HOSTS,
        "tcp_timeout": settings.SCAN_TCP_TIMEOUT,
        "tcp_retries": settings.SCAN_TCP_RETRIES,
        "tcp_concurrency": settings.SCAN_TCP_CONCURRENCY,
    }
