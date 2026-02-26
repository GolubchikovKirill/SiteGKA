from fastapi import APIRouter, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import EventLog
from app.schemas import EventLogsPublic

router = APIRouter(tags=["logs"])


@router.get("/", response_model=EventLogsPublic)
def read_logs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=300),
    severity: str | None = Query(default=None),
    device_kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> EventLogsPublic:
    del current_user
    statement = select(EventLog)
    count_stmt = select(func.count()).select_from(EventLog)

    if severity:
        statement = statement.where(EventLog.severity == severity.lower())
        count_stmt = count_stmt.where(EventLog.severity == severity.lower())
    if device_kind:
        statement = statement.where(EventLog.device_kind == device_kind.lower())
        count_stmt = count_stmt.where(EventLog.device_kind == device_kind.lower())
    if q:
        pattern = f"%{q}%"
        statement = statement.where(
            (EventLog.message.ilike(pattern))
            | (EventLog.device_name.ilike(pattern))
            | (EventLog.ip_address.ilike(pattern))
            | (EventLog.event_type.ilike(pattern))
        )
        count_stmt = count_stmt.where(
            (EventLog.message.ilike(pattern))
            | (EventLog.device_name.ilike(pattern))
            | (EventLog.ip_address.ilike(pattern))
            | (EventLog.event_type.ilike(pattern))
        )

    count = session.exec(count_stmt).one()
    logs = session.exec(statement.order_by(EventLog.created_at.desc()).offset(skip).limit(limit)).all()
    return EventLogsPublic(data=logs, count=count)
