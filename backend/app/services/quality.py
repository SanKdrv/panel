"""RAG quality evaluation pipeline (v2).

Изменения относительно v1:
- Per-stage эталоны вместо question/reference пар (без поля question).
- Поддержка списка lead_ids — картезиан (lead × gold entry).
- Асинхронные таски с прогрессом (для длинных прогонов).
- Detail на каждую сгенерированную пару (для дрилл-дауна в UI).
- Без изменений: Reference Alignment (LLM-as-judge), Answer Relevance (cosine),
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
from . import quality_history
from .metrics import (
    QUALITY_ANSWER_RELEVANCE,
    QUALITY_CONTEXT_PRECISION,
    QUALITY_REFERENCE_ALIGNMENT,
    QUALITY_RUN_TIMESTAMP,
    QUALITY_SAMPLES,
    QUALITY_TPS,
)
from .rag_client import RAGClient

logger = logging.getLogger(__name__)

ODZ = {
    "reference_alignment": 0.80,
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


# Поля, которые не считаем за «сгенерированный моделью контент» (служебные).
_NON_GENERATED_FIELDS = {"_system", "system", "task_id", "lead_id", "type", "id"}


def _count_generated_tokens(data) -> int:
    """Считает токены всего, что реально сгенерировала модель — все
    непустые текстовые поля raw_data кроме служебных (_system и т.п.).
    Используется для TPS, чтобы не занижать скорость генератора."""
    if data is None:
        return 0
    if isinstance(data, str):
        return len(_tokenize(data))
    if isinstance(data, list):
        return sum(_count_generated_tokens(x) for x in data)
    if isinstance(data, dict):
        total = 0
        for k, v in data.items():
            if k in _NON_GENERATED_FIELDS:
                continue
            if isinstance(v, str):
                total += len(_tokenize(v))
            elif isinstance(v, (dict, list)):
                total += _count_generated_tokens(v)
        return max(total, 1)
    return len(_tokenize(str(data)))


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
    full_url = f"{url.rstrip('/')}/api/embeddings"
    try:
        resp = await client.post(
            full_url,
            json={"model": model, "prompt": text},
            timeout=60.0,
        )
        if resp.is_error:
            logger.warning(
                "event=quality.embed.http_error url=%s model=%s status=%s body=%r",
                full_url, model, resp.status_code, resp.text[:300],
            )
            return []
        data = resp.json()
        emb = data.get("embedding") or []
        if not emb:
            logger.warning(
                "event=quality.embed.empty url=%s model=%s response_keys=%s body=%r",
                full_url, model, list(data.keys()), resp.text[:300],
            )
        return emb
    except Exception as exc:
        logger.warning(
            "event=quality.embed.error url=%s model=%s exc_type=%s err=%s",
            full_url, model, type(exc).__name__, exc or "(пусто)",
        )
        return []


def load_gold_dataset(path) -> list[dict]:
    return gold_service.load(path)


# Поля, в которых может лежать текст рекомендации внутри data dict.
_TEXT_FIELDS_ORDERED = ("recommendation", "text", "answer", "message", "content")
# Поля контекста, которые добавляются к основному тексту перед сравнением.
# Сейчас пусто: title — это название статьи/контента, на который ссылается
# RAG (метаинформация), recommendation уже упоминает его внутри текста.
# Эталоны таких заголовков не содержат, поэтому включение title только
# зашумляло Context Precision.
_CONTEXT_FIELDS: tuple[str, ...] = ()
# Поля, которые игнорируем (служебные / не пользовательский текст).
_SKIP_FIELDS = {
    "_system", "system", "task_id", "lead_id", "type", "id",
    "title", "reason", "explanation", "rationale",
}


def extract_text(data) -> str:
    """Извлекает осмысленный текст из data, который вернула RAG API.

    RAG возвращает рекомендацию как dict с разными полями. Раньше мы
    делали str(data), и в текст шла Python-репрезентация словаря со
    служебными ключами — это убивало метрики качества.

    Стратегия:
    - str/None → возвращаем как есть
    - dict → берём первое непустое из _TEXT_FIELDS_ORDERED как основу,
      опционально префиксуем title/reason. Если ни одного известного
      текстового поля нет — конкатим все строковые значения, кроме
      служебных полей.
    - list → объединяем элементы через перевод строки
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "\n".join(extract_text(x) for x in data if x is not None).strip()
    if isinstance(data, dict):
        # 1) Главный текстовый ключ
        main_text = ""
        for k in _TEXT_FIELDS_ORDERED:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                main_text = v.strip()
                break
            if isinstance(v, (dict, list)):
                inner = extract_text(v)
                if inner:
                    main_text = inner
                    break

        if main_text:
            parts: list[str] = []
            for k in _CONTEXT_FIELDS:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
            parts.append(main_text)
            return "\n".join(parts)

        # 2) Fallback: соберём все string-значения, кроме служебных
        chunks: list[str] = []
        for k, v in data.items():
            if k in _SKIP_FIELDS:
                continue
            if isinstance(v, str) and v.strip():
                chunks.append(v.strip())
            elif isinstance(v, (dict, list)):
                inner = extract_text(v)
                if inner:
                    chunks.append(inner)
        return "\n".join(chunks)
    # 3) Числа и прочее — просто str()
    return str(data)


async def _poll_recommendation(
    rag: RAGClient, token: str, timeout_s: float = 900.0, poll_interval: float = 5.0,
) -> str:
    """Опрашивает статус генерации. Возвращает one of:
    - "completed" — успех
    - "failed"    — RAG сообщил о фейле
    - "timeout"   — превысили общий timeout
    - "errors"    — слишком много подряд сетевых ошибок"""
    started = time.monotonic()
    consecutive_errors = 0
    while time.monotonic() - started < timeout_s:
        await asyncio.sleep(poll_interval)
        try:
            data = await rag.recommendation_status(token)
            consecutive_errors = 0
            status = data.get("status")
            if status == "completed":
                return "completed"
            if status == "failed":
                return "failed"
        except Exception as exc:
            consecutive_errors += 1
            logger.warning(
                "event=quality.poll.error token=%s consecutive=%d exc_type=%s err=%s",
                token, consecutive_errors, type(exc).__name__, exc or "(пусто)",
            )
            if consecutive_errors >= 10:
                logger.error("event=quality.poll.give_up token=%s", token)
                return "errors"
            # продолжаем — может быть временный сетевой блип
    return "timeout"


# ---------- services diagnostic ----------

async def _diagnose_services(
    client: httpx.AsyncClient, settings: Settings,
) -> None:
    """Однократный пинг judge и embedder в начале прогона.
    Только логирование — не падаем, даже если оба недоступны."""
    # Embedder
    try:
        r = await client.post(
            f"{settings.quality_embedding_url.rstrip('/')}/api/embeddings",
            json={"model": settings.quality_embedding_model, "prompt": "ping"},
            timeout=15.0,
        )
        r.raise_for_status()
        emb = r.json().get("embedding", [])
        logger.info(
            "event=quality.diag.embedder url=%s model=%s ok=%s dim=%s",
            settings.quality_embedding_url, settings.quality_embedding_model,
            bool(emb), len(emb),
        )
    except Exception as exc:
        logger.warning(
            "event=quality.diag.embedder.error url=%s model=%s err=%s",
            settings.quality_embedding_url, settings.quality_embedding_model, exc,
        )

    # Judge
    try:
        r = await client.post(
            f"{settings.quality_judge_url.rstrip('/')}/api/generate",
            json={
                "model": settings.quality_judge_model,
                "prompt": "Respond with the single number 0.5",
                "stream": False,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        logger.info(
            "event=quality.diag.judge url=%s model=%s ok=%s preview=%r",
            settings.quality_judge_url, settings.quality_judge_model,
            bool(text), text[:60],
        )
    except Exception as exc:
        logger.warning(
            "event=quality.diag.judge.error url=%s model=%s err=%s",
            settings.quality_judge_url, settings.quality_judge_model, exc,
        )


# ---------- task registry ----------

@dataclass
class TaskState:
    id: str
    status: str = "queued"             # queued | running | completed | failed | cancelled
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


def load_history_on_startup() -> int:
    """Вызывается из main.py при старте бэка. Загружает последние таски
    из runs/ в _tasks. Возвращает количество загруженных."""
    loaded = quality_history.load_recent()
    for d in loaded:
        try:
            t = TaskState(
                id=d["id"],
                status=d.get("status", "completed"),
                started_at=d.get("started_at"),
                finished_at=d.get("finished_at"),
                total=d.get("total", 0),
                done=d.get("done", 0),
                current_step=d.get("current_step", ""),
                result=d.get("result"),
                error=d.get("error"),
                cancelled=d.get("cancelled", False),
                samples=d.get("samples", []),
            )
            _tasks[t.id] = t
        except Exception as exc:
            logger.warning("event=quality.history.deserialize_error err=%s", exc)
    return len(_tasks)


def _reset_for_tests() -> None:
    global _tasks
    _tasks = {}


# ---------- find leads ----------

# ---------- lead search (async task) ----------

@dataclass
class LeadSearchState:
    id: str
    status: str = "running"            # running | done | cancelled
    started_at: str = ""
    finished_at: str | None = None
    found: list[dict] = field(default_factory=list)
    attempts: int = 0
    max_attempts: int = 0
    target_n: int = 0
    min_id: int = 0
    max_id: int = 0
    min_actions: int = 1
    cancelled: bool = False
    error: str | None = None


_lead_searches: dict[str, LeadSearchState] = {}


def get_lead_search(search_id: str) -> LeadSearchState | None:
    return _lead_searches.get(search_id)


def cancel_lead_search(search_id: str) -> bool:
    s = _lead_searches.get(search_id)
    if not s or s.status != "running":
        return False
    s.cancelled = True
    return True


async def start_lead_search(
    rag: RAGClient,
    min_id: int,
    max_id: int,
    n: int,
    min_actions: int = 1,
) -> str:
    if min_id > max_id or n <= 0 or min_actions < 1:
        raise ValueError("invalid search params")

    import random
    search_id = uuid.uuid4().hex[:12]
    pool = list(range(min_id, max_id + 1))
    random.shuffle(pool)
    max_attempts = min(len(pool), max(n * 5 * min_actions, 25))

    state = LeadSearchState(
        id=search_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        target_n=n, min_id=min_id, max_id=max_id, min_actions=min_actions,
        max_attempts=max_attempts,
    )
    _lead_searches[search_id] = state

    asyncio.create_task(_run_lead_search(rag, state, pool))
    return search_id


async def _run_lead_search(
    rag: RAGClient,
    state: LeadSearchState,
    pool: list[int],
) -> None:
    try:
        for lead_id in pool:
            if state.cancelled:
                break
            if len(state.found) >= state.target_n:
                break
            if state.attempts >= state.max_attempts:
                break
            state.attempts += 1
            try:
                data = await rag.get_lead_actions(str(lead_id))
                actions = data.get("actions") or []
                if len(actions) >= state.min_actions:
                    state.found.append({
                        "lead_id": str(lead_id),
                        "actions_count": len(actions),
                    })
            except Exception as exc:
                logger.debug("event=find_leads.skip lead_id=%s err=%s", lead_id, exc)
                continue
    except Exception as exc:
        logger.exception("event=find_leads.task_error search=%s", state.id)
        state.error = _fmt_exc(exc)
    finally:
        state.finished_at = datetime.now(timezone.utc).isoformat()
        state.status = "cancelled" if state.cancelled else "done"


def _reset_lead_searches_for_tests() -> None:
    global _lead_searches
    _lead_searches = {}


# ---------- legacy synchronous (used in test) ----------

async def find_valid_leads(
    rag: RAGClient,
    min_id: int,
    max_id: int,
    n: int,
    min_actions: int = 1,
    max_attempts: int | None = None,
) -> dict:
    """Случайно выбирает lead_id из [min, max], проверяет через
    /recommendations/actions/{id}. Считает лид валидным, если ответ 2xx
    и в actions >= min_actions записей. Возвращает первые n валидных
    + статистику."""
    import random
    if min_id > max_id or n <= 0 or min_actions < 1:
        return {
            "found": [], "attempts": 0, "requested": n,
            "min_actions": min_actions, "not_enough": True,
        }

    pool = list(range(min_id, max_id + 1))
    random.shuffle(pool)
    if max_attempts is None:
        # Чем выше min_actions, тем больше попыток допускаем.
        max_attempts = min(len(pool), max(n * 5 * min_actions, 25))

    found: list[dict] = []
    attempts = 0

    for lead_id in pool:
        if len(found) >= n or attempts >= max_attempts:
            break
        attempts += 1
        try:
            data = await rag.get_lead_actions(str(lead_id))
            actions = data.get("actions") or []
            if len(actions) >= min_actions:
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
        "min_actions": min_actions,
        "not_enough": len(found) < n,
    }


# ---------- evaluation ----------

async def _call_with_retry(coro_factory, *, what: str, attempts: int = 3,
                           base_delay: float = 2.0):
    """Вызывает coroutine-фабрику с экспоненциальным retry на сетевых ошибках.
    coro_factory — функция, возвращающая новый awaitable при каждом вызове."""
    last_exc: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "event=quality.retry what=%s attempt=%d/%d exc_type=%s err=%s",
                what, i, attempts, type(exc).__name__, exc or "(пусто)",
            )
            if i < attempts:
                await asyncio.sleep(base_delay * i)
    assert last_exc is not None
    raise last_exc


def _fmt_exc(exc: Exception) -> str:
    msg = str(exc).strip()
    if not msg:
        msg = "(без сообщения)"
    return f"{type(exc).__name__}: {msg}"


async def _evaluate_one_pair(
    rag: RAGClient,
    judge_client: httpx.AsyncClient,
    settings: Settings,
    lead_id: str,
    entry: dict,
) -> dict:
    """Один прогон (один лид × одна gold-запись). Всегда возвращает sample dict.
    Если генерация не удалась — sample имеет status='failed' и причину в error.
    Иначе status='ok' и все метрики посчитаны."""
    stage = entry["stage"]
    reference = entry["reference"]
    base = {
        "lead_id": lead_id,
        "entry_id": entry["id"],
        "stage": stage,
        "reference": reference,
    }

    t0 = time.monotonic()
    try:
        gen = await _call_with_retry(
            lambda: rag.generate_recommendation(lead_id, stage),
            what=f"generate(lead={lead_id},stage={stage})",
        )
        token = gen.get("token", "")
        if not token:
            return {**base, "status": "failed",
                    "error": "RAG не вернул token при /generate"}
        # Снэпшот существующих рекомендаций ДО polling — чтобы потом
        # отличить «нашу» новую от старых.
        try:
            pre = await rag.get_recommendations(lead_id)
            pre_ids = {r.get("id") for r in pre.get("recommendations", [])}
        except Exception:
            pre_ids = set()

        poll_status = await _poll_recommendation(rag, token)
        logger.info("event=quality.poll.done token=%s status=%s", token, poll_status)

        recovery_note: str | None = None
        recovered = False
        if poll_status != "completed":
            # RAG сообщил failed/timeout/errors. Но он мог соврать — генерация
            # могла довестись чуть позже. Ждём 30 секунд и заглядываем
            # в /recommendations, ищем НОВУЮ запись (которой не было до /generate).
            recovery_note = (
                f"poll вернул {poll_status}, ждём 30 с и проверяем "
                f"список рекомендаций"
            )
            logger.warning(
                "event=quality.recover.attempt token=%s lead=%s stage=%s reason=%s",
                token, lead_id, stage, poll_status,
            )
            await asyncio.sleep(30)

        try:
            recs = await _call_with_retry(
                lambda: rag.get_recommendations(lead_id),
                what=f"get_recommendations(lead={lead_id})",
            )
        except Exception as exc:
            if poll_status != "completed":
                return {**base, "status": "failed",
                        "error": f"poll={poll_status}; get_recommendations: {_fmt_exc(exc)}"}
            raise

        items = recs.get("recommendations", [])
        if not items:
            return {**base, "status": "failed",
                    "error": f"GET /recommendations пуст; poll={poll_status}"}

        new_items = [r for r in items if r.get("id") not in pre_ids]
        if not new_items and poll_status != "completed":
            # Никаких новых записей не появилось даже после паузы — настоящий fail
            logger.info(
                "event=quality.recover.empty lead=%s stage=%s — новых записей нет",
                lead_id, stage,
            )
            return {**base, "status": "failed",
                    "error": (
                        f"poll={poll_status}; за 30 с после фейла "
                        f"новых рекомендаций не появилось"
                    )}

        chosen = new_items[0] if new_items else items[0]
        if poll_status != "completed" and new_items:
            # Зафиксировали восстановление: poll сказал fail, но мы нашли
            # фактически сгенерированную RAG'ом новую рекомендацию.
            recovered = True
            logger.info(
                "event=quality.recover.ok lead=%s stage=%s new_id=%s",
                lead_id, stage, chosen.get("id"),
            )
        elif not new_items:
            recovery_note = (recovery_note or "") + "; новых записей нет, взяли первую"

        raw_data = chosen.get("data")
        generated = extract_text(raw_data)
        if not generated.strip():
            return {**base, "status": "failed",
                    "error": f"не удалось извлечь текст из data (poll={poll_status})"}
    except Exception as exc:
        logger.warning(
            "event=quality.gen.error lead=%s stage=%s exc_type=%s err=%s",
            lead_id, stage, type(exc).__name__, exc or "(пусто)",
        )
        return {**base, "status": "failed",
                "error": f"исключение при генерации: {_fmt_exc(exc)}"}

    duration = max(time.monotonic() - t0, 0.001)
    # TPS считаем по ВСЕМ сгенерированным моделью данным (включая title,
    # reason и прочие поля кроме служебного _system), а не только по
    # пользовательскому тексту — это честная метрика производительности
    # генератора. Для сравнения с эталоном используется `generated`,
    # для TPS — все непустые текстовые поля raw_data.
    tokens_for_tps = _count_generated_tokens(raw_data)
    tokens = max(len(_tokenize(generated)), 1)
    tps = tokens_for_tps / duration

    # Reference Alignment (бывш. Faithfulness)
    faith = await call_judge(
        judge_client,
        settings.quality_judge_url, settings.quality_judge_model,
        stage, reference, generated,
    )

    # Answer Relevance — c диагностикой пустых эмбеддингов
    ref_emb, gen_emb = await asyncio.gather(
        embed(judge_client, settings.quality_embedding_url,
              settings.quality_embedding_model, reference),
        embed(judge_client, settings.quality_embedding_url,
              settings.quality_embedding_model, generated),
    )
    diag: list[str] = []
    if recovery_note:
        diag.append(recovery_note)
    if not ref_emb:
        diag.append("embed(reference) вернул пусто")
    if not gen_emb:
        diag.append("embed(generated) вернул пусто")
    if ref_emb and gen_emb and len(ref_emb) != len(gen_emb):
        diag.append(f"размерности эмбеддингов не совпадают: {len(ref_emb)} vs {len(gen_emb)}")
    relevance = _cosine(ref_emb, gen_emb)

    precision = context_precision(reference, generated)

    sample = {
        **base,
        "status": "ok",
        "recovered": recovered,
        "generated": generated,
        "reference_alignment": faith,
        "answer_relevance": relevance,
        "context_precision": precision,
        "tps": round(tps, 3),
        "tokens": tokens,                       # токенов в пользовательском тексте
        "tokens_for_tps": tokens_for_tps,       # всего сгенерировано моделью
        "duration_s": round(duration, 2),
    }
    if diag:
        sample["diagnostics"] = diag
    return sample


_METRIC_KEYS = (
    "reference_alignment",
    "answer_relevance",
    "context_precision",
    "tps",
)


def _bootstrap_ci(
    values: list[float],
    *,
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap percentile CI для среднего.

    Из выборки values берём n_resamples псевдо-выборок того же размера
    с возвратом, считаем mean у каждой, возвращаем (low, high) перцентили.
    """
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        v = float(values[0])
        return (v, v)
    import random as _r
    rng = _r.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_idx = max(0, int(alpha * n_resamples))
    hi_idx = min(n_resamples - 1, int((1.0 - alpha) * n_resamples))
    return (round(means[lo_idx], 4), round(means[hi_idx], 4))


def _aggregate(samples: list[dict]) -> dict:
    """Усредняет только успешные samples (status='ok') + bootstrap CI."""
    ok = [s for s in samples if s.get("status") == "ok"]
    if not ok:
        return {
            "reference_alignment": 0.0, "answer_relevance": 0.0,
            "context_precision": 0.0, "tps": 0.0,
            "ci": {k: [0.0, 0.0] for k in _METRIC_KEYS},
            "samples": 0, "samples_total": len(samples),
            "samples_failed": len(samples),
            "samples_recovered": 0,
        }
    n = len(ok)
    means: dict[str, float] = {}
    ci: dict[str, list[float]] = {}
    for key in _METRIC_KEYS:
        vals = [float(s[key]) for s in ok]
        means[key] = round(sum(vals) / n, 4)
        lo, hi = _bootstrap_ci(vals)
        ci[key] = [lo, hi]
    return {
        **means,
        "ci":                ci,
        "samples":           n,
        "samples_total":     len(samples),
        "samples_failed":    len(samples) - n,
        "samples_recovered": sum(1 for s in ok if s.get("recovered")),
    }


def _publish_to_prometheus(metrics: dict, finished_at: datetime) -> None:
    QUALITY_REFERENCE_ALIGNMENT.set(metrics["reference_alignment"])
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
        # Диагностика: проверим, что judge и embedder отвечают вообще
        await _diagnose_services(judge_client, settings)

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
                samples.append(sample)
                task.samples.append(sample)
            if task.cancelled:
                break

    finished = datetime.now(timezone.utc)
    task.finished_at = finished.isoformat()

    metrics = _aggregate(samples)

    if metrics["samples"] == 0:
        if task.cancelled:
            task.status = "cancelled"
            task.error = "остановлено до получения первого успешного sample"
        else:
            task.status = "failed"
            task.error = "ни одного успешного sample (все попытки упали)"
        task.result = {
            "status": "no_samples",
            "metrics": metrics,
            "odz": ODZ,
            "lead_ids": lead_ids,
            "samples": samples,
        }
        quality_history.save_task(task)
        return

    _publish_to_prometheus(metrics, finished)

    # Если cancel пришёл, но какие-то samples успели — статус cancelled, но
    # результат вычисляется по тому, что собрали.
    task.status = "cancelled" if task.cancelled else "completed"
    task.result = {
        "status": "ok" if not task.cancelled else "cancelled",
        "metrics": metrics,
        "odz": ODZ,
        "lead_ids": lead_ids,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "samples": samples,
    }
    quality_history.save_task(task)


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
            samples.append(sample)
    finished = datetime.now(timezone.utc)

    metrics = _aggregate(samples)
    if metrics["samples"] == 0:
        return {
            "status": "no_samples",
            "metrics": metrics, "odz": ODZ,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": (finished - started).total_seconds(),
            "samples": samples,
        }

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
