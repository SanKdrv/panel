"""System health and dashboard data."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..security import get_current_user
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def system_health(rag: RAGClient = Depends(get_rag_client)) -> dict:
    """Public passthrough to RAG /system/health."""
    try:
        return await rag.health()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "components": {},
        }


@router.get("/dashboard")
async def dashboard(
    _: str = Depends(get_current_user),
    rag: RAGClient = Depends(get_rag_client),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Aggregated dashboard payload: health + grafana embed url."""
    try:
        health = await rag.health()
    except Exception as exc:
        health = {"status": "unhealthy", "error": str(exc), "components": {}}
    return {
        "health": health,
        "grafana_external_url": settings.grafana_external_url,
    }
