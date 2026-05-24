"""RAG quality evaluation pipeline (v2).

Изменения относительно v1:
- Per-stage эталоны вместо question/reference пар (без поля question).
- Поддержка списка lead_ids — картезиан (lead × gold entry).
- Асинхронные таски с прогрессом (для длинных прогонов).
- Detail на каждую сгенерированную пару (для дрилл-дауна в UI).
- Без изменений: Faithfulness (LLM-as-judge), Answer Relevance (cosine),
  Context Precision (keyword overlap), TPS, публикация в Prometheus.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings
from . import gold_dataset as gold_service
from .metrics import (
    QUALITY_ANSWER_RELEVANCE,
    QUALITY_CONTEXT_PRECISION,
    QUALITY_FAITHFULNESS,
    QUALITY_RUN_TIMESTAMP,
    QUALITY_SAMPLES,
    QUALITY_TPS,
)
from .rag_client import RAGClient

logger = logging.getLogger(__name__)

ODZ = {
    "faithfulness": 0.80,
    "answer_relevance": 0.75,
    "context_precision": 0.70,
    "tps": 5.0,
}

JUDGE_PROMPT_TEMPLATE = (
    "Ты — беспристрастный эксперт. Сравни СГЕНЕРИРОВАННЫЙ ответ с ЭТАЛОНОМ "
    "для соответствующей стадии воронки продаж ({stage}). Оцени, насколько "
    "сгенерированный ответ передаёт основные идеи и фактологию эталона, "
    "по шкале от 0.0 до 1.0, где 1.0 = все ключевые утверждения эталона "
    "поддержаны в ответе, 0.0 = совсем не пересекаются. Учти, что ответ "
    "может быть стилистически другим — оценивай содержание, а не форму. "
    "Верни одно число в формате десятичной дроби, без пояснений.\n\n"
    "ЭТАЛОН: {reference}\n"
    "СГЕНЕРИРОВАННЫЙ ОТВЕТ: {generated}\n\n"
    "ОЦЕНКА:"
)


# ---------- helpers ----------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.lower())


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def context_precision(reference: str, generated: str) -> float:
    ref_tokens = set(_tokenize(reference))
    gen_tokens = set(_tokenize(generated))
    if not ref_tokens:
        return 0.0
    return round(len(ref_tokens & gen_tokens) / len(ref_tokens), 4)


async def call_judge(
    client: httpx.AsyncClient, url: str, model: str,
    stage: str, reference: str, generated: str,
) -> float:
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        stage=stage, reference=reference, generated=generated,
    )
    try:
        resp = await client.post(
            f"{url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120.0,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        match = re.search(r"[01](?:\.\d+)?", text)
        if not match:
            logger.warning("event=quality.judge.no_score raw=%r", text[:100])
            return 0.0
        return max(0.0, min(1.0, float(match.group(0))))
    except Exception as exc:
        logger.warning("event=quality.judge.error error=%s", exc)
        return 0.0


async def embed(
    client: httpx.AsyncClient, url: str, model: str, text: str,
) -> list[float]:
    try:
        resp = await client.post(
            f"{url.rstrip('/')}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("embedding", [])
    except Exception as exc:
        logger.warning("event=quality.embed.error error=%s", exc)
        return []


def load_gold_dataset(path) -> list[dict]:
    return gold_service.load(path)


async def _poll_recommendation(
    rag: RAGClient, token: str, timeout_s: float = 600.0, poll_interval: float = 5.0,
) -> bool:
    started = time.monotonic()
    while time.monotonic() - started < timeout_s:
        await asyncio.sleep(poll_interval)
        data = await rag.recommendation_status(token)
        if data.get("status") == "completed":
            return True
        if data.get("status") == "failed":
            return False
    return False


# ---------- task registry ----------

@dataclass
class TaskState:
    id: str
    status: str = "queued"             # queued | running | completed | failed
    started_at: str | None = None
    finished_at: str | None = None
    total: int = 0
    done: int = 0
    current_step: str = ""
    result: dict | None = None
    error: str | None = None
    cancelled: bool = False
    samples: list[dict] = field(default_factory=list)


_tasks: dict[str, TaskState] = {}
_tasks_lock = asyncio.Lock()


def get_task(task_id: str) -> TaskState | None:
    return _tasks.get(task_id)


def list_tasks(limit: int = 20) -> list[TaskState]:
    items = sorted(_tasks.values(), key=lambda t: t.started_at or "", reverse=True)
    return items[:limit]


def _reset_for_tests() -> None:
    global _tasks
    _tasks = {}


# ---------- find leads ----------

async def find_valid_leads(
    rag: RAGClient,
    min_id: int,
    max_id: int,
    n: int,
    max_attempts: int | None = None,
) -> dict:
    """Случайно выбирает lead_id из [min, max], проверяет через
    /recommendations/actions/{id}. Считает лид валидным, если ответ 2xx
    и actions непустой. Возвращает первые n валидных + cтатистику."""
    import random
    if min_id > max_id or n <= 0:
        return {"found": [], "attempts": 0, "requested": n, "not_enough": True}

    pool = list(range(min_id, max_id + 1))
    random.shuffle(pool)
    if max_attempts is None:
        max_attempts = min(len(pool), max(n * 5, 25))

    found: list[dict] = []
    attempts = 0

    for lead_id in pool:
        if len(found) >= n or attempts >= max_attempts:
            break
        attempts += 1
        try:
            data = await rag.get_lead_actions(str(lead_id))
            actions = data.get("actions") or []
            if actions:
                found.append({
                    "lead_id": str(lead_id),
                    "actions_count": len(actions),
                })
        except Exception as exc:
            logger.debug("event=find_leads.skip lead_id=%s err=%s", lead_id, exc)
            continue

    return {
        "found": found,
        "attempts": attempts,
        "requested": n,
        "not_enough": len(found) < n,
    }


# ---------- evaluation ----------

async def _evaluate_one_pair(
    rag: RAGClient,
    judge_client: httpx.AsyncClient,
    settings: Settings,
    lead_id: str,
    entry: dict,
) -> dict | None:
    """Один прогон (один лид × одна gold-запись). Возвращает sample dict
    или None если генерация не удалась."""
    stage = entry["stage"]
    reference = entry["reference"]

    t0 = time.monotonic()
    try:
        gen = await rag.generate_recommendation(lead_id, stage)
        token = gen.get("token", "")
        ok = await _poll_recommendation(rag, token)
        if not ok:
            return None
        recs = await rag.get_recommendations(lead_id)
        items = recs.get("recommendations", [])
        if not items:
            return None
        generated = str(items[0].get("data", ""))
    except Exception as exc:
        logger.warning("event=quality.gen.error lead=%s err=%s", lead_id, exc)
        return None

    duration = max(time.monotonic() - t0, 0.001)
    tokens = max(len(_tokenize(generated)), 1)
    tps = tokens / duration

    faith = await call_judge(
        judge_client,
        settings.quality_judge_url, settings.quality_judge_model,
        stage, reference, generated,
    )
    ref_emb, gen_emb = await asyncio.gather(
        embed(judge_client, settings.quality_embedding_url,
              settings.quality_embedding_model, reference),
        embed(judge_client, settings.quality_embedding_url,
              settings.quality_embedding_model, generated),
    )
    relevance = _cosine(ref_emb, gen_emb)
    precision = context_precision(reference, generated)

    return {
        "lead_id": lead_id,
        "entry_id": entry["id"],
        "stage": stage,
        "reference": reference,
        "generated": generated,
        "faithfulness": faith,
        "answer_relevance": relevance,
        "context_precision": precision,
        "tps": round(tps, 3),
        "tokens": tokens,
        "duration_s": round(duration, 2),
    }


def _aggregate(samples: list[dict]) -> dict:
    if not samples:
        return {
            "faithfulness": 0.0, "answer_relevance": 0.0,
            "context_precision": 0.0, "tps": 0.0, "samples": 0,
        }
    n = len(samples)
    return {
        "faithfulness":       round(sum(s["faithfulness"] for s in samples) / n, 4),
        "answer_relevance":   round(sum(s["answer_relevance"] for s in samples) / n, 4),
        "context_precision":  round(sum(s["context_precision"] for s in samples) / n, 4),
        "tps":                round(sum(s["tps"] for s in samples) / n, 4),
        "samples":            n,
    }


def _publish_to_prometheus(metrics: dict, finished_at: datetime) -> None:
    QUALITY_FAITHFULNESS.set(metrics["faithfulness"])
    QUALITY_ANSWER_RELEVANCE.set(metrics["answer_relevance"])
    QUALITY_CONTEXT_PRECISION.set(metrics["context_precision"])
    QUALITY_TPS.set(metrics["tps"])
    QUALITY_SAMPLES.set(metrics["samples"])
    QUALITY_RUN_TIMESTAMP.set(finished_at.timestamp())


async def _run_evaluation_task(
    task_id: str,
    rag: RAGClient,
    settings: Settings,
    lead_ids: list[str],
    gold_entries: list[dict],
) -> None:
    task = _tasks[task_id]
    task.status = "running"
    task.started_at = datetime.now(timezone.utc).isoformat()
    task.total = len(lead_ids) * len(gold_entries)
    task.done = 0

    samples: list[dict] = []
    async with httpx.AsyncClient() as judge_client:
        for lead_id in lead_ids:
            for entry in gold_entries:
                if task.cancelled:
                    break
                task.current_step = f"lead {lead_id} × {entry['stage']}"
                logger.info("event=quality.task.step task=%s lead=%s stage=%s",
                            task_id, lead_id, entry["stage"])
                sample = await _evaluate_one_pair(
                    rag, judge_client, settings, lead_id, entry,
                )
                task.done += 1
                if sample:
                    samples.append(sample)
                    task.samples.append(sample)
            if task.cancelled:
                break

    finished = datetime.now(timezone.utc)
    task.finished_at = finished.isoformat()

    if not samples:
        task.status = "failed" if not task.cancelled else "completed"
        task.error = "no successful samples" if not task.cancelled else None
        task.result = {
            "status": "no_samples",
            "metrics": None,
            "odz": ODZ,
            "lead_ids": lead_ids,
            "samples": [],
        }
        return

    metrics = _aggregate(samples)
    _publish_to_prometheus(metrics, finished)

    task.status = "completed"
    task.result = {
        "status": "ok",
        "metrics": metrics,
        "odz": ODZ,
        "lead_ids": lead_ids,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "samples": samples,
    }


async def start_evaluation(
    rag: RAGClient,
    settings: Settings,
    lead_ids: list[str],
    stages: list[str] | None = None,
) -> str:
    """Запускает evaluation в background, возвращает task_id."""
    entries = gold_service.load(settings.quality_gold_dataset_path)
    entries = gold_service.filter_by_stages(entries, stages)
    if not entries:
        raise ValueError("gold dataset is empty (no matching entries)")
    if not lead_ids:
        raise ValueError("lead_ids must not be empty")

    task_id = uuid.uuid4().hex[:12]
    async with _tasks_lock:
        _tasks[task_id] = TaskState(id=task_id)

    asyncio.create_task(
        _run_evaluation_task(task_id, rag, settings, lead_ids, entries)
    )
    return task_id


async def cancel_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if not task or task.status not in ("queued", "running"):
        return False
    task.cancelled = True
    return True


# ---------- backward-compat synchronous entry point (used in tests) ----------

async def evaluate(rag: RAGClient, settings: Settings) -> dict:
    """Синхронная оценка — раннер использует все эталоны и дефолтный лид."""
    entries = gold_service.load(settings.quality_gold_dataset_path)
    if not entries:
        return {
            "status": "no_dataset",
            "metrics": None, "odz": ODZ,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 0.0,
        }

    samples: list[dict] = []
    started = datetime.now(timezone.utc)
    async with httpx.AsyncClient() as judge_client:
        for entry in entries:
            sample = await _evaluate_one_pair(
                rag, judge_client, settings, "quality-eval", entry,
            )
            if sample:
                samples.append(sample)
    finished = datetime.now(timezone.utc)

    if not samples:
        return {
            "status": "no_samples",
            "metrics": None, "odz": ODZ,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": (finished - started).total_seconds(),
        }

    metrics = _aggregate(samples)
    _publish_to_prometheus(metrics, finished)
    return {
        "status": "ok",
        "metrics": metrics,
        "odz": ODZ,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 2),
        "samples": samples,
    }
