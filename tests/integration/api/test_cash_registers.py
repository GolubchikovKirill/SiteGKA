from app.api.routes import cash_registers as cash_routes


def test_create_cash_register(client, admin_token: str):
    payload = {
        "kkm_number": "001",
        "store_code": "A1",
        "kkm_type": "retail",
        "hostname": "cash-a1",
    }
    response = client.post(
        "/api/v1/cash-registers/",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["kkm_number"] == "001"


def test_poll_all_cash_registers_uses_polling_service_when_enabled(client, admin_token: str, monkeypatch):
    async def _fake_proxy_request(**kwargs):
        assert kwargs["path"] == "/poll/cash-registers"
        return {"data": [], "count": 0}

    monkeypatch.setattr(cash_routes.settings, "POLLING_SERVICE_ENABLED", True)
    monkeypatch.setattr(cash_routes, "_proxy_request", _fake_proxy_request)

    response = client.post(
        "/api/v1/cash-registers/poll-all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0
