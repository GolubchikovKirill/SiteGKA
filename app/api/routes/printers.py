import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.domains.inventory.models import Printer
from app.domains.inventory.printer_polling import (
    PrinterNotFoundError,
    UnsupportedPrinterPollError,
    invalidate_printer_cache,
    poll_all_printers_local,
    poll_single_printer_local,
)
from app.domains.inventory.schemas import PrinterCreate, PrinterPublic, PrintersPublic, PrinterUpdate
from app.domains.shared.schemas import Message
from app.services.cache import get_cached_model, set_cached_model
from app.services.internal_services import _proxy_request
from app.services.smart_search import build_ilike_filter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["printers"])

CACHE_TTL = 30


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
    if cached := await get_cached_model(cache_key, PrintersPublic):
        return cached

    statement = select(Printer).where(Printer.printer_type == printer_type)
    count_stmt = select(func.count()).select_from(Printer).where(Printer.printer_type == printer_type)
    if store_name:
        flt = build_ilike_filter(
            [
                Printer.store_name,
                Printer.model,
                Printer.host_pc,
                Printer.ip_address,
                Printer.mac_address,
            ],
            store_name,
        )
        if flt is not None:
            statement = statement.where(flt)
            count_stmt = count_stmt.where(flt)
    count = session.exec(count_stmt).one()
    printers = session.exec(statement.offset(skip).limit(limit).order_by(Printer.store_name)).all()
    result = PrintersPublic(data=printers, count=count)

    await set_cached_model(cache_key, result, ttl=CACHE_TTL)

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
    await invalidate_printer_cache()
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
    await invalidate_printer_cache()
    return printer


@router.delete("/{printer_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_printer(session: SessionDep, printer_id: uuid.UUID) -> Message:
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    session.delete(printer)
    session.commit()
    await invalidate_printer_cache()
    return Message(message="Printer deleted")


# -- Poll endpoints ----------------------------------------------------------


@router.post("/{printer_id}/poll", response_model=PrinterPublic)
async def poll_single_printer(printer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Printer:
    del current_user
    try:
        return await poll_single_printer_local(session=session, printer_id=printer_id)
    except PrinterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Printer not found") from exc
    except UnsupportedPrinterPollError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/poll-all", response_model=PrintersPublic)
async def poll_all_printers(
    session: SessionDep,
    current_user: CurrentUser,
    printer_type: str = Query(default="laser"),
) -> PrintersPublic:
    del current_user
    if settings.POLLING_SERVICE_ENABLED:
        payload = await _proxy_request(
            base_url=settings.POLLING_SERVICE_URL,
            method="POST",
            path="/poll/printers",
            params={"printer_type": printer_type},
        )
        return PrintersPublic.model_validate(payload)

    return await poll_all_printers_local(session=session, printer_type=printer_type)
