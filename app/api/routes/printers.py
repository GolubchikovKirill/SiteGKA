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
from app.services.ping import check_port
from app.services.snmp import poll_printer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["printers"])

MAX_POLL_WORKERS = 20

# Cyrillic ↔ Latin lookalikes for smart search
_CYR_TO_LAT = str.maketrans("АВЕКМНОРСТХавекмнорстх", "ABEKMHOPCTXabekmhopctx")


def _normalize(text: str) -> str:
    return text.translate(_CYR_TO_LAT)


def _search_filter(column, query: str):
    """Build OR filter matching both original and normalized text."""
    normalized = _normalize(query)
    from sqlalchemy import or_, func as sa_func
    return or_(
        sa_func.translate(column, "АВЕКМНОРСТХаверкмнорстх", "ABEKMHOPCTXabekmhopctx").ilike(f"%{normalized}%"),
        column.ilike(f"%{query}%"),
    )


@router.get("/", response_model=PrintersPublic)
def read_printers(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, le=500),
    store_name: str | None = None,
    printer_type: str = Query(default="laser"),
) -> PrintersPublic:
    statement = select(Printer).where(Printer.printer_type == printer_type)
    count_stmt = select(func.count()).select_from(Printer).where(Printer.printer_type == printer_type)
    if store_name:
        flt = _search_filter(Printer.store_name, store_name)
        statement = statement.where(flt)
        count_stmt = count_stmt.where(flt)
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


def _poll_one(printer: Printer) -> tuple[str, object | None]:
    """Poll a single printer using the appropriate method for its type."""
    ip = printer.ip_address
    try:
        if printer.printer_type == "label":
            online = check_port(ip)
            return ip, {"is_online": online}
        else:
            return ip, poll_printer(ip, printer.snmp_community)
    except Exception as e:
        logger.warning("Poll failed for %s: %s", ip, e)
        return ip, None


@router.post("/{printer_id}/poll", response_model=PrinterPublic)
def poll_single_printer(printer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Printer:
    """Poll a single printer and update its cached status."""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    if printer.printer_type == "label":
        printer.is_online = check_port(printer.ip_address)
        printer.status = "online" if printer.is_online else "offline"
    else:
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
def poll_all_printers(
    session: SessionDep,
    current_user: CurrentUser,
    printer_type: str = Query(default="laser"),
) -> PrintersPublic:
    """Poll all printers of a given type in parallel."""
    printers = session.exec(select(Printer).where(Printer.printer_type == printer_type)).all()
    if not printers:
        return PrintersPublic(data=[], count=0)

    printer_map = {p.ip_address: p for p in printers}

    with ThreadPoolExecutor(max_workers=min(MAX_POLL_WORKERS, len(printers))) as pool:
        futures = {pool.submit(_poll_one, p): p.ip_address for p in printers}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                _, result = future.result()
            except Exception as e:
                logger.warning("Poll failed for %s: %s", ip, e)
                result = None

            p = printer_map[ip]
            if result is None:
                p.is_online = False
                p.status = "error"
            elif isinstance(result, dict):
                p.is_online = result["is_online"]
                p.status = "online" if p.is_online else "offline"
            else:
                p.is_online = result.is_online
                p.status = result.status
                p.toner_black = result.toner_black
                p.toner_cyan = result.toner_cyan
                p.toner_magenta = result.toner_magenta
                p.toner_yellow = result.toner_yellow
            p.last_polled_at = datetime.now(UTC)
            session.add(p)

    session.commit()
    for p in printers:
        session.refresh(p)

    return PrintersPublic(data=printers, count=len(printers))
