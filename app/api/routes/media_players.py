import asyncio
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.redis import get_redis
from app.models import MediaPlayer
from app.schemas import (
    MediaPlayerCreate,
    MediaPlayerPublic,
    MediaPlayersPublic,
    MediaPlayerUpdate,
    Message,
)
from app.services.device_poll import poll_device_sync
from app.services.iconbit import (
    delete_file as iconbit_delete_file,
    get_status as iconbit_get_status,
    play as iconbit_play,
    play_file as iconbit_play_file,
    stop as iconbit_stop,
    upload_file as iconbit_upload_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["media-players"])

MAX_POLL_WORKERS = 20
CACHE_TTL = 30


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
        result = poll_device_sync(player.ip_address)
        return player.ip_address, result
    except Exception as e:
        logger.warning("Poll failed for media player %s: %s", player.ip_address, e)
        return player.ip_address, None


@router.post("/{player_id}/poll", response_model=MediaPlayerPublic)
async def poll_single_player(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> MediaPlayer:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")

    _, result = await asyncio.to_thread(_poll_one, player)

    if result is None:
        player.is_online = False
    else:
        player.is_online = result.is_online
        player.hostname = result.hostname
        player.os_info = result.os_info
        player.uptime = result.uptime
        player.open_ports = ",".join(str(p) for p in result.open_ports) if result.open_ports else None
        if result.mac_address and not player.mac_address:
            player.mac_address = result.mac_address

    player.last_polled_at = datetime.now(UTC)
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
    statement = select(MediaPlayer)
    if device_type:
        statement = statement.where(MediaPlayer.device_type == device_type)
    players = session.exec(statement).all()
    if not players:
        return MediaPlayersPublic(data=[], count=0)

    results: dict[str, object | None] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_POLL_WORKERS, len(players))) as pool:
        futures = {pool.submit(_poll_one, p): p.ip_address for p in players}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                _, result = future.result()
            except Exception as e:
                logger.warning("Poll failed for %s: %s", ip, e)
                result = None
            results[ip] = result

    for player in players:
        result = results.get(player.ip_address)
        if result is None:
            player.is_online = False
        else:
            player.is_online = result.is_online
            player.hostname = result.hostname
            player.os_info = result.os_info
            player.uptime = result.uptime
            player.open_ports = ",".join(str(p) for p in result.open_ports) if result.open_ports else None
            if result.mac_address and not player.mac_address:
                player.mac_address = result.mac_address
        player.last_polled_at = datetime.now(UTC)
        session.add(player)

    session.commit()

    result_statement = select(MediaPlayer)
    if device_type:
        result_statement = result_statement.where(MediaPlayer.device_type == device_type)
    all_players = session.exec(result_statement).all()

    await _invalidate_cache()
    return MediaPlayersPublic(data=all_players, count=len(all_players))


# ── Iconbit control ──────────────────────────────────────────────


@router.get("/{player_id}/iconbit/status")
async def iconbit_status(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> dict:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    result = await asyncio.to_thread(iconbit_get_status, player.ip_address)
    return {
        "now_playing": result.now_playing,
        "is_playing": result.is_playing,
        "files": result.files,
        "free_space": result.free_space,
    }


@router.post("/{player_id}/iconbit/play")
async def iconbit_play_action(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> dict:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_play, player.ip_address)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to start playback")
    return {"status": "playing"}


@router.post("/{player_id}/iconbit/stop")
async def iconbit_stop_action(player_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> dict:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_stop, player.ip_address)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to stop playback")
    return {"status": "stopped"}


@router.post("/{player_id}/iconbit/play-file")
async def iconbit_play_file_action(
    player_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_play_file, player.ip_address, filename)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to play file")
    return {"status": "playing", "file": filename}


@router.post("/{player_id}/iconbit/delete-file")
async def iconbit_delete_file_action(
    player_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    ok = await asyncio.to_thread(iconbit_delete_file, player.ip_address, filename)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to delete file")
    return {"status": "deleted", "file": filename}


@router.post("/{player_id}/iconbit/upload")
async def iconbit_upload_action(
    player_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = ...,
) -> dict:
    player = session.get(MediaPlayer, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Media player not found")
    if player.device_type != "iconbit":
        raise HTTPException(status_code=400, detail="Not an Iconbit device")
    content = await file.read()
    ok = await asyncio.to_thread(iconbit_upload_file, player.ip_address, file.filename or "upload.mp3", content)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to upload file")
    return {"status": "uploaded", "file": file.filename}


# ── Bulk Iconbit operations ─────────────────────────────────────


def _get_all_iconbits(session) -> list[MediaPlayer]:
    return list(session.exec(select(MediaPlayer).where(MediaPlayer.device_type == "iconbit")).all())


@router.post("/iconbit/bulk-play")
async def iconbit_bulk_play(session: SessionDep, current_user: CurrentUser) -> dict:
    """Start playback on all Iconbit devices."""
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_play, p.ip_address)
        results.append(ok)
    return {"success": sum(results), "failed": len(results) - sum(results)}


@router.post("/iconbit/bulk-stop")
async def iconbit_bulk_stop(session: SessionDep, current_user: CurrentUser) -> dict:
    """Stop playback on all Iconbit devices."""
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_stop, p.ip_address)
        results.append(ok)
    return {"success": sum(results), "failed": len(results) - sum(results)}


@router.post("/iconbit/bulk-upload")
async def iconbit_bulk_upload(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = ...,
) -> dict:
    """Upload a media file to all Iconbit devices."""
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    content = await file.read()
    fname = file.filename or "upload.mp3"
    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_upload_file, p.ip_address, fname, content)
        results.append(ok)
    return {"success": sum(results), "failed": len(results) - sum(results), "file": fname}


@router.post("/iconbit/bulk-delete-file")
async def iconbit_bulk_delete(
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    """Delete a file from all Iconbit devices."""
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_delete_file, p.ip_address, filename)
        results.append(ok)
    return {"success": sum(results), "failed": len(results) - sum(results), "file": filename}


@router.post("/iconbit/bulk-play-file")
async def iconbit_bulk_play_file(
    session: SessionDep,
    current_user: CurrentUser,
    filename: str = Body(embed=True),
) -> dict:
    """Play a specific file on all Iconbit devices."""
    players = _get_all_iconbits(session)
    if not players:
        return {"success": 0, "failed": 0}

    results = []
    for p in players:
        ok = await asyncio.to_thread(iconbit_play_file, p.ip_address, filename)
        results.append(ok)
    return {"success": sum(results), "failed": len(results) - sum(results), "file": filename}
