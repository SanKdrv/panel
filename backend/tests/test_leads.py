def test_lead_card_aggregates(client, auth_headers, fake_rag):
    r = client.get("/api/leads/lead_1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["lead_id"] == "lead_1"
    assert len(body["actions"]) == 1
    assert len(body["tasks"]) == 1
    assert len(body["recommendations"]) == 1
    assert body["errors"] == {}


def test_lead_card_partial_failure(client, auth_headers, fake_rag):
    from unittest.mock import AsyncMock
    fake_rag.get_lead_tasks = AsyncMock(side_effect=RuntimeError("redis down"))
    r = client.get("/api/leads/lead_1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "tasks" in body["errors"]
    # other sections still present
    assert len(body["actions"]) == 1
    assert len(body["recommendations"]) == 1
