def test_health_public(client, fake_rag):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "staging_area" in body["components"]


def test_health_passthrough_on_error(client, fake_rag):
    from unittest.mock import AsyncMock
    fake_rag.health = AsyncMock(side_effect=RuntimeError("boom"))
    r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unhealthy"


def test_dashboard_requires_auth(client):
    r = client.get("/api/system/dashboard")
    assert r.status_code == 401


def test_dashboard_authorized(client, auth_headers, fake_rag):
    r = client.get("/api/system/dashboard", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["health"]["status"] == "healthy"
    assert "grafana_embed_url" in body


def test_panel_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
