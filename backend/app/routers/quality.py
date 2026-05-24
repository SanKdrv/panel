"""Quality evaluation endpoint: trigger + read latest result."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..models import QualityTriggerResponse
from ..security import get_current_user
from ..services import quality as quality_service
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/quality",
    tags=["quality"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)


# Module-level cache of the latest evaluation run.
_latest_result: dict | None = None
_running_lock = asyncio.Lock()
_running = False


@router.post("/evaluate", response_model=QualityTriggerResponse)
async def trigger_evaluation(
    rag: RAGClient = Depends(get_rag_client),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Run evaluation synchronously (small gold dataset) and store result."""
    global _latest_result, _running

    async with _running_lock:
        if _running:
            return {"status": "already_running", "message": "Evaluation already in progress"}
        _running = True

    try:
        result = await quality_service.evaluate(rag, settings)
        _latest_result = result
        logger.info("event=quality.evaluate.done status=%s", result.get("status"))
        return {"status": result.get("status", "ok"), "message": "Evaluation completed"}
    except Exception as exc:
        logger.exception("event=quality.evaluate.error")
        return {"status": "error", "message": str(exc)}
    finally:
        _running = False


@router.get("/latest")
async def latest_result() -> dict:
    if _latest_result is None:
        return {
            "status": "no_run",
            "metrics": None,
            "odz": quality_service.ODZ,
        }
    return _latest_result


def _reset_for_tests() -> None:
    """Test helper."""
    global _latest_result, _running
    _latest_result = None
    _running = False
