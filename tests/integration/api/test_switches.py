from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.api.routes import switches as switch_routes
from app.services.switches.base import SwitchPollInfo, SwitchPortState


@dataclass
class _SwitchInfo:
    hostname: str | None = "SW-01"
    model_info: str | None = "WS-C2960X"
    ios_version: str | None = "15.2(7)E"
    uptime: str | None = "2д 5ч"
    is_online: bool = True


def test_create_and_poll_switch(client: TestClient, admin_token: str, monkeypatch):
    class _Provider:
        def poll_switch(self, _switch):
            info = _SwitchInfo()
            return SwitchPollInfo(
                is_online=info.is_online,
                hostname=info.hostname,
                model_info=info.model_info,
                ios_version=info.ios_version,
                uptime=info.uptime,
            )

        def get_ports(self, _switch):
            return []

        def set_admin_state(self, _switch, _port, _state):
            return None

        def set_description(self, _switch, _port, _description):
            return None

        def set_vlan(self, _switch, _port, _vlan):
            return None

        def set_poe(self, _switch, _port, _action):
            return None

    monkeypatch.setattr(switch_routes, "resolve_switch_provider", lambda *_args, **_kwargs: _Provider())

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
            "vendor": "cisco",
            "management_protocol": "snmp+ssh",
            "snmp_version": "2c",
            "snmp_community_ro": "public",
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


def test_switch_ports_read_and_write(
    client: TestClient,
    admin_token: str,
    user_token: str,
    monkeypatch,
):
    class _Provider:
        def poll_switch(self, _switch):
            return SwitchPollInfo(is_online=True)

        def get_ports(self, _switch):
            return [
                SwitchPortState(
                    port="Gi0/1",
                    if_index=1,
                    description="AP uplink",
                    admin_status="up",
                    oper_status="up",
                    speed_mbps=1000,
                    vlan=20,
                    poe_enabled=True,
                )
            ]

        def set_admin_state(self, _switch, _port, _state):
            return None

        def set_description(self, _switch, _port, _description):
            return None

        def set_vlan(self, _switch, _port, _vlan):
            return None

        def set_poe(self, _switch, _port, _action):
            return None

    monkeypatch.setattr(switch_routes, "resolve_switch_provider", lambda *_args, **_kwargs: _Provider())

    created = client.post(
        "/api/v1/switches/",
        json={
            "name": "D-Link Floor 1",
            "ip_address": "10.10.10.40",
            "ssh_username": "admin",
            "ssh_password": "admin",
            "enable_password": "",
            "ssh_port": 22,
            "ap_vlan": 20,
            "vendor": "dlink",
            "management_protocol": "snmp",
            "snmp_version": "2c",
            "snmp_community_ro": "public",
            "snmp_community_rw": "private",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 200
    switch_id = created.json()["id"]

    read_ports = client.get(
        f"/api/v1/switches/{switch_id}/ports",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert read_ports.status_code == 200
    assert read_ports.json()["count"] == 1
    assert read_ports.json()["data"][0]["port"] == "Gi0/1"

    forbidden_write = client.post(
        f"/api/v1/switches/{switch_id}/ports/Gi0%2F1/vlan",
        json={"vlan": 100},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_write.status_code == 403

    write_ok = client.post(
        f"/api/v1/switches/{switch_id}/ports/Gi0%2F1/vlan",
        json={"vlan": 100},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert write_ok.status_code == 200
