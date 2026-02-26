import asyncio
import logging
import uuid
from datetime import UTC, datetime
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.redis import get_redis
from app.models import NetworkSwitch
from app.observability.metrics import (
    network_bulk_operation_duration_seconds,
    network_bulk_processed_total,
    set_device_counts,
    switch_ops_total,
    switch_port_op_duration_seconds,
    switch_port_ops_total,
)
from app.schemas import (
    AccessPointInfo,
    DiscoveryResults,
    Message,
    NetworkSwitchCreate,
    NetworkSwitchesPublic,
    NetworkSwitchPublic,
    NetworkSwitchUpdate,
    ScanProgress,
    ScanRequest,
    SwitchPortAdminStateUpdate,
    SwitchPortDescriptionUpdate,
    SwitchPortInfo,
    SwitchPortModeUpdate,
    SwitchPortPoeUpdate,
    SwitchPortsPublic,
    SwitchPortVlanUpdate,
)
from app.services.cisco_ssh import get_access_points, poe_cycle_ap, reboot_ap
from app.services.discovery import get_discovery_progress, get_discovery_results, run_discovery_scan
from app.services.event_log import write_event_log
from app.services.poll_resilience import apply_poll_outcome, is_circuit_open, poll_jitter_async
from app.services.switches import resolve_switch_provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["switches"])


def _record_status_change(session: SessionDep, sw: NetworkSwitch, was_online: bool | None) -> None:
    if was_online is None or was_online == sw.is_online:
        return
    write_event_log(
        session,
        category="device",
        event_type="device_online" if sw.is_online else "device_offline",
        severity="info" if sw.is_online else "warning",
        device_kind="switch",
        device_name=sw.name,
        ip_address=sw.ip_address,
        message=f"Network device '{sw.name}' is now {'online' if sw.is_online else 'offline'}",
    )


async def _run_switch_discovery(subnet: str, ports: str, known_switches: list[dict]) -> None:
    try:
        await run_discovery_scan("switch", subnet, ports, known_switches)
    except Exception as exc:
        logger.error("Switch discovery failed: %s", exc)


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


@router.post("/discover/scan", response_model=ScanProgress, dependencies=[Depends(get_current_active_superuser)])
async def discover_switch_scan(body: ScanRequest, session: SessionDep) -> dict:
    switches = session.exec(select(NetworkSwitch)).all()
    known = [{"id": str(s.id), "ip_address": s.ip_address, "mac_address": None} for s in switches]
    asyncio.create_task(_run_switch_discovery(body.subnet, body.ports, known))
    return {"status": "running", "scanned": 0, "total": 0, "found": 0, "message": None}


@router.get("/discover/status", response_model=ScanProgress)
async def discover_switch_status(current_user: CurrentUser) -> dict:
    del current_user
    return await get_discovery_progress("switch")


@router.get("/discover/results", response_model=DiscoveryResults)
async def discover_switch_results(current_user: CurrentUser) -> dict:
    del current_user
    progress = await get_discovery_progress("switch")
    devices = await get_discovery_results("switch")
    return {"progress": progress, "devices": devices}


@router.post("/discover/add", response_model=NetworkSwitchPublic, dependencies=[Depends(get_current_active_superuser)])
def discover_add_switch(session: SessionDep, payload: dict) -> NetworkSwitch:
    ip = str(payload.get("ip_address", "")).strip()
    if not ip:
        raise HTTPException(status_code=422, detail="ip_address is required")
    existing = session.exec(select(NetworkSwitch).where(NetworkSwitch.ip_address == ip)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Switch with this IP already exists")
    vendor = str(payload.get("vendor") or "generic").strip().lower()
    if vendor not in {"cisco", "dlink", "generic"}:
        vendor = "generic"
    name = str(payload.get("name") or payload.get("hostname") or f"Switch {ip}")[:255]
    switch = NetworkSwitch(
        name=name,
        ip_address=ip,
        vendor=vendor,
        management_protocol="snmp+ssh",
        snmp_version="2c",
        snmp_community_ro="public",
    )
    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


@router.post(
    "/discover/update-ip/{switch_id}",
    response_model=NetworkSwitchPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def discover_update_switch_ip(
    switch_id: uuid.UUID,
    session: SessionDep,
    new_ip: str = "",
) -> NetworkSwitch:
    switch = session.get(NetworkSwitch, switch_id)
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    old_ip = switch.ip_address
    if new_ip:
        conflict = session.exec(
            select(NetworkSwitch).where(NetworkSwitch.ip_address == new_ip, NetworkSwitch.id != switch.id)
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Another switch already has this IP")
        switch.ip_address = new_ip
        if old_ip != new_ip:
            write_event_log(
                session,
                category="network",
                event_type="ip_changed",
                severity="warning",
                device_kind="switch",
                device_name=switch.name,
                ip_address=new_ip,
                message=f"Switch '{switch.name}' moved IP: {old_ip} -> {new_ip}",
            )
    switch.updated_at = datetime.now(UTC)
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

    was_online = switch.is_online
    provider = resolve_switch_provider(switch)
    info = await asyncio.to_thread(provider.poll_switch, switch)

    switch.is_online = info.is_online
    switch_ops_total.labels(operation="poll", result="online" if info.is_online else "offline").inc()
    switch.hostname = info.hostname or switch.hostname
    switch.model_info = info.model_info or switch.model_info
    switch.ios_version = info.ios_version or switch.ios_version
    switch.uptime = info.uptime or switch.uptime
    switch.last_polled_at = datetime.now(UTC)
    _record_status_change(session, switch, was_online)
    session.add(switch)
    session.commit()
    session.refresh(switch)
    return switch


@router.post("/poll-all", response_model=Message)
async def poll_all_switches(
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    del current_user
    started = perf_counter()
    lock_key = "lock:poll-all:switches"
    lock_acquired = True
    try:
        r = await get_redis()
        lock_acquired = bool(await r.set(lock_key, "1", ex=45, nx=True))
    except Exception:
        lock_acquired = True
    if not lock_acquired:
        logger.info("Skipping duplicate poll-all request for switches: lock busy")
        return Message(message="Switch poll already in progress")
    switches = session.exec(select(NetworkSwitch)).all()
    error_count = 0

    semaphore = asyncio.Semaphore(12)

    async def _poll_one(sw: NetworkSwitch) -> tuple[NetworkSwitch, object | None, Exception | None]:
        try:
            async with semaphore:
                await poll_jitter_async()
                provider = resolve_switch_provider(sw)
                info = await asyncio.to_thread(provider.poll_switch, sw)
                return sw, info, None
        except Exception as exc:  # pragma: no cover - defensive
            return sw, None, exc

    try:
        poll_targets: list[NetworkSwitch] = []
        for sw in switches:
            if await is_circuit_open("switch", str(sw.id)):
                switch_ops_total.labels(operation="poll_all", result="skipped").inc()
                continue
            poll_targets.append(sw)

        results = await asyncio.gather(*[_poll_one(sw) for sw in poll_targets]) if poll_targets else []
        for switch, info, exc in results:
            try:
                was_online = switch.is_online
                if exc:
                    raise exc
                if info is None:
                    raise RuntimeError("poll returned no data")
                effective_online = await apply_poll_outcome(
                    kind="switch",
                    entity_id=str(switch.id),
                    previous_effective_online=bool(switch.is_online),
                    probed_online=bool(info.is_online),
                    probed_error=False,
                )
                switch.is_online = effective_online
                switch.hostname = info.hostname or switch.hostname
                switch.model_info = info.model_info or switch.model_info
                switch.ios_version = info.ios_version or switch.ios_version
                switch.uptime = info.uptime or switch.uptime
                switch.last_polled_at = datetime.now(UTC)
                _record_status_change(session, switch, was_online)
                switch_ops_total.labels(operation="poll_all", result="online" if effective_online else "offline").inc()
                session.add(switch)
            except Exception as exc:
                logger.warning("Bulk switch poll failed for %s (%s): %s", switch.name, switch.ip_address, exc)
                write_event_log(
                    session,
                    category="system",
                    event_type="critical_poll_error",
                    severity="critical",
                    device_kind="switch",
                    device_name=switch.name,
                    ip_address=switch.ip_address,
                    message=f"Critical switch poll error for '{switch.name}': {exc}",
                )
                switch.is_online = await apply_poll_outcome(
                    kind="switch",
                    entity_id=str(switch.id),
                    previous_effective_online=bool(switch.is_online),
                    probed_online=False,
                    probed_error=True,
                )
                switch.last_polled_at = datetime.now(UTC)
                session.add(switch)
                switch_ops_total.labels(operation="poll_all", result="error").inc()
                error_count += 1
        session.commit()
        network_bulk_processed_total.labels(operation="switch_poll_all", result="success").inc(max(len(switches) - error_count, 0))
        if error_count:
            network_bulk_processed_total.labels(operation="switch_poll_all", result="error").inc(error_count)
        network_bulk_operation_duration_seconds.labels(operation="switch_poll_all").observe(max(perf_counter() - started, 0))
        return Message(message="Switches polled")
    finally:
        if lock_acquired:
            try:
                r = await get_redis()
                await r.delete(lock_key)
            except Exception:
                pass


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
            status_text=p.status_text,
            vlan_text=p.vlan_text,
            duplex_text=p.duplex_text,
            speed_text=p.speed_text,
            media_type=p.media_type,
            speed_mbps=p.speed_mbps,
            duplex=p.duplex,
            vlan=p.vlan,
            port_mode=p.port_mode,
            access_vlan=p.access_vlan,
            trunk_native_vlan=p.trunk_native_vlan,
            trunk_allowed_vlans=p.trunk_allowed_vlans,
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


@router.post("/{switch_id}/ports/{port:path}/mode", response_model=Message)
async def set_port_mode(
    switch_id: uuid.UUID,
    port: str,
    body: SwitchPortModeUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    return await _run_port_write(
        session=session,
        switch_id=switch_id,
        current_user=current_user,
        operation="mode",
        port=port,
        callback=lambda sw, provider, p: provider.set_mode(
            sw,
            p,
            body.mode,
            access_vlan=body.access_vlan,
            native_vlan=body.native_vlan,
            allowed_vlans=body.allowed_vlans,
        ),
    )
