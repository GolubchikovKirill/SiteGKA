import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import NetworkSwitch
from app.observability.metrics import set_device_counts, switch_ops_total
from app.schemas import (
    AccessPointInfo,
    Message,
    NetworkSwitchCreate,
    NetworkSwitchesPublic,
    NetworkSwitchPublic,
    NetworkSwitchUpdate,
)
from app.services.cisco_ssh import (
    get_access_points,
    get_switch_info,
    poe_cycle_ap,
    reboot_ap,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["switches"])


@router.get("/", response_model=NetworkSwitchesPublic)
def read_switches(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    name: str | None = None,
) -> NetworkSwitchesPublic:
    statement = select(NetworkSwitch)
    count_stmt = select(func.count()).select_from(NetworkSwitch)
    if name:
        statement = statement.where(NetworkSwitch.name.ilike(f"%{name}%"))
        count_stmt = count_stmt.where(NetworkSwitch.name.ilike(f"%{name}%"))
    count = session.exec(count_stmt).one()
    switches = session.exec(statement.offset(skip).limit(limit).order_by(NetworkSwitch.name)).all()
    set_device_counts(
        kind="switch",
        total=len(switches),
        online=sum(1 for s in switches if s.is_online),
    )
    return NetworkSwitchesPublic(data=switches, count=count)


@router.post("/", response_model=NetworkSwitchPublic, dependencies=[Depends(get_current_active_superuser)])
def create_switch(session: SessionDep, switch_in: NetworkSwitchCreate) -> NetworkSwitch:
    existing = session.exec(select(NetworkSwitch).where(NetworkSwitch.ip_address == switch_in.ip_address)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Switch with this IP already exists")
    switch = NetworkSwitch(**switch_in.model_dump())
    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


@router.get("/{switch_id}", response_model=NetworkSwitchPublic)
def read_switch(switch_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> NetworkSwitch:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    return switch


@router.patch("/{switch_id}", response_model=NetworkSwitchPublic, dependencies=[Depends(get_current_active_superuser)])
def update_switch(session: SessionDep, switch_id: uuid.UUID, switch_in: NetworkSwitchUpdate) -> NetworkSwitch:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    update_data = switch_in.model_dump(exclude_unset=True)
    if "ip_address" in update_data and update_data["ip_address"] is not None:
        existing = session.exec(
            select(NetworkSwitch).where(
                NetworkSwitch.ip_address == update_data["ip_address"],
                NetworkSwitch.id != switch_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Switch with this IP already exists")
    switch.updated_at = datetime.now(UTC)
    switch.sqlmodel_update(update_data)
    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


@router.delete("/{switch_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_switch(session: SessionDep, switch_id: uuid.UUID) -> Message:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    session.delete(switch)
    session.commit()
    return Message(message="Switch deleted")


@router.post("/{switch_id}/poll", response_model=NetworkSwitchPublic)
async def poll_switch(switch_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> NetworkSwitch:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")

    info = await asyncio.to_thread(
        get_switch_info,
        switch.ip_address,
        switch.ssh_username,
        switch.ssh_password,
        switch.enable_password,
        switch.ssh_port,
    )

    switch.is_online = info.is_online
    switch_ops_total.labels(operation="poll", result="online" if info.is_online else "offline").inc()
    switch.hostname = info.hostname or switch.hostname
    switch.model_info = info.model_info or switch.model_info
    switch.ios_version = info.ios_version or switch.ios_version
    switch.uptime = info.uptime or switch.uptime
    switch.last_polled_at = datetime.now(UTC)
    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


@router.get("/{switch_id}/access-points", response_model=list[AccessPointInfo])
async def get_switch_aps(
    switch_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[AccessPointInfo]:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")

    aps = await asyncio.to_thread(
        get_access_points,
        switch.ip_address,
        switch.ssh_username,
        switch.ssh_password,
        switch.enable_password,
        switch.ssh_port,
        switch.ap_vlan,
    )
    switch_ops_total.labels(operation="access_points", result="success").inc()

    return [
        AccessPointInfo(
            mac_address=ap.mac_address,
            port=ap.port,
            vlan=ap.vlan,
            ip_address=ap.ip_address,
            cdp_name=ap.cdp_name,
            cdp_platform=ap.cdp_platform,
            poe_power=ap.poe_power,
            poe_status=ap.poe_status,
        )
        for ap in aps
    ]


@router.post("/{switch_id}/reboot-ap")
async def reboot_access_point(
    switch_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    interface: str = Body(embed=True),
    method: str = Body(default="poe", embed=True),
) -> dict:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")

    if method == "poe":
        ok = await asyncio.to_thread(
            poe_cycle_ap,
            switch.ip_address, switch.ssh_username, switch.ssh_password,
            switch.enable_password, switch.ssh_port, interface,
        )
    else:
        ok = await asyncio.to_thread(
            reboot_ap,
            switch.ip_address, switch.ssh_username, switch.ssh_password,
            switch.enable_password, switch.ssh_port, interface,
        )

    if not ok:
        switch_ops_total.labels(operation="reboot_ap", result="error").inc()
        raise HTTPException(status_code=502, detail="Failed to reboot AP")
    switch_ops_total.labels(operation="reboot_ap", result="success").inc()
    return {"status": "rebooting", "interface": interface, "method": method}
