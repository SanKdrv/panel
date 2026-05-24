"""Tests for quality evaluation pipeline (v2)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services import gold_dataset as gold_service
from app.services import quality as q
from app.services.metrics import (
    QUALITY_FAITHFULNESS,
    QUALITY_SAMPLES,
)
from app.routers import quality as quality_router


# ===== context_precision =====

def test_context_precision_full_overlap():
    assert q.context_precision("Котики молоко", "котики и молоко") == 1.0


def test_context_precision_partial():
    ref = "apple banana cherry"
    gen = "apple"
    assert q.context_precision(ref, gen) == pytest.approx(1 / 3, abs=0.01)


def test_context_precision_empty_reference():
    assert q.context_precision("", "anything") == 0.0


def test_context_precision_case_insensitive():
    assert q.context_precision("HELLO", "hello world") == 1.0


# ===== cosine =====

def test_cosine_orthogonal():
    assert q._cosine([1, 0], [0, 1]) == 0.0


def test_cosine_identical():
    assert q._cosine([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_cosine_empty_input():
    assert q._cosine([], []) == 0.0


def test_cosine_mismatched_length():
    assert q._cosine([1, 2], [1, 2, 3]) == 0.0


def test_tokenize_strips_punctuation():
    tokens = q._tokenize("Hello, world! Привет.")
    assert "hello" in tokens and "world" in tokens and "привет" in tokens


# ===== extract_text =====

def test_extract_text_string():
    assert q.extract_text("hello") == "hello"


def test_extract_text_none():
    assert q.extract_text(None) == ""


def test_extract_text_picks_recommendation():
    data = {
        "title": "Test title",
        "recommendation": "Главный текст рекомендации",
        "reason": "Потому что",
        "_system": {"task_id": "x", "lead_id": "153"},
    }
    out = q.extract_text(data)
    assert "Главный текст рекомендации" in out
    # title — метаинформация о контенте, в сравнение не идёт
    assert "Test title" not in out
    # reason — служебное объяснение, в сравнение не идёт
    assert "Потому что" not in out
    assert "task_id" not in out
    assert "_system" not in out


def test_extract_text_fallback_to_other_strings():
    data = {"foo": "Some text", "bar": "More text", "_system": {"x": 1}}
    out = q.extract_text(data)
    assert "Some text" in out
    assert "More text" in out
    assert "_system" not in out


def test_extract_text_nested_dict():
    data = {"recommendation": {"text": "Nested rec"}}
    assert "Nested rec" in q.extract_text(data)


def test_extract_text_list():
    assert q.extract_text(["a", "b"]) == "a\nb"


def test_extract_text_picks_text_field_when_no_recommendation():
    assert "только text" in q.extract_text({"text": "только text"})


# ===== _count_generated_tokens =====

def test_count_tokens_dict_includes_all_user_fields():
    data = {
        "title": "Один два",          # 2 tokens
        "recommendation": "три четыре пять",  # 3 tokens
        "reason": "шесть",            # 1 token
        "_system": {"task_id": "ignored", "lead_id": "ignored"},
    }
    # Считаем все кроме _system
    assert q._count_generated_tokens(data) == 6


def test_count_tokens_string():
    assert q._count_generated_tokens("hello world test") == 3


def test_count_tokens_none():
    assert q._count_generated_tokens(None) == 0


def test_count_tokens_excludes_service_fields():
    data = {"recommendation": "x y z", "_system": {"a": "long text here"}}
    assert q._count_generated_tokens(data) == 3


# ===== gold dataset =====

@pytest.mark.asyncio
async def test_gold_add_list_update_delete(tmp_path):
    p = tmp_path / "gold.json"
    e1 = await gold_service.add_entry(p, "cold", "Hello cold")
    assert e1["stage"] == "cold"
    assert e1["reference"] == "Hello cold"
    assert e1["id"].startswith("cold-")

    e2 = await gold_service.add_entry(p, "warm", "Hello warm")
    entries = await gold_service.list_entries(p)
    assert len(entries) == 2

    updated = await gold_service.update_entry(
        p, e1["id"], reference="updated cold",
    )
    assert updated["reference"] == "updated cold"

    await gold_service.delete_entry(p, e2["id"])
    entries = await gold_service.list_entries(p)
    assert len(entries) == 1
    assert entries[0]["id"] == e1["id"]


@pytest.mark.asyncio
async def test_gold_invalid_stage(tmp_path):
    p = tmp_path / "gold.json"
    with pytest.raises(ValueError):
        await gold_service.add_entry(p, "bogus", "x")


@pytest.mark.asyncio
async def test_gold_empty_reference(tmp_path):
    p = tmp_path / "gold.json"
    with pytest.raises(ValueError):
        await gold_service.add_entry(p, "cold", "   ")


@pytest.mark.asyncio
async def test_gold_delete_missing(tmp_path):
    p = tmp_path / "gold.json"
    with pytest.raises(KeyError):
        await gold_service.delete_entry(p, "nope")


def test_gold_load_corrupt(tmp_path):
    p = tmp_path / "gold.json"
    p.write_text('[{"stage":"foo","reference":"x"}]', encoding="utf-8")
    # entries with invalid stage are filtered out
    assert gold_service.load(p) == []


# ===== find_valid_leads =====

@pytest.mark.asyncio
async def test_find_valid_leads_picks_valid(fake_rag):
    async def actions(lead_id):
        if lead_id in ("5", "7"):
            return {"lead_id": lead_id, "actions": [{"id": "a"}]}
        return {"lead_id": lead_id, "actions": []}

    fake_rag.get_lead_actions = AsyncMock(side_effect=actions)
    result = await q.find_valid_leads(fake_rag, 1, 10, n=2, max_attempts=10)
    assert len(result["found"]) == 2
    ids = {x["lead_id"] for x in result["found"]}
    assert ids.issubset({"5", "7"})
    assert result["not_enough"] is False


@pytest.mark.asyncio
async def test_find_valid_leads_min_actions(fake_rag):
    """min_actions=3 пропускает лидов с меньшим числом actions."""
    def actions_for(lead_id):
        # лиды 1-3: по 1 action; 4-6: по 5 actions
        count = 5 if int(lead_id) >= 4 else 1
        return {"lead_id": lead_id, "actions": [{"id": str(i)} for i in range(count)]}

    fake_rag.get_lead_actions = AsyncMock(side_effect=lambda lid: actions_for(lid))
    result = await q.find_valid_leads(
        fake_rag, 1, 6, n=2, min_actions=3, max_attempts=20,
    )
    assert len(result["found"]) == 2
    for f in result["found"]:
        assert int(f["lead_id"]) >= 4
        assert f["actions_count"] == 5


@pytest.mark.asyncio
async def test_find_valid_leads_not_enough(fake_rag):
    fake_rag.get_lead_actions = AsyncMock(
        return_value={"lead_id": "x", "actions": []}
    )
    result = await q.find_valid_leads(fake_rag, 1, 3, n=5, max_attempts=10)
    assert result["found"] == []
    assert result["not_enough"] is True


@pytest.mark.asyncio
async def test_find_valid_leads_invalid_range(fake_rag):
    result = await q.find_valid_leads(fake_rag, 10, 5, n=3)
    assert result["found"] == []
    assert result["not_enough"] is True


# ===== async task evaluation =====

@pytest.mark.asyncio
async def test_start_evaluation_completes(tmp_path, settings, fake_rag):
    gold = [
        {"id": "cold-1", "stage": "cold", "reference": "hello world"},
    ]
    p = tmp_path / "gold.json"
    p.write_text(json.dumps(gold), encoding="utf-8")

    settings_copy = type(settings).model_construct(**settings.model_dump())
    settings_copy.quality_gold_dataset_path = str(p)

    fake_rag.generate_recommendation = AsyncMock(
        return_value={"token": "tok", "status": "queued"}
    )
    # data возвращается как dict — extract_text должен вытащить recommendation
    fake_rag.get_recommendations = AsyncMock(return_value={
        "lead_id": "1",
        "recommendations": [{
            "id": "r", "type": "cold",
            "data": {"recommendation": "hello world", "_system": {"task_id": "x"}},
        }],
    })

    with patch.object(q, "call_judge", AsyncMock(return_value=0.9)), \
         patch.object(q, "embed", AsyncMock(return_value=[1.0, 0.0, 0.0])), \
         patch.object(q, "_poll_recommendation", AsyncMock(return_value=True)):
        quality_router._reset_for_tests()
        task_id = await q.start_evaluation(
            fake_rag, settings_copy, lead_ids=["1", "2"],
        )
        for _ in range(50):
            task = q.get_task(task_id)
            if task and task.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.05)

    task = q.get_task(task_id)
    assert task is not None
    assert task.status == "completed"
    assert task.total == 2  # 2 leads × 1 entry
    assert task.done == 2
    assert task.result["metrics"]["samples"] == 2
    assert task.result["metrics"]["samples_failed"] == 0
    assert task.result["metrics"]["samples_total"] == 2
    assert task.result["metrics"]["faithfulness"] == 0.9
    assert all(s["status"] == "ok" for s in task.result["samples"])
    assert QUALITY_FAITHFULNESS._value.get() == 0.9
    assert QUALITY_SAMPLES._value.get() == 2


@pytest.mark.asyncio
async def test_start_evaluation_empty_leads(settings, fake_rag):
    with pytest.raises(ValueError):
        await q.start_evaluation(fake_rag, settings, lead_ids=[])


# ===== HTTP routes =====

def test_quality_routes_require_auth(client):
    quality_router._reset_for_tests()
    assert client.post("/api/quality/tasks", json={"lead_ids": []}).status_code == 401
    assert client.get("/api/quality/tasks").status_code == 401
    assert client.get("/api/quality/latest").status_code == 401
    assert client.get("/api/quality/gold").status_code == 401


def test_quality_latest_no_run(client, auth_headers):
    quality_router._reset_for_tests()
    r = client.get("/api/quality/latest", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "no_run"


def test_gold_crud_endpoints(client, auth_headers, tmp_path, monkeypatch):
    # Use isolated gold dataset for this test
    from app.config import get_settings
    s = get_settings()
    orig = s.quality_gold_dataset_path
    p = tmp_path / "gold.json"
    s.quality_gold_dataset_path = str(p)
    try:
        # list (empty)
        r = client.get("/api/quality/gold", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["entries"] == []

        # create
        r = client.post(
            "/api/quality/gold",
            headers=auth_headers,
            json={"stage": "cold", "reference": "hello"},
        )
        assert r.status_code == 200
        entry_id = r.json()["id"]

        # list (1)
        r = client.get("/api/quality/gold", headers=auth_headers)
        assert len(r.json()["entries"]) == 1

        # update
        r = client.put(
            f"/api/quality/gold/{entry_id}",
            headers=auth_headers,
            json={"reference": "updated"},
        )
        assert r.status_code == 200
        assert r.json()["reference"] == "updated"

        # delete
        r = client.delete(f"/api/quality/gold/{entry_id}", headers=auth_headers)
        assert r.status_code == 200

        # 404 on missing
        r = client.put(
            "/api/quality/gold/missing",
            headers=auth_headers,
            json={"reference": "x"},
        )
        assert r.status_code == 404
    finally:
        s.quality_gold_dataset_path = orig


def test_gold_invalid_stage_rejected(client, auth_headers, tmp_path):
    from app.config import get_settings
    s = get_settings()
    orig = s.quality_gold_dataset_path
    s.quality_gold_dataset_path = str(tmp_path / "gold.json")
    try:
        r = client.post(
            "/api/quality/gold",
            headers=auth_headers,
            json={"stage": "bogus", "reference": "x"},
        )
        assert r.status_code == 400
    finally:
        s.quality_gold_dataset_path = orig


def test_find_leads_endpoint(client, auth_headers, fake_rag):
    fake_rag.get_lead_actions = AsyncMock(return_value={
        "lead_id": "1",
        "actions": [{"id": "a"}],
    })
    r = client.post(
        "/api/quality/leads/find",
        headers=auth_headers,
        json={"min_id": 1, "max_id": 5, "n": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["found"]) >= 1


def test_find_leads_invalid_range(client, auth_headers):
    r = client.post(
        "/api/quality/leads/find",
        headers=auth_headers,
        json={"min_id": 10, "max_id": 5, "n": 2},
    )
    assert r.status_code == 400


def test_start_eval_empty_leads(client, auth_headers):
    r = client.post(
        "/api/quality/tasks",
        headers=auth_headers,
        json={"lead_ids": []},
    )
    assert r.status_code == 400


def test_task_status_404(client, auth_headers):
    r = client.get("/api/quality/tasks/nonexistent", headers=auth_headers)
    assert r.status_code == 404


def test_gold_dataset_file_exists():
    """Sanity: production gold dataset is valid."""
    p = Path(__file__).parent.parent / "app" / "data" / "gold_dataset.json"
    assert p.exists()
    entries = gold_service.load(p)
    assert len(entries) >= 4
    stages = {e["stage"] for e in entries}
    assert stages == {"cold", "warm", "hot", "after_sale"}
