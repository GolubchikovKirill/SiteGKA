from fastapi.testclient import TestClient

from app.api.routes import scanner as scanner_routes


def test_get_scanner_settings_requires_auth(client: TestClient):
    response = client.get("/api/v1/scanner/settings")
    assert response.status_code in (401, 403)


def test_get_scanner_settings(client: TestClient, admin_token: str):
    response = client.get(
        "/api/v1/scanner/settings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "subnet" in response.json()
    assert "ports" in response.json()


def test_scanner_status_uses_discovery_service_when_enabled(client: TestClient, admin_token: str, monkeypatch):
    async def _fake_proxy_request(**kwargs):
        assert kwargs["path"] == "/discover/printers/status"
        return {"status": "running", "scanned": 1, "total": 10, "found": 0, "message": None}

    monkeypatch.setattr(scanner_routes.settings, "DISCOVERY_SERVICE_ENABLED", True)
    monkeypatch.setattr(scanner_routes, "_proxy_request", _fake_proxy_request)
    response = client.get(
        "/api/v1/scanner/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"
