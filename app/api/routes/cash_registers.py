import asyncio
import csv
import socket
import uuid
from datetime import UTC, datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.models import CashRegister
from app.schemas import (
    CashRegisterCreate,
    CashRegisterPublic,
    CashRegistersPublic,
    CashRegisterUpdate,
    Message,
)
from app.services.event_log import write_event_log
from app.services.internal_services import _proxy_request
from app.services.ping import check_port

router = APIRouter(tags=["cash-registers"])


def _probe_register(hostname: str) -> tuple[bool, str | None]:
    # Resolve first so obvious DNS issues are treated as offline fast.
    try:
        socket.gethostbyname(hostname)
    except OSError:
        return False, "dns_unresolved"
    # Try common Windows service ports.
    if check_port(hostname, port=3389, timeout=1.5) or check_port(hostname, port=445, timeout=1.5):
        return True, None
    return False, "port_closed"


def _offline_reason_ru(reason: str | None) -> str:
    if reason == "dns_unresolved":
        return "hostname не резолвится"
    if reason == "port_closed":
        return "сетевые порты недоступны"
    return "хост недоступен"


def _record_status_change(session, reg: CashRegister, prev_online: bool | None) -> None:
    if prev_online == reg.is_online:
        return
    if reg.is_online:
        write_event_log(
            session,
            event_type="cash_register_online",
            category="availability",
            severity="info",
            device_kind="cash_register",
            device_name=f"ККМ №{reg.kkm_number}",
            ip_address=reg.hostname,
            message=f"Касса ККМ №{reg.kkm_number} снова online ({reg.hostname})",
        )
        return
    reason = _offline_reason_ru(reg.reachability_reason)
    write_event_log(
        session,
        event_type="cash_register_offline",
        category="availability",
        severity="warning",
        device_kind="cash_register",
        device_name=f"ККМ №{reg.kkm_number}",
        ip_address=reg.hostname,
        message=f"Касса ККМ №{reg.kkm_number} offline ({reason})",
    )


@router.get("/", response_model=CashRegistersPublic)
def read_cash_registers(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    q: str | None = Query(default=None),
) -> CashRegistersPublic:
    del current_user
    statement = select(CashRegister)
    count_stmt = select(func.count()).select_from(CashRegister)
    if q:
        pattern = f"%{q}%"
        flt = (
            CashRegister.kkm_number.ilike(pattern)
            | CashRegister.hostname.ilike(pattern)
            | CashRegister.store_code.ilike(pattern)
            | CashRegister.serial_number.ilike(pattern)
            | CashRegister.inventory_number.ilike(pattern)
        )
        statement = statement.where(flt)
        count_stmt = count_stmt.where(flt)
    count = session.exec(count_stmt).one()
    rows = session.exec(statement.order_by(CashRegister.kkm_number).offset(skip).limit(limit)).all()
    return CashRegistersPublic(data=rows, count=count)


@router.post("/", response_model=CashRegisterPublic, dependencies=[Depends(get_current_active_superuser)])
def create_cash_register(session: SessionDep, payload: CashRegisterCreate) -> CashRegister:
    cash = CashRegister(**payload.model_dump())
    session.add(cash)
    session.commit()
    session.refresh(cash)
    return cash


@router.patch("/{cash_id}", response_model=CashRegisterPublic, dependencies=[Depends(get_current_active_superuser)])
def update_cash_register(session: SessionDep, cash_id: uuid.UUID, payload: CashRegisterUpdate) -> CashRegister:
    cash = session.get(CashRegister, cash_id)
    if not cash:
        raise HTTPException(status_code=404, detail="Cash register not found")
    cash.sqlmodel_update(payload.model_dump(exclude_unset=True))
    cash.updated_at = datetime.now(UTC)
    session.add(cash)
    session.commit()
    session.refresh(cash)
    return cash


@router.delete("/{cash_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_cash_register(session: SessionDep, cash_id: uuid.UUID) -> Message:
    cash = session.get(CashRegister, cash_id)
    if not cash:
        raise HTTPException(status_code=404, detail="Cash register not found")
    session.delete(cash)
    session.commit()
    return Message(message="Cash register deleted")


@router.post("/{cash_id}/poll", response_model=CashRegisterPublic)
async def poll_cash_register(
    cash_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> CashRegister | CashRegisterPublic:
    del current_user
    if settings.POLLING_SERVICE_ENABLED:
        payload = await _proxy_request(
            base_url=settings.POLLING_SERVICE_URL,
            method="POST",
            path=f"/poll/cash-registers/{cash_id}",
        )
        return CashRegisterPublic.model_validate(payload)

    cash = session.get(CashRegister, cash_id)
    if not cash:
        raise HTTPException(status_code=404, detail="Cash register not found")
    prev_online = cash.is_online
    is_online, reason = await asyncio.to_thread(_probe_register, cash.hostname)
    cash.is_online = is_online
    cash.reachability_reason = reason
    cash.last_polled_at = datetime.now(UTC)
    _record_status_change(session, cash, prev_online)
    session.add(cash)
    session.commit()
    session.refresh(cash)
    return cash


@router.post("/poll-all", response_model=CashRegistersPublic)
async def poll_all_cash_registers(session: SessionDep, current_user: CurrentUser) -> CashRegistersPublic:
    del current_user
    if settings.POLLING_SERVICE_ENABLED:
        payload = await _proxy_request(
            base_url=settings.POLLING_SERVICE_URL,
            method="POST",
            path="/poll/cash-registers",
        )
        return CashRegistersPublic.model_validate(payload)

    rows = session.exec(select(CashRegister)).all()
    for row in rows:
        prev_online = row.is_online
        is_online, reason = await asyncio.to_thread(_probe_register, row.hostname)
        row.is_online = is_online
        row.reachability_reason = reason
        row.last_polled_at = datetime.now(UTC)
        _record_status_change(session, row, prev_online)
        session.add(row)
    session.commit()
    result = session.exec(select(CashRegister).order_by(CashRegister.kkm_number)).all()
    return CashRegistersPublic(data=result, count=len(result))


@router.get("/export")
def export_cash_registers_csv(
    session: SessionDep,
    current_user: CurrentUser,
    q: str | None = Query(default=None),
) -> Response:
    del current_user
    statement = select(CashRegister).order_by(CashRegister.kkm_number)
    if q:
        pattern = f"%{q}%"
        statement = statement.where(
            CashRegister.kkm_number.ilike(pattern)
            | CashRegister.hostname.ilike(pattern)
            | CashRegister.store_code.ilike(pattern)
            | CashRegister.serial_number.ilike(pattern)
            | CashRegister.inventory_number.ilike(pattern)
        )
    rows = session.exec(statement).all()

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "№ ККМ",
            "Код ТТ",
            "Серийный номер",
            "Инвентаризационный №",
            "ID терминала РС",
            "ID терминала Сбер",
            "Версия Windows",
            "Тип ККМ",
            "Номер кассы",
            "Hostname",
            "Комментарий",
            "Online",
            "Причина оффлайна",
            "Последний опрос",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.kkm_number,
                row.store_code or "",
                row.serial_number or "",
                row.inventory_number or "",
                row.terminal_id_rs or "",
                row.terminal_id_sber or "",
                row.windows_version or "",
                "РИТЕЙЛ" if row.kkm_type == "retail" else "ШТРИХ",
                row.cash_number or "",
                row.hostname,
                row.comment or "",
                "online" if row.is_online else "offline",
                _offline_reason_ru(row.reachability_reason) if row.is_online is False else "",
                row.last_polled_at.isoformat() if row.last_polled_at else "",
            ]
        )

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cash-registers.csv"'},
    )
