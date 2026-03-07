import uuid
import asyncio
import socket
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.models import Computer
from app.schemas import ComputerCreate, ComputerPublic, ComputersPublic, ComputerUpdate, Message
from app.services.smart_search import build_ilike_filter

router = APIRouter(tags=["computers"])

_COMPUTER_PROBE_PORTS = (445, 3389, 135)


def _resolve_hostname(hostname: str) -> str | None:
    if not hostname:
        return None
    value = hostname.strip()
    if not value:
        return None
    candidates = [value]
    if "." not in value:
        suffixes = [s.strip() for s in settings.DNS_SEARCH_SUFFIXES.split(",") if s.strip()]
        candidates.extend([f"{value}.{suffix}" for suffix in suffixes])

    for candidate in candidates:
        try:
            return socket.gethostbyname(candidate)
        except OSError:
            continue
    return None


def _probe_computer(hostname: str) -> tuple[bool, str | None]:
    resolved_ip = _resolve_hostname(hostname)
    if not resolved_ip:
        return False, "dns_unresolved"
    for port in _COMPUTER_PROBE_PORTS:
        try:
            with socket.create_connection((resolved_ip, port), timeout=1.2):
                return True, None
        except OSError:
            continue
    return False, "port_closed"


@router.get("/", response_model=ComputersPublic)
def read_computers(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    q: str | None = Query(default=None),
) -> ComputersPublic:
    statement = select(Computer)
    count_stmt = select(func.count()).select_from(Computer)
    if q:
        flt = build_ilike_filter(
            [Computer.hostname, Computer.location, Computer.comment],
            q,
        )
        if flt is not None:
            statement = statement.where(flt)
            count_stmt = count_stmt.where(flt)
    rows = session.exec(statement.order_by(Computer.hostname).offset(skip).limit(limit)).all()
    count = session.exec(count_stmt).one()
    return ComputersPublic(data=rows, count=count)


@router.post("/", response_model=ComputerPublic, dependencies=[Depends(get_current_active_superuser)])
def create_computer(session: SessionDep, payload: ComputerCreate) -> Computer:
    exists = session.exec(select(Computer).where(Computer.hostname == payload.hostname)).first()
    if exists:
        raise HTTPException(status_code=409, detail="Computer with this hostname already exists")
    row = Computer(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.patch("/{computer_id}", response_model=ComputerPublic, dependencies=[Depends(get_current_active_superuser)])
def update_computer(session: SessionDep, computer_id: uuid.UUID, payload: ComputerUpdate) -> Computer:
    row = session.get(Computer, computer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Computer not found")
    updates = payload.model_dump(exclude_unset=True)
    new_hostname = updates.get("hostname")
    if new_hostname and new_hostname != row.hostname:
        conflict = session.exec(
            select(Computer).where(Computer.hostname == new_hostname, Computer.id != computer_id)
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Computer with this hostname already exists")
    row.sqlmodel_update(updates)
    row.updated_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{computer_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_computer(session: SessionDep, computer_id: uuid.UUID) -> Message:
    row = session.get(Computer, computer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Computer not found")
    session.delete(row)
    session.commit()
    return Message(message="Computer deleted")


@router.post("/{computer_id}/poll", response_model=ComputerPublic)
async def poll_computer(computer_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Computer:
    del current_user
    row = session.get(Computer, computer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Computer not found")
    is_online, reason = await asyncio.to_thread(_probe_computer, row.hostname)
    row.is_online = is_online
    row.reachability_reason = reason
    row.last_polled_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.post("/poll-all", response_model=ComputersPublic)
async def poll_all_computers(session: SessionDep, current_user: CurrentUser) -> ComputersPublic:
    del current_user
    rows = session.exec(select(Computer)).all()
    for row in rows:
        is_online, reason = await asyncio.to_thread(_probe_computer, row.hostname)
        row.is_online = is_online
        row.reachability_reason = reason
        row.last_polled_at = datetime.now(UTC)
        session.add(row)
    session.commit()
    return ComputersPublic(data=rows, count=len(rows))
