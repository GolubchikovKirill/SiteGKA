import asyncio
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.core.redis import get_redis
from app.models import MediaPlayer
from app.observability.metrics import (
    media_player_ops_total,
    media_player_polls_total,
    network_bulk_operation_duration_seconds,
    network_bulk_processed_total,
    set_device_counts,
)
from app.schemas import (
    DiscoveryResults,
    MediaPlayerCreate,
    MediaPlayerPublic,
    MediaPlayersPublic,
    MediaPlayerUpdate,
    Message,
    ScanProgress,
    ScanRequest,
)
from app.services.device_poll import find_device_by_mac, find_devices_by_macs, poll_device_sync
from app.services.discovery import get_discovery_progress, get_discovery_results, run_discovery_scan
from app.services.event_log import write_event_log
from app.services.iconbit import (
    delete_all_files as iconbit_delete_all,
)
from app.services.iconbit import (
    delete_file as iconbit_delete_file,
)
from app.services.iconbit import (
    get_status as iconbit_get_status,
)
from app.services.iconbit import (
    play as iconbit_play,
)
from app.services.iconbit import (
    play_file as iconbit_play_file,
)
from app.services.iconbit import (
    stop as iconbit_stop,
)
from app.services.iconbit import (
    upload_file as iconbit_upload_file,
)
from app.services.internal_services import _proxy_request
from app.services.ml_snapshots import write_media_player_snapshot
from app.services.ping import check_port as check_tcp_port
from app.services.poll_resilience import apply_poll_outcome, is_circuit_open, poll_jitter_sync

logger = logging.getLogger(__name__)

router = APIRouter(tags=["media-players"])

MAX_POLL_WORKERS = 20
CACHE_TTL = 30


def _record_status_change(session: SessionDep, player: MediaPlayer, was_online: bool | None) -> None:
    if was_online is None or was_online == player.is_online:
        return
    write_event_log(
        session,
        category="device",
        event_type="device_online" if player.is_online else "device_offline",
        severity="info" if player.is_online else "warning",
        device_kind="media_player",
        device_name=player.name,
        ip_address=player.ip_address,
        message=f"Media player '{player.name}' is now {'online' if player.is_online else 'offline'}",
    )


@dataclass
class _LightPollResult:
    is_online: bool
    hostname: str | None = None
    os_info: str | None = None
    uptime: str | None = None
    open_ports: list[int] | None = None
    mac_address: str | None = None


async def _run_iconbit_discovery(subnet: str, ports: str, known_players: list[dict]) -> None:
    try:
        await run_discovery_scan("iconbit", subnet, ports, known_players)
    except Exception as exc:
        logger.error("Iconbit discovery failed: %s", exc)


async def _invalidate_cache() -> None:
    try:
        r = await get_redis()
        keys = []
        async for key in r.scan_iter("media_players:*"):
            keys.append(key)
        if keys:
            await r.delete(*keys)
    except Exception as e:
        logger.warning("Media player cache invalidation failed: %s", e)


@router.get("/", response_model=MediaPlayersPublic)
async def read_media_players(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, le=500),
    name: str | None = None,
    device_type: str | None = None,
) -> MediaPlayersPublic:
    cache_key = f"media_players:{device_type or ''}:{name or ''}:{skip}:{limit}"
    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            return MediaPlayersPublic(**json.loads(cached))
    except Exception:
        pass

    statement = select(MediaPlayer)
    count_stmt = select(func.count()).select_from(MediaPlayer)

    if device_type:
        statement = statement.where(MediaPlayer.device_type == device_type)
        count_stmt = count_stmt.where(MediaPlayer.device_type == device_type)
    if name:
        statement = statement.where(MediaPlayer.name.ilike(f"%{name}%"))
        count_stmt = count_stmt.where(MediaPlayer.name.ilike(f"%{name}%"))

    count = session.exec(count_stmt).one()
    players = session.exec(statement.offset(skip).limit(limit).order_by(MediaPlayer.name)).all()
    result = MediaPlayersPublic(data=players, count=count)

    try:
        r = await get_redis()
        await r.setex(cache_key, CACHE_TTL, result.model_dump_json())
    except Exception:
        pass

    return result


@router.post("/", response_model=MediaPlayerPublic, dependencies=[Depends(get_current_active_superuser)])
async def create_media_player(session: SessionDep, player_in: MediaPlayerCreate) -> MediaPlayer:
    existing = session.exec(select(MediaPlayer).where(MediaPlayer.ip_address == player_in.ip_address)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device with this IP already exists")
    player = MediaPlayer(**player_in.model_dump())
    session.add(player)
    session.commit()
    session.refresh(player)
    await _invalidate_cache()
    return player


@router.post("/discover/scan", response_model=ScanProgress, dependencies=[Depends(get_current_active_superuser)])
async def discover_iconbit_scan(
    body: ScanRequest,
    session: SessionDep,
) -> dict:
    players = session.exec(select(MediaPlayer).where(MediaPlayer.device_type == "iconbit")).all()
    known = [{"id": str(p.id), "ip_address": p.ip_address, "mac_address": p.mac_address} for p in players]
    if settings.DISCOVERY_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.DISCOVERY_SERVICE_URL,
            method="POST",
            path="/discover/iconbit/scan",
            json_body={
                "subnet": body.subnet,
                "ports": body.ports,
                "known_devices": known,
            },
        )
    asyncio.create_task(_run_iconbit_discovery(body.subnet, body.ports, known))
    return {"status": "running", "scanned": 0, "total": 0, "found": 0, "message": None}


@router.get("/discover/status", response_model=ScanProgress)
async def discover_iconbit_status(current_user: CurrentUser) -> dict:
    del current_user
    if settings.DISCOVERY_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.DISCOVERY_SERVICE_URL,
            method="GET",
            path="/discover/iconbit/status",
        )
    return await get_discovery_progress("iconbit")


@router.get("/discover/results", response_model=DiscoveryResults)
async def discover_iconbit_results(current_user: CurrentUser) -> dict:
    del current_user
    if settings.DISCOVERY_SERVICE_ENABLED:
        payload = await _proxy_request(
            base_url=settings.DISCOVERY_SERVICE_URL,
            method="GET",
            path="/discover/iconbit/results",
        )
        return DiscoveryResults.model_validate(payload).model_dump()
    progress = await get_discovery_progress("iconbit")
    devices = await get_discovery_results("iconbit")
    return {"progress": progress, "devices": devices}


@router.post("/discover/add", response_model=MediaPlayerPublic, dependencies=[Depends(get_current_active_superuser)])
async def discover_add_iconbit(
    session: SessionDep,
    payload: dict,
) -> MediaPlayer:
    ip = str(payload.get("ip_address", "")).strip()
    if not ip:
        raise HTTPException(status_code=422, detail="ip_address is required")
    existing = session.exec(select(MediaPlayer).where(MediaPlayer.ip_address == ip)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Device with this IP already exists")
    name = str(payload.get("name") or f"Iconbit {ip}")
    model = str(payload.get("model") or "Iconbit")
    player = MediaPlayer(
        device_type="iconbit",
        name=name[:255],
        model=model[:255],
        ip_address=ip,
        mac_address=str(payload.get("mac_address") or "")[:17] or None,
    )
    session.add(player)
    session.commit()
    session.refresh(player)
    await _invalidate_cache()
    return player


@router.post(
    "/discover/update-ip/{player_id}",
    response_model=MediaPlayerPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
async def discover_update_iconbit_ip(
    player_id: uuid.UUID,
    session: SessionDep,
    new_ip: str = "",
    new_mac: str | None = None,
) -> MediaPlayer:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    old_ip = player.ip_address
    if new_ip:
        conflict = session.exec(select(MediaPlayer).where(MediaPlayer.ip_address == new_ip, MediaPlayer.id != player.id)).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Another device already has this IP")
        player.ip_address = new_ip
        if old_ip != new_ip:
            write_event_log(
                session,
                category="network",
                event_type="ip_changed",
                severity="warning",
                device_kind="media_player",
                device_name=player.name,
                ip_address=new_ip,
                message=f"Media player '{player.name}' moved IP: {old_ip} -> {new_ip}",
            )
    if new_mac:
        player.mac_address = new_mac
    player.updated_at = datetime.now(UTC)
    session.add(player)
    session.commit()
    session.refresh(player)
    await _invalidate_cache()
    return player


@router.get("/{player_id}", response_model=MediaPlayerPublic)
def read_media_player(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> MediaPlayer:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    return player


@router.patch("/{player_id}", response_model=MediaPlayerPublic, dependencies=[Depends(get_current_active_superuser)])
async def update_media_player(session: SessionDep, player_id: uuid.UUID, player_in: MediaPlayerUpdate) -> MediaPlayer:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    update_data = player_in.model_dump(exclude_unset=True)
    if "ip_address" in update_data and update_data["ip_address"] is not None:
        existing = session.exec(
            select(MediaPlayer).where(
                MediaPlayer.ip_address == update_data["ip_address"],
                MediaPlayer.id != player_id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Device with this IP already exists")
    player.updated_at = datetime.now(UTC)
    player.sqlmodel_update(update_data)
    session.add(player)
    session.commit()
    session.refresh(player)
    await _invalidate_cache()
    return player


@router.delete("/{player_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_media_player(session: SessionDep, player_id: uuid.UUID) -> Message:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    session.delete(player)
    session.commit()
    await _invalidate_cache()
    return Message(message="Media player deleted")


# ── Polling ──────────────────────────────────────────────────────


def _poll_one(player: MediaPlayer) -> tuple[str, object | None]:
    try:
        poll_jitter_sync()
        if player.device_type == "iconbit":
            is_online = check_tcp_port(player.ip_address, port=8081, timeout=2.5)
            return player.ip_address, _LightPollResult(is_online=is_online, open_ports=[8081] if is_online else [])
        result = poll_device_sync(player.ip_address)
        return player.ip_address, result
    except Exception as e:
        logger.warning("Poll failed for media player %s: %s", player.ip_address, e)
        return player.ip_address, None


def _apply_poll_result(player: MediaPlayer, result) -> None:
    """Apply poll results to a player model."""
    if result is None or not result.is_online:
        player.is_online = False
    else:
        player.is_online = True
        if result.hostname:
            player.hostname = result.hostname
        if result.os_info:
            player.os_info = result.os_info
        if result.uptime:
            player.uptime = result.uptime
        player.open_ports = ",".join(str(p) for p in result.open_ports) if result.open_ports else None
        if result.mac_address and not player.mac_address:
            player.mac_address = result.mac_address


@router.post("/{player_id}/poll", response_model=MediaPlayerPublic)
async def poll_single_player(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> MediaPlayer:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")

    was_online = player.is_online
    _, result = await asyncio.to_thread(_poll_one, player)
    _apply_poll_result(player, result)
    media_player_polls_total.labels(
        mode="single",
        device_type=player.device_type,
        result="online" if player.is_online else "offline",
    ).inc()

    # If offline and MAC is known, try to find new IP
    if not player.is_online and player.mac_address:
        new_ip = await find_device_by_mac(player.mac_address)
        if new_ip and new_ip != player.ip_address:
            logger.info("Device %s moved: %s -> %s (MAC %s)", player.name, player.ip_address, new_ip, player.mac_address)
            old_ip = player.ip_address
            player.ip_address = new_ip
            write_event_log(
                session,
                category="network",
                event_type="ip_changed",
                severity="warning",
                device_kind="media_player",
                device_name=player.name,
                ip_address=new_ip,
                message=f"Media player '{player.name}' moved IP: {old_ip} -> {new_ip}",
            )
            _, result = await asyncio.to_thread(_poll_one, player)
            _apply_poll_result(player, result)
            media_player_polls_total.labels(
                mode="single",
                device_type=player.device_type,
                result="online" if player.is_online else "offline",
            ).inc()

    player.last_polled_at = datetime.now(UTC)
    _record_status_change(session, player, was_online)
    write_media_player_snapshot(session, player, source="single_poll")
    session.add(player)
    session.commit()
    session.refresh(player)
    await _invalidate_cache()
    return player


@router.post("/poll-all", response_model=MediaPlayersPublic)
async def poll_all_players(
    session: SessionDep,
    current_user: CurrentUser,
    device_type: str | None = Query(default=None),
) -> MediaPlayersPublic:
    if settings.POLLING_SERVICE_ENABLED:
        payload = await _proxy_request(
            base_url=settings.POLLING_SERVICE_URL,
            method="POST",
            path="/poll/media-players",
            params={"device_type": device_type} if device_type else None,
        )
        return MediaPlayersPublic.model_validate(payload)

    started = perf_counter()
    lock_key = f"lock:poll-all:media:{device_type or 'all'}"
    lock_acquired = True
    try:
        r = await get_redis()
        lock_acquired = bool(await r.set(lock_key, "1", ex=45, nx=True))
    except Exception:
        lock_acquired = True
    statement = select(MediaPlayer)
    if device_type:
        statement = statement.where(MediaPlayer.device_type == device_type)
    players = session.exec(statement).all()
    set_device_counts(
        kind="media_player",
        total=len(players),
        online=sum(1 for p in players if p.is_online),
    )
    if not lock_acquired:
        logger.info("Skipping duplicate poll-all request for media players (%s): lock busy", device_type or "all")
        return MediaPlayersPublic(data=players, count=len(players))
    if not players:
        return MediaPlayersPublic(data=[], count=0)

    try:
        poll_targets: list[MediaPlayer] = []
        skipped_ids: set[uuid.UUID] = set()
        for player in players:
            if await is_circuit_open("media_player", str(player.id)):
                media_player_polls_total.labels(mode="all", device_type=player.device_type, result="skipped").inc()
                skipped_ids.add(player.id)
                continue
            poll_targets.append(player)

        results: dict[str, object | None] = {}
        if poll_targets:
            with ThreadPoolExecutor(max_workers=min(MAX_POLL_WORKERS, len(poll_targets))) as pool:
                futures = {pool.submit(_poll_one, p): p.ip_address for p in poll_targets}
                for future in as_completed(futures):
                    ip = futures[future]
                    try:
                        _, result = future.result()
                    except Exception as e:
                        logger.warning("Poll failed for %s: %s", ip, e)
                        result = None
                    results[ip] = result

        # Apply results and collect offline devices with MAC for rediscovery
        offline_with_mac: list[MediaPlayer] = []
        for player in players:
            if player.id in skipped_ids:
                session.add(player)
                continue

            result = results.get(player.ip_address)
            previous_online = player.is_online
            raw_online = bool(result and result.is_online)
            effective_online = await apply_poll_outcome(
                kind="media_player",
                entity_id=str(player.id),
                previous_effective_online=previous_online,
                probed_online=raw_online,
                probed_error=result is None,
            )
            _apply_poll_result(player, result)
            player.is_online = effective_online
            media_player_polls_total.labels(
                mode="all",
                device_type=player.device_type,
                result="online" if effective_online else "offline",
            ).inc()
            if (not effective_online) and player.mac_address:
                offline_with_mac.append(player)
            player.last_polled_at = datetime.now(UTC)
            _record_status_change(session, player, previous_online)
            write_media_player_snapshot(session, player, source="bulk_poll")
            session.add(player)

        # Try to rediscover offline devices by MAC (one sweep for all)
        if offline_with_mac:
            logger.info("Trying MAC rediscovery for %d offline devices...", len(offline_with_mac))
            mac_to_ip = await find_devices_by_macs([p.mac_address for p in offline_with_mac if p.mac_address])
            for player in offline_with_mac:
                new_ip = mac_to_ip.get((player.mac_address or "").lower())
                if new_ip and new_ip != player.ip_address:
                    logger.info("Device %s moved: %s -> %s (MAC %s)", player.name, player.ip_address, new_ip, player.mac_address)
                    old_ip = player.ip_address
                    player.ip_address = new_ip
                    write_event_log(
                        session,
                        category="network",
                        event_type="ip_changed",
                        severity="warning",
                        device_kind="media_player",
                        device_name=player.name,
                        ip_address=new_ip,
                        message=f"Media player '{player.name}' moved IP: {old_ip} -> {new_ip}",
                    )
                    _, result = await asyncio.to_thread(_poll_one, player)
                    _apply_poll_result(player, result)
                    media_player_polls_total.labels(
                        mode="all",
                        device_type=player.device_type,
                        result="online" if player.is_online else "offline",
                    ).inc()
                    player.last_polled_at = datetime.now(UTC)
                    write_media_player_snapshot(session, player, source="bulk_poll_relocated")
                    session.add(player)

        session.commit()
        success_count = sum(1 for p in players if p.is_online)
        network_bulk_processed_total.labels(operation="media_poll_all", result="success").inc(success_count)
        network_bulk_processed_total.labels(operation="media_poll_all", result="offline").inc(max(len(players) - success_count, 0))
        network_bulk_operation_duration_seconds.labels(operation="media_poll_all").observe(max(perf_counter() - started, 0))

        result_statement = select(MediaPlayer)
        if device_type:
            result_statement = result_statement.where(MediaPlayer.device_type == device_type)
        all_players = session.exec(result_statement).all()
        set_device_counts(
            kind="media_player",
            total=len(all_players),
            online=sum(1 for p in all_players if p.is_online),
        )

        await _invalidate_cache()
        return MediaPlayersPublic(data=all_players, count=len(all_players))
    finally:
        if lock_acquired:
            try:
                r = await get_redis()
                await r.delete(lock_key)
            except Exception:
                pass


# ── Rediscovery ──────────────────────────────────────────────────


@router.post("/rediscover", response_model=MediaPlayersPublic)
async def rediscover_devices(
    session: SessionDep,
    current_user: CurrentUser,
) -> MediaPlayersPublic:
    """Find devices that changed IP by scanning subnets for known MACs."""
    started = perf_counter()
    players = session.exec(select(MediaPlayer).where(MediaPlayer.mac_address.isnot(None))).all()
    if not players:
        return MediaPlayersPublic(data=[], count=0)

    updated = 0
    mac_to_ip = await find_devices_by_macs([p.mac_address for p in players if p.mac_address])
    for player in players:
        new_ip = mac_to_ip.get((player.mac_address or "").lower())
        if new_ip and new_ip != player.ip_address:
            logger.info("Rediscovery: %s moved %s -> %s (MAC %s)", player.name, player.ip_address, new_ip, player.mac_address)
            old_ip = player.ip_address
            player.ip_address = new_ip
            updated += 1
            write_event_log(
                session,
                category="network",
                event_type="ip_changed",
                severity="warning",
                device_kind="media_player",
                device_name=player.name,
                ip_address=new_ip,
                message=f"Media player '{player.name}' moved IP: {old_ip} -> {new_ip}",
            )
            _, result = await asyncio.to_thread(_poll_one, player)
            _apply_poll_result(player, result)
            player.last_polled_at = datetime.now(UTC)
            write_media_player_snapshot(session, player, source="rediscover")
            session.add(player)

    if updated:
        session.commit()
        await _invalidate_cache()

    logger.info("Rediscovery complete: %d/%d devices updated", updated, len(players))
    media_player_ops_total.labels(operation="rediscover", result="success").inc()
    network_bulk_processed_total.labels(operation="media_rediscover", result="success").inc(updated)
    network_bulk_processed_total.labels(operation="media_rediscover", result="unchanged").inc(max(len(players) - updated, 0))
    network_bulk_operation_duration_seconds.labels(operation="media_rediscover").observe(max(perf_counter() - started, 0))
    all_players = session.exec(select(MediaPlayer)).all()
    return MediaPlayersPublic(data=all_players, count=len(all_players))


# ── Iconbit control ──────────────────────────────────────────────


@router.get("/{player_id}/iconbit/status")
async def iconbit_status(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> dict:
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="GET",
            path=f"/iconbit/{player_id}/status",
        )
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    result = await asyncio.to_thread(iconbit_get_status, player.ip_address)
    media_player_ops_total.labels(operation="iconbit_status", result="success").inc()
    return {
        "now_playing": result.now_playing,
        "is_playing": result.is_playing,
        "state": result.state,
        "position": result.position,
        "duration": result.duration,
        "files": result.files,
        "free_space": result.free_space,
    }


@router.post("/{player_id}/iconbit/play")
async def iconbit_play_action(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> dict:
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path=f"/iconbit/{player_id}/play",
        )
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_play, player.ip_address)
    if not ok:
        media_player_ops_total.labels(operation="iconbit_play", result="error").inc()
        raise HTTPException(status_code=502, detail="Failed to start playback")
    media_player_ops_total.labels(operation="iconbit_play", result="success").inc()
    return {"status": "playing"}


@router.post("/{player_id}/iconbit/stop")
async def iconbit_stop_action(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> dict:
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path=f"/iconbit/{player_id}/stop",
        )
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_stop, player.ip_address)
    if not ok:
        media_player_ops_total.labels(operation="iconbit_stop", result="error").inc()
        raise HTTPException(status_code=502, detail="Failed to stop playback")
    media_player_ops_total.labels(operation="iconbit_stop", result="success").inc()
    return {"status": "stopped"}


@router.post("/{player_id}/iconbit/play-file")
async def iconbit_play_file_action(
    player_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path=f"/iconbit/{player_id}/play-file",
            json_body={"filename": filename},
        )
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_play_file, player.ip_address, filename)
    if not ok:
        media_player_ops_total.labels(operation="iconbit_play_file", result="error").inc()
        raise HTTPException(status_code=502, detail="Failed to play file")
    media_player_ops_total.labels(operation="iconbit_play_file", result="success").inc()
    return {"status": "playing", "file": filename}


@router.post("/{player_id}/iconbit/delete-file")
async def iconbit_delete_file_action(
    player_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path=f"/iconbit/{player_id}/delete-file",
            json_body={"filename": filename},
        )
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_delete_file, player.ip_address, filename)
    if not ok:
        media_player_ops_total.labels(operation="iconbit_delete_file", result="error").inc()
        raise HTTPException(status_code=502, detail="Failed to delete file")
    media_player_ops_total.labels(operation="iconbit_delete_file", result="success").inc()
    return {"status": "deleted", "file": filename}


@router.post("/{player_id}/iconbit/upload")
async def iconbit_upload_action(
    player_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = ...,
) -> dict:
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        content = await file.read()
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path=f"/iconbit/{player_id}/upload",
            files={"file": (file.filename or "upload.mp3", content, file.content_type or "application/octet-stream")},
        )
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    content = await file.read()
    ok = await asyncio.to_thread(iconbit_upload_file, player.ip_address, file.filename or "upload.mp3", content)
    if not ok:
        media_player_ops_total.labels(operation="iconbit_upload", result="error").inc()
        raise HTTPException(status_code=502, detail="Failed to upload file")
    media_player_ops_total.labels(operation="iconbit_upload", result="success").inc()
    return {"status": "uploaded", "file": file.filename}


# ── Bulk Iconbit operations ─────────────────────────────────────


def _get_all_iconbits(session) -> list[MediaPlayer]:
    return list(session.exec(select(MediaPlayer).where(MediaPlayer.device_type == "iconbit")).all())


@router.post("/iconbit/bulk-play")
async def iconbit_bulk_play(session: SessionDep, current_user: CurrentUser) -> dict:
    """Start playback on all Iconbit devices."""
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path="/iconbit/bulk-play",
        )
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_play, p.ip_address)
        results.append(ok)
    success = sum(results)
    failed = len(results) - success
    media_player_ops_total.labels(operation="iconbit_bulk_play", result="success").inc(success)
    media_player_ops_total.labels(operation="iconbit_bulk_play", result="error").inc(failed)
    return {"success": success, "failed": failed}


@router.post("/iconbit/bulk-stop")
async def iconbit_bulk_stop(session: SessionDep, current_user: CurrentUser) -> dict:
    """Stop playback on all Iconbit devices."""
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path="/iconbit/bulk-stop",
        )
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_stop, p.ip_address)
        results.append(ok)
    success = sum(results)
    failed = len(results) - success
    media_player_ops_total.labels(operation="iconbit_bulk_stop", result="success").inc(success)
    media_player_ops_total.labels(operation="iconbit_bulk_stop", result="error").inc(failed)
    return {"success": success, "failed": failed}


@router.post("/iconbit/bulk-upload")
async def iconbit_bulk_upload(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = ...,
) -> dict:
    """Upload a media file to all Iconbit devices."""
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        content = await file.read()
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path="/iconbit/bulk-upload",
            files={"file": (file.filename or "upload.mp3", content, file.content_type or "application/octet-stream")},
        )
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    content = await file.read()
    fname = file.filename or "upload.mp3"
    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_upload_file, p.ip_address, fname, content)
        results.append(ok)
    success = sum(results)
    failed = len(results) - success
    media_player_ops_total.labels(operation="iconbit_bulk_upload", result="success").inc(success)
    media_player_ops_total.labels(operation="iconbit_bulk_upload", result="error").inc(failed)
    return {"success": success, "failed": failed, "file": fname}


@router.post("/iconbit/bulk-delete-file")
async def iconbit_bulk_delete(
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    """Delete a file from all Iconbit devices."""
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path="/iconbit/bulk-delete-file",
            json_body={"filename": filename},
        )
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_delete_file, p.ip_address, filename)
        results.append(ok)
    success = sum(results)
    failed = len(results) - success
    media_player_ops_total.labels(operation="iconbit_bulk_delete", result="success").inc(success)
    media_player_ops_total.labels(operation="iconbit_bulk_delete", result="error").inc(failed)
    return {"success": success, "failed": failed, "file": filename}


@router.post("/iconbit/bulk-play-file")
async def iconbit_bulk_play_file(
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    """Play a specific file on all Iconbit devices."""
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path="/iconbit/bulk-play-file",
            json_body={"filename": filename},
        )
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_play_file, p.ip_address, filename)
        results.append(ok)
    success = sum(results)
    failed = len(results) - success
    media_player_ops_total.labels(operation="iconbit_bulk_play_file", result="success").inc(success)
    media_player_ops_total.labels(operation="iconbit_bulk_play_file", result="error").inc(failed)
    return {"success": success, "failed": failed, "file": filename}


@router.post("/iconbit/bulk-replace")
async def iconbit_bulk_replace(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = ...,
) -> dict:
    """Replace playlist on all Iconbit: delete old files, upload new, start playback."""
    if settings.NETWORK_CONTROL_SERVICE_ENABLED:
        content = await file.read()
        return await _proxy_request(
            base_url=settings.NETWORK_CONTROL_SERVICE_URL,
            method="POST",
            path="/iconbit/bulk-replace",
            files={"file": (file.filename or "upload.mp3", content, file.content_type or "application/octet-stream")},
        )
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    content = await file.read()
    fname = file.filename or "upload.mp3"
    success = 0
    failed = 0
    for p in players:
        try:
            await asyncio.to_thread(iconbit_delete_all, p.ip_address)
            uploaded = await asyncio.to_thread(iconbit_upload_file, p.ip_address, fname, content)
            if uploaded:
                await asyncio.to_thread(iconbit_play, p.ip_address)
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    media_player_ops_total.labels(operation="iconbit_bulk_replace", result="success").inc(success)
    media_player_ops_total.labels(operation="iconbit_bulk_replace", result="error").inc(failed)
    return {"success": success, "failed": failed, "file": fname}
