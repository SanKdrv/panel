"""Tests for the quality evaluation pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services import quality as q
from app.services.metrics import (
    QUALITY_ANSWER_RELEVANCE,
    QUALITY_CONTEXT_PRECISION,
    QUALITY_FAITHFULNESS,
    QUALITY_SAMPLES,
    QUALITY_TPS,
)
from app.routers import quality as quality_router


def test_context_precision_full_overlap():
    ref = "Котики молоко"
    gen = "котики и молоко"
    assert q.context_precision(ref, gen) == 1.0


def test_context_precision_partial_overlap():
    # 2 из 3 эталонных слов встречаются в ответе → 0.6667
    ref = "Котики любят молоко"
    gen = "котики и молоко"
    assert q.context_precision(ref, gen) == pytest.approx(2 / 3, abs=0.01)


def test_context_precision_partial():
    ref = "apple banana cherry"
    gen = "apple"
    assert q.context_precision(ref, gen) == pytest.approx(1 / 3, abs=0.01)


def test_context_precision_empty_reference():
    assert q.context_precision("", "anything") == 0.0


def test_context_precision_case_insensitive():
    assert q.context_precision("HELLO", "hello world") == 1.0


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


def test_load_gold_dataset(tmp_path):
    p = tmp_path / "gold.json"
    p.write_text(json.dumps([{"question": "q1", "reference": "r1"}]), encoding="utf-8")
    data = q.load_gold_dataset(p)
    assert data[0]["question"] == "q1"


def test_load_gold_dataset_missing(tmp_path):
    assert q.load_gold_dataset(tmp_path / "missing.json") == []


@pytest.mark.asyncio
async def test_evaluate_no_dataset(tmp_path, settings, fake_rag):
    # Point at an empty file
    settings_copy = type(settings).model_construct(**settings.model_dump())
    settings_copy.quality_gold_dataset_path = str(tmp_path / "absent.json")
    result = await q.evaluate(fake_rag, settings_copy)
    assert result["status"] == "no_dataset"
    assert result["metrics"] is None


@pytest.mark.asyncio
async def test_evaluate_full_run(tmp_path, settings, fake_rag):
    gold = [
        {
            "question": "Что такое RAG?",
            "reference": "RAG это retrieval-augmented generation",
            "lead_id": "test-1",
            "type": "cold",
        },
    ]
    p = tmp_path / "gold.json"
    p.write_text(json.dumps(gold), encoding="utf-8")

    settings_copy = type(settings).model_construct(**settings.model_dump())
    settings_copy.quality_gold_dataset_path = str(p)

    # Mock generation: token + completed + recommendation text
    fake_rag.generate_recommendation = AsyncMock(return_value={"token": "tok", "status": "queued"})
    fake_rag.recommendation_status = AsyncMock(return_value={"status": "completed"})
    fake_rag.get_recommendations = AsyncMock(return_value={
        "lead_id": "test-1",
        "recommendations": [{"id": "r1", "type": "cold", "data": "RAG это retrieval-augmented generation"}],
    })

    async def fake_judge(*args, **kwargs):
        return 0.9

    async def fake_embed(*args, **kwargs):
        return [1.0, 0.0, 0.0]

    with patch.object(q, "call_judge", side_effect=fake_judge), \
         patch.object(q, "embed", side_effect=fake_embed), \
         patch.object(q, "_poll_recommendation", AsyncMock(return_value=True)):
        result = await q.evaluate(fake_rag, settings_copy)

    assert result["status"] == "ok"
    m = result["metrics"]
    assert m["faithfulness"] == 0.9
    # cosine of identical vectors = 1.0
    assert m["answer_relevance"] == pytest.approx(1.0)
    # context precision full overlap
    assert m["context_precision"] > 0.5
    assert m["tps"] > 0
    assert m["samples"] == 1

    # Prometheus gauges should be set
    assert QUALITY_FAITHFULNESS._value.get() == 0.9
    assert QUALITY_SAMPLES._value.get() == 1


def test_quality_routes_require_auth(client):
    quality_router._reset_for_tests()
    assert client.post("/api/quality/evaluate").status_code == 401
    assert client.get("/api/quality/latest").status_code == 401


def test_quality_latest_no_run(client, auth_headers):
    quality_router._reset_for_tests()
    r = client.get("/api/quality/latest", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "no_run"
    assert body["metrics"] is None
    assert "faithfulness" in body["odz"]


def test_quality_evaluate_endpoint(client, auth_headers, fake_rag, tmp_path):
    """Trigger /evaluate via TestClient with mocked judge/embed."""
    quality_router._reset_for_tests()
    gold_path = Path(__file__).parent.parent / "app" / "data" / "gold_dataset.json"
    assert gold_path.exists()

    async def fake_judge(*a, **kw):
        return 0.85

    async def fake_embed(*a, **kw):
        return [0.5, 0.5, 0.5]

    with patch.object(q, "call_judge", side_effect=fake_judge), \
         patch.object(q, "embed", side_effect=fake_embed), \
         patch.object(q, "_poll_recommendation", AsyncMock(return_value=True)):
        r = client.post("/api/quality/evaluate", headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "no_samples")

    r2 = client.get("/api/quality/latest", headers=auth_headers)
    assert r2.status_code == 200
