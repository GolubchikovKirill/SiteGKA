def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint(client):
    response = client.get("/ready")
    assert response.status_code in (200, 503)
    payload = response.json()
    assert payload["status"] in ("ready", "degraded")
    assert "checks" in payload
    assert {"database", "redis"} <= set(payload["checks"].keys())
