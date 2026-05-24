"""RAG quality evaluation pipeline.

Implements the pipeline described in section 3.4 of the diploma:

1. Load gold test-set ({question, reference} pairs).
2. Call the RAG API for each question, measure TPS.
3. Compute Faithfulness via LLM-as-judge (Ollama).
4. Compute Answer Relevance as cosine similarity between question and answer
   embeddings.
5. Compute Context Precision as the fraction of reference keywords found in
   the RAG answer.
6. Aggregate metrics and compare to ODZ from the diploma.
7. Publish gauges to Prometheus.
8. Return the result for display in the admin panel.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
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

# ODZ from diploma table 2.x (rag_odz)
ODZ = {
    "faithfulness": 0.80,
    "answer_relevance": 0.75,
    "context_precision": 0.70,
    "tps": 5.0,
}

JUDGE_PROMPT_TEMPLATE = (
    "You are an impartial evaluator. Compare the GENERATED answer to the "
    "REFERENCE answer for the given QUESTION. Score how faithful the "
    "GENERATED answer is to the REFERENCE on a scale from 0.0 to 1.0, where "
    "1.0 means every claim in GENERATED is supported by REFERENCE and 0.0 "
    "means none is. Respond with a single decimal number only.\n\n"
    "QUESTION: {question}\n"
    "REFERENCE: {reference}\n"
    "GENERATED: {generated}\n\n"
    "SCORE:"
)


@dataclass
class SampleResult:
    question: str
    reference: str
    generated: str
    faithfulness: float
    answer_relevance: float
    context_precision: float
    tps: float
    tokens: int
    duration_s: float


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
    """Fraction of unique reference keywords that appear in the generated text."""
    ref_tokens = set(_tokenize(reference))
    gen_tokens = set(_tokenize(generated))
    if not ref_tokens:
        return 0.0
    overlap = ref_tokens & gen_tokens
    return round(len(overlap) / len(ref_tokens), 4)


async def call_judge(
    client: httpx.AsyncClient,
    url: str,
    model: str,
    question: str,
    reference: str,
    generated: str,
) -> float:
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question, reference=reference, generated=generated
    )
    try:
        resp = await client.post(
            f"{url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        match = re.search(r"[01](?:\.\d+)?", text)
        if not match:
            logger.warning("event=quality.judge.no_score raw=%r", text[:100])
            return 0.0
        score = float(match.group(0))
        return max(0.0, min(1.0, score))
    except Exception as exc:
        logger.warning("event=quality.judge.error error=%s", exc)
        return 0.0


async def embed(
    client: httpx.AsyncClient, url: str, model: str, text: str
) -> list[float]:
    try:
        resp = await client.post(
            f"{url.rstrip('/')}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("embedding", [])
    except Exception as exc:
        logger.warning("event=quality.embed.error error=%s", exc)
        return []


def load_gold_dataset(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        logger.warning("event=quality.gold.missing path=%s", path)
        return []
    return json.loads(p.read_text(encoding="utf-8"))


async def _poll_recommendation(
    rag: RAGClient,
    token: str,
    timeout_s: float = 120.0,
    poll_interval: float = 2.0,
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


async def evaluate(
    rag: RAGClient,
    settings: Settings,
) -> dict[str, Any]:
    """Run a full evaluation round and update Prometheus gauges."""
    gold = load_gold_dataset(settings.quality_gold_dataset_path)
    started_at = datetime.now(timezone.utc)
    if not gold:
        return {
            "status": "no_dataset",
            "metrics": None,
            "odz": ODZ,
            "started_at": started_at.isoformat(),
            "finished_at": started_at.isoformat(),
            "duration_seconds": 0.0,
        }

    samples: list[SampleResult] = []
    async with httpx.AsyncClient() as judge_client:
        for entry in gold:
            question = entry["question"]
            reference = entry["reference"]
            lead_id = entry.get("lead_id", "quality-eval")
            lead_type = entry.get("type", "cold")

            # Generate via RAG API
            t0 = time.monotonic()
            try:
                gen = await rag.generate_recommendation(lead_id, lead_type)
                token = gen.get("token", "")
                ok = await _poll_recommendation(rag, token)
                if not ok:
                    logger.warning("event=quality.gen.failed q=%r", question[:60])
                    continue
                recs = await rag.get_recommendations(lead_id)
                items = recs.get("recommendations", [])
                generated = str(items[0]["data"]) if items else ""
            except Exception as exc:
                logger.warning("event=quality.gen.error error=%s", exc)
                continue

            duration = max(time.monotonic() - t0, 0.001)
            tokens = max(len(_tokenize(generated)), 1)
            tps = tokens / duration

            # Faithfulness via judge
            faith = await call_judge(
                judge_client,
                settings.quality_judge_url,
                settings.quality_judge_model,
                question,
                reference,
                generated,
            )

            # Answer Relevance via embeddings
            q_emb, a_emb = await asyncio.gather(
                embed(
                    judge_client,
                    settings.quality_embedding_url,
                    settings.quality_embedding_model,
                    question,
                ),
                embed(
                    judge_client,
                    settings.quality_embedding_url,
                    settings.quality_embedding_model,
                    generated,
                ),
            )
            relevance = _cosine(q_emb, a_emb)

            # Context Precision via keyword overlap
            precision = context_precision(reference, generated)

            samples.append(
                SampleResult(
                    question=question,
                    reference=reference,
                    generated=generated,
                    faithfulness=faith,
                    answer_relevance=relevance,
                    context_precision=precision,
                    tps=tps,
                    tokens=tokens,
                    duration_s=duration,
                )
            )

    finished_at = datetime.now(timezone.utc)
    duration_total = (finished_at - started_at).total_seconds()

    if not samples:
        return {
            "status": "no_samples",
            "metrics": None,
            "odz": ODZ,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": duration_total,
        }

    n = len(samples)
    mean_faith = round(sum(s.faithfulness for s in samples) / n, 4)
    mean_rel = round(sum(s.answer_relevance for s in samples) / n, 4)
    mean_prec = round(sum(s.context_precision for s in samples) / n, 4)
    mean_tps = round(sum(s.tps for s in samples) / n, 4)

    # Publish to Prometheus
    QUALITY_FAITHFULNESS.set(mean_faith)
    QUALITY_ANSWER_RELEVANCE.set(mean_rel)
    QUALITY_CONTEXT_PRECISION.set(mean_prec)
    QUALITY_TPS.set(mean_tps)
    QUALITY_SAMPLES.set(n)
    QUALITY_RUN_TIMESTAMP.set(finished_at.timestamp())

    return {
        "status": "ok",
        "metrics": {
            "faithfulness": mean_faith,
            "answer_relevance": mean_rel,
            "context_precision": mean_prec,
            "tps": mean_tps,
            "samples": n,
        },
        "odz": ODZ,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration_total, 2),
    }
