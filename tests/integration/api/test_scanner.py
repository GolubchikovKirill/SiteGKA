from fastapi.testclient import TestClient


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
