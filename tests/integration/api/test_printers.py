from fastapi.testclient import TestClient


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
