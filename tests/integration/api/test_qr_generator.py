from app.api.routes import qr_generator as qr_routes


def test_qr_generator_requires_auth(client):
    response = client.post("/api/v1/qr-generator/export", json={})
    assert response.status_code == 401


def test_qr_generator_requires_superuser(client, user_token: str):
    response = client.post(
        "/api/v1/qr-generator/export",
        json={
            "db_mode": "duty_free",
            "airport_code": "4007",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_qr_generator_returns_zip(client, admin_token: str, monkeypatch):
    def _fake_generate(_params):
        return b"fake-zip-content"

    monkeypatch.setattr(qr_routes, "generate_qr_docs_zip", _fake_generate)

    response = client.post(
        "/api/v1/qr-generator/export",
        json={
            "db_mode": "both",
            "airport_code": "4007",
            "surnames": "Иванов",
            "add_login": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.content == b"fake-zip-content"
