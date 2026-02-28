from fastapi.testclient import TestClient

from app.api.routes import printers as printer_routes


def test_create_printer_and_reject_duplicate_ip(client: TestClient, admin_token: str):
    payload = {
        "printer_type": "laser",
        "connection_type": "ip",
        "store_name": "Store A",
        "model": "HP M404",
        "ip_address": "10.10.10.10",
        "snmp_community": "public",
    }
    first = client.post(
        "/api/v1/printers/",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/printers/",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 400


def test_poll_usb_printer_is_blocked(client: TestClient, admin_token: str):
    create = client.post(
        "/api/v1/printers/",
        json={
            "printer_type": "label",
            "connection_type": "usb",
            "store_name": "Store USB",
            "model": "Zebra",
            "host_pc": "POS-01",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create.status_code == 200
    printer_id = create.json()["id"]

    poll = client.post(
        f"/api/v1/printers/{printer_id}/poll",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert poll.status_code == 400


def test_poll_all_printers_uses_polling_service_when_enabled(client: TestClient, admin_token: str, monkeypatch):
    async def _fake_proxy_request(**kwargs):
        assert kwargs["path"] == "/poll/printers"
        return {"data": [], "count": 0}

    monkeypatch.setattr(printer_routes.settings, "POLLING_SERVICE_ENABLED", True)
    monkeypatch.setattr(printer_routes, "_proxy_request", _fake_proxy_request)
    response = client.post(
        "/api/v1/printers/poll-all",
        params={"printer_type": "laser"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0
