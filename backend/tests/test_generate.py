def test_generate_trigger(client, auth_headers, fake_rag):
    r = client.post(
        "/api/generate",
        headers=auth_headers,
        json={"lead_id": "lead_1", "type": "warm"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"] == "tok123"
    assert body["status"] == "queued"
    fake_rag.generate_recommendation.assert_awaited_with("lead_1", "warm")


def test_generate_status(client, auth_headers, fake_rag):
    r = client.get("/api/generate/status/tok123", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_generate_invalid_type(client, auth_headers):
    r = client.post(
        "/api/generate",
        headers=auth_headers,
        json={"lead_id": "lead_1", "type": "bogus"},
    )
    assert r.status_code == 422


def test_generate_propagates_rag_error(client, auth_headers, fake_rag):
    from unittest.mock import AsyncMock
    fake_rag.generate_recommendation = AsyncMock(side_effect=RuntimeError("rag down"))
    r = client.post(
        "/api/generate",
        headers=auth_headers,
        json={"lead_id": "lead_1", "type": "cold"},
    )
    assert r.status_code == 502
