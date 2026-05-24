"""Tests for quality history persistence."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services import quality_history
from app.services.quality import TaskState


@pytest.fixture
def tmp_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("QUALITY_RUNS_DIR", str(tmp_path))
    return tmp_path


def _make_task(tid: str = "t1") -> TaskState:
    return TaskState(
        id=tid,
        status="completed",
        started_at="2026-05-24T10:00:00+00:00",
        finished_at="2026-05-24T10:01:00+00:00",
        total=1, done=1,
        result={"status": "ok", "metrics": {"samples": 1}},
        samples=[{"lead_id": "1", "stage": "cold", "status": "ok"}],
    )


def test_save_and_load(tmp_runs):
    task = _make_task("abc")
    quality_history.save_task(task)
    assert (tmp_runs / "abc.json").exists()

    loaded = quality_history.load_recent(limit=10)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "abc"
    assert loaded[0]["result"]["metrics"]["samples"] == 1


def test_cleanup_keeps_only_max_files(tmp_runs, monkeypatch):
    monkeypatch.setattr(quality_history, "MAX_FILES", 5)
    for i in range(10):
        quality_history.save_task(_make_task(f"task-{i:02d}"))
    # Должно остаться ровно 5 файлов
    files = list(tmp_runs.glob("*.json"))
    assert len(files) == 5


def test_load_recent_orders_by_mtime(tmp_runs):
    import time
    quality_history.save_task(_make_task("old"))
    time.sleep(0.05)
    quality_history.save_task(_make_task("new"))
    loaded = quality_history.load_recent(limit=10)
    assert loaded[0]["id"] == "new"
    assert loaded[1]["id"] == "old"


def test_load_recent_limit(tmp_runs):
    for i in range(5):
        quality_history.save_task(_make_task(f"t{i}"))
    loaded = quality_history.load_recent(limit=3)
    assert len(loaded) == 3


def test_load_recent_skips_corrupt_files(tmp_runs):
    quality_history.save_task(_make_task("ok"))
    (tmp_runs / "broken.json").write_text("not json", encoding="utf-8")
    loaded = quality_history.load_recent(limit=10)
    # 1 валидный, повреждённый пропустили
    assert len(loaded) == 1
    assert loaded[0]["id"] == "ok"


def test_load_recent_empty_dir(tmp_runs):
    assert quality_history.load_recent(limit=10) == []
