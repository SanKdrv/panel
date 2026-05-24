"""Lazy singleton factory for the shared RAG client."""
from __future__ import annotations

from fastapi import Depends

from ..config import Settings, get_settings
from .rag_client import RAGClient

_client: RAGClient | None = None


def get_rag_client(settings: Settings = Depends(get_settings)) -> RAGClient:
    global _client
    if _client is None:
        _client = RAGClient(
            base_url=settings.rag_backend_url,
            secret=settings.rag_api_secret,
            timeout=settings.rag_timeout_seconds,
        )
    return _client


async def shutdown_rag_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def set_rag_client(client: RAGClient | None) -> None:
    """Test helper: inject or reset the singleton."""
    global _client
    _client = client
