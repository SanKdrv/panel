"""Персистентное хранение завершённых quality-таск.

Каждая завершённая task сериализуется в `runs/<task_id>.json`.
При старте бэка последние ~50 файлов подгружаются обратно в _tasks.
Самые старые файлы автоматически удаляются после превышения лимита.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .quality import TaskState

logger = logging.getLogger(__name__)

RUNS_DIR_DEFAULT = Path(__file__).parent.parent / "data" / "runs"
MAX_FILES = 200
LOAD_ON_STARTUP = 50


def _runs_dir() -> Path:
    path = Path(os.environ.get("QUALITY_RUNS_DIR", str(RUNS_DIR_DEFAULT)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _task_to_serializable(task: "TaskState") -> dict:
    return {
        "id": task.id,
        "status": task.status,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "total": task.total,
        "done": task.done,
        "current_step": task.current_step,
        "error": task.error,
        "result": task.result,
        "cancelled": task.cancelled,
        "samples": task.samples,
    }


def save_task(task: "TaskState") -> None:
    """Сохранить task в runs/<id>.json. Безопасно к ошибкам."""
    try:
        path = _runs_dir() / f"{task.id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(_task_to_serializable(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)
        logger.info("event=quality.history.saved task=%s path=%s",
                    task.id, path)
        _cleanup_old_files()
    except Exception as exc:
        logger.warning("event=quality.history.save_error task=%s err=%s",
                       task.id, exc)


def _cleanup_old_files() -> None:
    """Удалить самые старые файлы, если их больше MAX_FILES."""
    try:
        files = sorted(
            _runs_dir().glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if len(files) <= MAX_FILES:
            return
        for old in files[MAX_FILES:]:
            try:
                old.unlink()
                logger.info("event=quality.history.cleanup removed=%s", old.name)
            except Exception as exc:
                logger.warning("event=quality.history.cleanup.error file=%s err=%s",
                               old.name, exc)
    except Exception as exc:
        logger.warning("event=quality.history.cleanup_error err=%s", exc)


def load_recent(limit: int = LOAD_ON_STARTUP) -> list[dict]:
    """Загрузить последние N тасок из файлов. Возвращает список сериализованных
    dict'ов (а не TaskState — десериализация делается в caller)."""
    try:
        files = sorted(
            _runs_dir().glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        loaded: list[dict] = []
        for f in files:
            try:
                loaded.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception as exc:
                logger.warning("event=quality.history.load_one.error file=%s err=%s",
                               f.name, exc)
        logger.info("event=quality.history.loaded count=%d", len(loaded))
        return loaded
    except Exception as exc:
        logger.warning("event=quality.history.load_error err=%s", exc)
        return []
