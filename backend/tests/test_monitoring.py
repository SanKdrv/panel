"""Tests for /api/monitoring/* endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def fake_prom_result():
    return [
        {
            "metric": {"role": "rag-core", "instance": "192.168.0.31:9100"},
            "values": [
                [1700000000, "12.5"],
                [1700000060, "15.1"],
                [1700000120, "11.9"],
            ],
        },
        {
            "metric": {"role": "ollama-llm", "instance": "192.168.0.32:9100"},
            "values": [
                [1700000000, "40.0"],
                [1700000060, "42.5"],
            ],
        },
    ]


def test_monitoring_requires_auth(client):
    assert client.get("/api/monitoring/servers").status_code == 401
    assert client.get("/api/monitoring/quality/history").status_code == 401


def test_servers_endpoint(client, auth_headers, fake_prom_result):
    with patch(
        "app.routers.monitoring.PrometheusClient.query_range",
        new=AsyncMock(return_value=fake_prom_result),
    ):
        r = client.get(
            "/api/monitoring/servers?range=3600&step=30",
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["range_seconds"] == 3600
    assert body["step_seconds"] == 30
    assert "cpu" in body["metrics"]
    assert "ram" in body["metrics"]
    assert "disk" in body["metrics"]
    cpu = body["metrics"]["cpu"]
    assert len(cpu) == 2
    assert cpu[0]["label"] == "rag-core"
    assert cpu[0]["points"][0] == [1700000000000, 12.5]


def test_servers_handles_prom_failure(client, auth_headers):
    with patch(
        "app.routers.monitoring.PrometheusClient.query_range",
        new=AsyncMock(side_effect=RuntimeError("down")),
    ):
        r = client.get("/api/monitoring/servers", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # пустые серии, но не падаем
    assert body["metrics"]["cpu"] == []
    assert body["metrics"]["ram"] == []
    assert body["metrics"]["disk"] == []


def test_quality_history(client, auth_headers, fake_prom_result):
    with patch(
        "app.routers.monitoring.PrometheusClient.query_range",
        new=AsyncMock(return_value=fake_prom_result[:1]),
    ):
        r = client.get(
            "/api/monitoring/quality/history?range=3600&step=60",
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert "rag_faithfulness" in body["metrics"]
    points = body["metrics"]["rag_faithfulness"]
    assert points[0] == [1700000000000, 12.5]


def test_servers_invalid_range(client, auth_headers):
    r = client.get("/api/monitoring/servers?range=10", headers=auth_headers)
    assert r.status_code == 422  # < 60


def test_servers_invalid_range_max(client, auth_headers):
    r = client.get("/api/monitoring/servers?range=999999", headers=auth_headers)
    assert r.status_code == 422  # > 86400
