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


def test_iconbit_discovery_scan_and_results(client: TestClient, admin_token: str, monkeypatch):
    async def _fake_run(kind: str, subnet: str, ports: str, known_devices: list[dict]):
        assert kind == "iconbit"
        assert subnet == "10.10.98.0/24"
        assert ports == "8081,80,443"
        assert isinstance(known_devices, list)
        return None

    async def _fake_progress(_kind: str):
        return {"status": "done", "scanned": 254, "total": 254, "found": 1, "message": None}

    async def _fake_results(_kind: str):
        return [
            {
                "ip": "10.10.98.120",
                "mac": "aa:bb:cc:11:22:33",
                "open_ports": [8081],
                "hostname": "ICONBIT-01",
                "model_info": "Iconbit",
                "vendor": "generic",
                "device_kind": "iconbit",
                "is_known": False,
                "known_device_id": None,
                "ip_changed": False,
                "old_ip": None,
            }
        ]

    monkeypatch.setattr(media_routes, "run_discovery_scan", _fake_run)
    monkeypatch.setattr(media_routes, "get_discovery_progress", _fake_progress)
    monkeypatch.setattr(media_routes, "get_discovery_results", _fake_results)

    scan_resp = client.post(
        "/api/v1/media-players/discover/scan",
        json={"subnet": "10.10.98.0/24", "ports": "8081,80,443"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert scan_resp.status_code == 200
    assert scan_resp.json()["status"] == "running"

    results_resp = client.get(
        "/api/v1/media-players/discover/results",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert results_resp.status_code == 200
    assert results_resp.json()["progress"]["status"] == "done"
    assert results_resp.json()["devices"][0]["device_kind"] == "iconbit"


def test_iconbit_discovery_add_and_update_ip(client: TestClient, admin_token: str):
    create_resp = client.post(
        "/api/v1/media-players/discover/add",
        json={
            "ip_address": "10.10.98.121",
            "name": "Iconbit New",
            "model": "Iconbit",
            "mac_address": "aa:bb:cc:dd:ee:11",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200
    player_id = create_resp.json()["id"]
    assert create_resp.json()["device_type"] == "iconbit"

    update_resp = client.post(
        f"/api/v1/media-players/discover/update-ip/{player_id}",
        params={"new_ip": "10.10.98.122", "new_mac": "aa:bb:cc:dd:ee:12"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["ip_address"] == "10.10.98.122"
    assert update_resp.json()["mac_address"] == "aa:bb:cc:dd:ee:12"
