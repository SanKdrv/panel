"""Prometheus metrics exposed by the admin panel backend.

Gauge metrics for RAG quality evaluation are updated after each
on-demand evaluation run (see services/quality.py).
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# --- HTTP / panel internals ---
HTTP_REQUESTS = Counter(
    "admin_http_requests_total",
    "Admin panel HTTP requests",
    labelnames=("method", "path", "status"),
)

# --- RAG quality (filled by the quality evaluator) ---
QUALITY_FAITHFULNESS = Gauge(
    "rag_faithfulness",
    "Mean Faithfulness over the gold test-set (0..1)",
)
QUALITY_ANSWER_RELEVANCE = Gauge(
    "rag_answer_relevance",
    "Mean Answer Relevance (cosine similarity) over the gold test-set (0..1)",
)
QUALITY_CONTEXT_PRECISION = Gauge(
    "rag_context_precision",
    "Mean Context Precision (keyword overlap) over the gold test-set (0..1)",
)
QUALITY_TPS = Gauge(
    "rag_tps",
    "Mean tokens-per-second across gold test-set generations",
)
QUALITY_SAMPLES = Gauge(
    "rag_quality_samples",
    "Number of samples in the latest quality evaluation run",
)
QUALITY_RUN_TIMESTAMP = Gauge(
    "rag_quality_run_timestamp_seconds",
    "Unix time of the latest quality evaluation run",
)

# --- Generation latency (when admin panel triggers /generate) ---
GENERATION_LATENCY = Histogram(
    "admin_generation_latency_seconds",
    "End-to-end generation latency observed from the panel",
)
GENERATION_REQUESTS = Counter(
    "admin_generation_requests_total",
    "Generation requests initiated from the panel",
    labelnames=("lead_type", "outcome"),
)
