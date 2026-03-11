from __future__ import annotations

import uuid

from app.api.routes import cash_registers as cash_routes
from app.api.routes import media_players as media_routes
from app.api.routes import printers as printer_routes
from app.api.routes import switches as switch_routes
from app.api.routes.cash_registers import poll_cash_register as poll_cash_register_route
from app.api.routes.switches import poll_switch as poll_switch_route
from app.api.deps import SessionDep
from app.schemas import (
    CashRegisterPublic,
    CashRegistersPublic,
    MediaPlayersPublic,
    Message,
    NetworkSwitchPublic,
    PrintersPublic,
)


async def poll_all_printers_local(*, session: SessionDep, printer_type: str = "laser") -> PrintersPublic:
    return await printer_routes.poll_all_printers(session=session, current_user=None, printer_type=printer_type)


async def poll_all_media_players_local(
    *,
    session: SessionDep,
    device_type: str | None = None,
) -> MediaPlayersPublic:
    return await media_routes.poll_all_players(session=session, current_user=None, device_type=device_type)


async def poll_all_switches_local(*, session: SessionDep) -> Message:
    return await switch_routes.poll_all_switches(session=session, current_user=None)


async def poll_switch_local(*, session: SessionDep, switch_id: uuid.UUID) -> NetworkSwitchPublic:
    switch = await poll_switch_route(switch_id=switch_id, session=session, current_user=None)
    return NetworkSwitchPublic.model_validate(switch)


async def poll_all_cash_registers_local(*, session: SessionDep) -> CashRegistersPublic:
    return await cash_routes.poll_all_cash_registers(session=session, current_user=None)


async def poll_cash_register_local(*, session: SessionDep, cash_id: uuid.UUID) -> CashRegisterPublic:
    item = await poll_cash_register_route(cash_id=cash_id, session=session, current_user=None)
    return CashRegisterPublic.model_validate(item)
