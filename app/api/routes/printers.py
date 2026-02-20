import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import Printer
from app.schemas import (
    Message,
    PrinterCreate,
    PrinterPublic,
    PrintersPublic,
    PrinterUpdate,
)
from app.services.snmp import poll_printer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["printers"])

MAX_POLL_WORKERS = 20


@router.get("/", response_model=PrintersPublic)
def read_printers(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, le=500),
    store_name: str | None = None,
) -> PrintersPublic:
    statement = select(Printer)
    count_stmt = select(func.count()).select_from(Printer)
    if store_name:
        statement = statement.where(Printer.store_name.ilike(f"%{store_name}%"))
        count_stmt = count_stmt.where(Printer.store_name.ilike(f"%{store_name}%"))
    count = session.exec(count_stmt).one()
    printers = session.exec(statement.offset(skip).limit(limit).order_by(Printer.store_name)).all()
    return PrintersPublic(data=printers, count=count)


@router.post("/", response_model=PrinterPublic, dependencies=[Depends(get_current_active_superuser)])
def create_printer(session: SessionDep, printer_in: PrinterCreate) -> Printer:
    existing = session.exec(select(Printer).where(Printer.ip_address == printer_in.ip_address)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Printer with this IP already exists")
    printer = Printer(**printer_in.model_dump())
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return printer


@router.get("/{printer_id}", response_model=PrinterPublic)
def read_printer(printer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Printer:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    return printer


@router.patch("/{printer_id}", response_model=PrinterPublic, dependencies=[Depends(get_current_active_superuser)])
def update_printer(session: SessionDep, printer_id: uuid.UUID, printer_in: PrinterUpdate) -> Printer:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    update_data = printer_in.model_dump(exclude_unset=True)
    if "ip_address" in update_data:
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
    return printer


@router.delete("/{printer_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_printer(session: SessionDep, printer_id: uuid.UUID) -> Message:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    session.delete(printer)
    session.commit()
    return Message(message="Printer deleted")


@router.post("/{printer_id}/poll", response_model=PrinterPublic)
def poll_single_printer(printer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Printer:
    """Poll a single printer via SNMP and update its cached status."""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    result = poll_printer(printer.ip_address, printer.snmp_community)
    printer.is_online = result.is_online
    printer.status = result.status
    printer.toner_black = result.toner_black
    printer.toner_cyan = result.toner_cyan
    printer.toner_magenta = result.toner_magenta
    printer.toner_yellow = result.toner_yellow
    printer.last_polled_at = datetime.now(UTC)
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return printer


@router.post("/poll-all", response_model=PrintersPublic)
def poll_all_printers(session: SessionDep, current_user: CurrentUser) -> PrintersPublic:
    """Poll all printers in parallel and update their cached status."""
    printers = session.exec(select(Printer)).all()
    if not printers:
        return PrintersPublic(data=[], count=0)

    printer_map = {p.ip_address: p for p in printers}

    with ThreadPoolExecutor(max_workers=min(MAX_POLL_WORKERS, len(printers))) as pool:
        futures = {pool.submit(poll_printer, p.ip_address, p.snmp_community): p.ip_address for p in printers}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                result = future.result()
            except Exception as e:
                logger.warning("SNMP poll failed for %s: %s", ip, e)
                result = None

            p = printer_map[ip]
            if result:
                p.is_online = result.is_online
                p.status = result.status
                p.toner_black = result.toner_black
                p.toner_cyan = result.toner_cyan
                p.toner_magenta = result.toner_magenta
                p.toner_yellow = result.toner_yellow
            else:
                p.is_online = False
                p.status = "error"
            p.last_polled_at = datetime.now(UTC)
            session.add(p)

    session.commit()
    for p in printers:
        session.refresh(p)

    return PrintersPublic(data=printers, count=len(printers))
