"""Эндпоинты для нативных графиков на странице «Мониторинг».

Проксируют Prometheus query API и собирают данные для графиков
CPU/RAM/Disk per server. Фронту не нужно знать PromQL —
он получает готовые серии {label, points}.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Query

from ..config import Settings, get_settings
from ..security import get_current_user
from ..services.prometheus import PrometheusClient

router = APIRouter(
    prefix="/api/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)


PROMQL = {
    # avg without (cpu, mode) — агрегируем по ядрам и режимам,
    # но сохраняем лейблы instance/role/job для маппинга в UI.
    "cpu":   '100 * (1 - avg without (cpu, mode) (rate(node_cpu_seconds_total{mode="idle"}[2m])))',
    "ram":   '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
    "disk":  '(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100',
}

QUALITY_METRICS = (
    "rag_faithfulness",
    "rag_answer_relevance",
    "rag_context_precision",
    "rag_tps",
)


def _get_prom_client(settings: Settings) -> PrometheusClient:
    return PrometheusClient(base_url=settings.prometheus_url)


def _series_to_points(result: list[dict]) -> list[dict]:
    """Преобразует ответ Prometheus в [{label, points: [[ts_ms, val], ...]}]."""
    out = []
    for series in result:
        label = (
            series.get("metric", {}).get("role")
            or series.get("metric", {}).get("instance")
            or series.get("metric", {}).get("__name__")
            or "series"
        )
        points = [[int(float(t) * 1000), float(v)] for t, v in series.get("values", [])]
        out.append({"label": label, "points": points})
    return out


@router.get("/servers")
async def servers_resources(
    range_seconds: int = Query(3600, ge=60, le=86400, alias="range"),
    step_seconds: int = Query(30, ge=5, le=600, alias="step"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """CPU/RAM/Disk по всем серверам за последние range секунд."""
    prom = _get_prom_client(settings)
    end = time.time()
    start = end - range_seconds

    result: dict[str, list] = {}
    for metric_name, query in PROMQL.items():
        try:
            raw = await prom.query_range(query, start=start, end=end, step=step_seconds)
            result[metric_name] = _series_to_points(raw)
        except Exception as exc:
            logger.warning("event=monitoring.query.error metric=%s err=%s", metric_name, exc)
            result[metric_name] = []

    return {
        "range_seconds": range_seconds,
        "step_seconds": step_seconds,
        "start_ms": int(start * 1000),
        "end_ms": int(end * 1000),
        "metrics": result,
    }


@router.get("/quality/history")
async def quality_history(
    range_seconds: int = Query(86400, ge=300, le=604800, alias="range"),
    step_seconds: int = Query(300, ge=30, le=3600, alias="step"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Тренд метрик качества (rag_*) за период."""
    prom = _get_prom_client(settings)
    end = time.time()
    start = end - range_seconds

    result: dict[str, list] = {}
    for metric in QUALITY_METRICS:
        try:
            raw = await prom.query_range(metric, start=start, end=end, step=step_seconds)
            series = _series_to_points(raw)
            result[metric] = series[0]["points"] if series else []
        except Exception as exc:
            logger.warning("event=quality.history.error metric=%s err=%s", metric, exc)
            result[metric] = []

    return {
        "range_seconds": range_seconds,
        "step_seconds": step_seconds,
        "start_ms": int(start * 1000),
        "end_ms": int(end * 1000),
        "metrics": result,
    }
