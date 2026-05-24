"""Recommendation generation: trigger + polling."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from ..models import GenerateRequest, GenerateResponse, GenerationStatusResponse
from ..security import get_current_user
from ..services.metrics import GENERATION_LATENCY, GENERATION_REQUESTS
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/generate",
    tags=["generate"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)


@router.post("", response_model=GenerateResponse)
async def trigger_generation(
    body: GenerateRequest,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    started = time.perf_counter()
    try:
        data = await rag.generate_recommendation(body.lead_id, body.type)
        GENERATION_REQUESTS.labels(lead_type=body.type, outcome="queued").inc()
        return data
    except Exception as exc:
        GENERATION_REQUESTS.labels(lead_type=body.type, outcome="error").inc()
        logger.exception("event=generate.trigger.error lead_id=%s", body.lead_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        GENERATION_LATENCY.observe(time.perf_counter() - started)


@router.get("/status/{token}", response_model=GenerationStatusResponse)
async def generation_status(
    token: str,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.recommendation_status(token)
