from fastapi.testclient import TestClient


def test_login_success_returns_access_token(client: TestClient, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "Pass1234"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_password_returns_400(client: TestClient, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "wrong-pass"},
    )
    assert response.status_code == 400


def test_test_token_endpoint_requires_valid_token(client: TestClient, admin_token: str):
    response = client.post(
        "/api/v1/auth/test-token",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"
