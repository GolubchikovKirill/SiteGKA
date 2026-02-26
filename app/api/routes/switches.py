import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import NetworkSwitch
from app.observability.metrics import (
    set_device_counts,
    switch_ops_total,
    switch_port_op_duration_seconds,
    switch_port_ops_total,
)
from app.schemas import (
    AccessPointInfo,
    Message,
    NetworkSwitchCreate,
    NetworkSwitchesPublic,
    NetworkSwitchPublic,
    NetworkSwitchUpdate,
    SwitchPortAdminStateUpdate,
    SwitchPortDescriptionUpdate,
    SwitchPortInfo,
    SwitchPortPoeUpdate,
    SwitchPortsPublic,
    SwitchPortVlanUpdate,
)
from app.services.cisco_ssh import get_access_points, poe_cycle_ap, reboot_ap
from app.services.switches import resolve_switch_provider

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

    provider = resolve_switch_provider(switch)
    info = await asyncio.to_thread(provider.poll_switch, switch)

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
    if switch.vendor != "cisco":
        raise HTTPException(status_code=400, detail="Access point discovery is available for Cisco switches")

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
    payload: dict,
) -> dict:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    if switch.vendor != "cisco":
        raise HTTPException(status_code=400, detail="AP reboot is available for Cisco switches")

    interface = str(payload.get("interface", "")).strip()
    method = str(payload.get("method", "poe")).strip().lower()
    if not interface:
        raise HTTPException(status_code=422, detail="interface is required")
    if method not in {"poe", "shutdown"}:
        raise HTTPException(status_code=422, detail="method must be 'poe' or 'shutdown'")

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


@router.get("/{switch_id}/ports", response_model=SwitchPortsPublic)
async def get_switch_ports(
    switch_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    q: str | None = Query(default=None),
) -> SwitchPortsPublic:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    provider = resolve_switch_provider(switch)
    operation = "get_ports"
    vendor = switch.vendor
    with switch_port_op_duration_seconds.labels(vendor=vendor, operation=operation).time():
        try:
            ports = await asyncio.to_thread(provider.get_ports, switch)
            switch_port_ops_total.labels(vendor=vendor, operation=operation, result="success").inc()
        except Exception as exc:
            switch_port_ops_total.labels(vendor=vendor, operation=operation, result="error").inc()
            raise HTTPException(status_code=502, detail=f"Failed to fetch switch ports: {exc}") from exc
    if q:
        q_l = q.lower()
        ports = [p for p in ports if q_l in p.port.lower() or (p.description and q_l in p.description.lower())]
    window = ports[skip : skip + limit]
    data = [
        SwitchPortInfo(
            port=p.port,
            if_index=p.if_index,
            description=p.description,
            admin_status=p.admin_status,
            oper_status=p.oper_status,
            speed_mbps=p.speed_mbps,
            duplex=p.duplex,
            vlan=p.vlan,
            poe_enabled=p.poe_enabled,
            poe_power_w=p.poe_power_w,
            mac_count=p.mac_count,
        )
        for p in window
    ]
    return SwitchPortsPublic(data=data, count=len(ports))


def _require_superuser(current_user: CurrentUser) -> None:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can perform write operations")


async def _run_port_write(
    *,
    session: SessionDep,
    switch_id: uuid.UUID,
    current_user: CurrentUser,
    operation: str,
    port: str,
    callback,
) -> Message:
    _require_superuser(current_user)
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    provider = resolve_switch_provider(switch)
    vendor = switch.vendor
    with switch_port_op_duration_seconds.labels(vendor=vendor, operation=operation).time():
        try:
            await asyncio.to_thread(callback, switch, provider, port)
            switch_port_ops_total.labels(vendor=vendor, operation=operation, result="success").inc()
        except Exception as exc:
            switch_port_ops_total.labels(vendor=vendor, operation=operation, result="error").inc()
            raise HTTPException(status_code=502, detail=f"Port operation failed: {exc}") from exc
    return Message(message="ok")


@router.post("/{switch_id}/ports/{port:path}/admin-state", response_model=Message)
async def set_port_admin_state(
    switch_id: uuid.UUID,
    port: str,
    body: SwitchPortAdminStateUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    return await _run_port_write(
        session=session,
        switch_id=switch_id,
        current_user=current_user,
        operation="admin_state",
        port=port,
        callback=lambda sw, provider, p: provider.set_admin_state(sw, p, body.admin_state),
    )


@router.post("/{switch_id}/ports/{port:path}/description", response_model=Message)
async def set_port_description(
    switch_id: uuid.UUID,
    port: str,
    body: SwitchPortDescriptionUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    return await _run_port_write(
        session=session,
        switch_id=switch_id,
        current_user=current_user,
        operation="description",
        port=port,
        callback=lambda sw, provider, p: provider.set_description(sw, p, body.description),
    )


@router.post("/{switch_id}/ports/{port:path}/vlan", response_model=Message)
async def set_port_vlan(
    switch_id: uuid.UUID,
    port: str,
    body: SwitchPortVlanUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    return await _run_port_write(
        session=session,
        switch_id=switch_id,
        current_user=current_user,
        operation="vlan",
        port=port,
        callback=lambda sw, provider, p: provider.set_vlan(sw, p, body.vlan),
    )


@router.post("/{switch_id}/ports/{port:path}/poe", response_model=Message)
async def set_port_poe(
    switch_id: uuid.UUID,
    port: str,
    body: SwitchPortPoeUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    return await _run_port_write(
        session=session,
        switch_id=switch_id,
        current_user=current_user,
        operation="poe",
        port=port,
        callback=lambda sw, provider, p: provider.set_poe(sw, p, body.action),
    )
