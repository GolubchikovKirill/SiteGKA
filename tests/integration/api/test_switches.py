from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.routes import switches as switch_routes


@dataclass
class _SwitchInfo:
    hostname: str | None = "SW-01"
    model_info: str | None = "WS-C2960X"
    ios_version: str | None = "15.2(7)E"
    uptime: str | None = "2д 5ч"
    is_online: bool = True


def test_create_and_poll_switch(client: TestClient, admin_token: str, monkeypatch):
    monkeypatch.setattr(switch_routes, "get_switch_info", lambda *_args, **_kwargs: _SwitchInfo())

    created = client.post(
        "/api/v1/switches/",
        json={
            "name": "Main Switch",
            "ip_address": "10.10.10.30",
            "ssh_username": "admin",
            "ssh_password": "admin",
            "enable_password": "admin",
            "ssh_port": 22,
            "ap_vlan": 20,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 200
    switch_id = created.json()["id"]

    polled = client.post(
        f"/api/v1/switches/{switch_id}/poll",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert polled.status_code == 200
    assert polled.json()["is_online"] is True
