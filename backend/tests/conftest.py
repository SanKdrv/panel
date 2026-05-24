"""Shared pytest fixtures: app + mocked RAG client."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Override env BEFORE importing app/config
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "secret")
os.environ.setdefault("SESSION_SECRET", "test-secret-key-32-bytes-long-xxx")
os.environ.setdefault("RAG_BACKEND_URL", "http://rag-test")
os.environ.setdefault("RAG_API_SECRET", "test-rag-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.services.rag_client_factory import set_rag_client  # noqa: E402


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def fake_rag():
    """A mock RAG client where every method is an AsyncMock."""
    client = MagicMock()
    client.health = AsyncMock(return_value={
        "status": "healthy",
        "timestamp": "2026-05-24T10:00:00Z",
        "components": {
            "staging_area": {"status": "ready", "latency_ms": 12},
            "vector_db": {"status": "ready", "latency_ms": 45},
            "queue": {"status": "healthy", "queue_depth": 3},
            "llm_service": {"status": "available", "latency_ms": 320},
            "embedding_service": {"status": "available", "latency_ms": 210},
            "redis": {"status": "healthy", "latency_ms": 4},
        },
        "uptime_seconds": 3600,
    })
    client.list_resource_types = AsyncMock(return_value={
        "resource_types": [{"id": 1, "name": "FAQ"}]
    })
    client.create_resource_type = AsyncMock(return_value={"id": 5, "name": "new"})
    client.upload_resource = AsyncMock(return_value={"resource_id": 42, "status": "queued"})
    client.get_resource = AsyncMock(return_value={"resource_id": 42, "resource_type": "FAQ", "data": {}})
    client.import_email = AsyncMock(return_value={"status": "created", "count": 5})
    client.vector_db_status = AsyncMock(return_value={"status": "ready"})
    client.resource_status = AsyncMock(return_value={"status": "created"})

    client.generate_recommendation = AsyncMock(return_value={"token": "tok123", "status": "queued"})
    client.recommendation_status = AsyncMock(return_value={"status": "completed"})
    client.get_recommendations = AsyncMock(return_value={
        "lead_id": "lead_1",
        "recommendations": [{"id": "r1", "type": "warm", "data": {"text": "hello"}}],
    })
    client.get_lead_actions = AsyncMock(return_value={
        "lead_id": "lead_1",
        "actions": [{"id": "a1", "type": "view", "data": {}}],
    })
    client.get_lead_tasks = AsyncMock(return_value={
        "lead_id": "lead_1",
        "tasks": [{"id": "t1", "status": "completed", "type": "warm"}],
    })

    client.get_prompt = AsyncMock(side_effect=lambda lt: {"lead_type": lt, "prompt": f"prompt for {lt}"})
    client.update_prompt = AsyncMock(side_effect=lambda lt, p: {"lead_type": lt, "prompt": p})

    client.create_mautic_field = AsyncMock(return_value={
        "id": 1, "name": "x", "alias": "x", "type": "text", "object": "lead",
    })
    client.update_mautic_field = AsyncMock(return_value={
        "lead_id": "1", "field": "x", "value": "y", "status": "updated",
    })
    client.check_mautic_contact = AsyncMock(return_value={"unique": True, "contact_id": 7})

    set_rag_client(client)
    yield client
    set_rag_client(None)


@pytest.fixture()
def auth_token(settings):
    token, _ = create_access_token("admin", settings)
    return token


@pytest.fixture()
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture()
def client(fake_rag):
    return TestClient(app)
