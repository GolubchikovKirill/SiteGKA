from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.routes import media_players as media_routes


@dataclass
class _PollResult:
    is_online: bool = True
    hostname: str | None = "NETTOP-01"
    os_info: str | None = "Windows 10"
    uptime: str | None = "1д 2ч"
    open_ports: list[int] | None = None
    mac_address: str | None = "aa:bb:cc:dd:ee:ff"


def test_create_media_player_and_poll(client: TestClient, admin_token: str, monkeypatch):
    async def _no_move(_mac: str):
        return None

    monkeypatch.setattr(media_routes, "_poll_one", lambda _player: ("10.10.10.20", _PollResult(open_ports=[445, 3389])))
    monkeypatch.setattr(media_routes, "find_device_by_mac", _no_move)

    created = client.post(
        "/api/v1/media-players/",
        json={
            "device_type": "nettop",
            "name": "Music PC",
            "model": "Nettop",
            "ip_address": "10.10.10.20",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 200
    player_id = created.json()["id"]

    polled = client.post(
        f"/api/v1/media-players/{player_id}/poll",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert polled.status_code == 200
    assert polled.json()["is_online"] is True
