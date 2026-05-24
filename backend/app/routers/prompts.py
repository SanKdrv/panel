"""Prompt management (4 funnel stages)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import PromptResponse, UpdatePromptRequest
from ..security import get_current_user
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/prompts",
    tags=["prompts"],
    dependencies=[Depends(get_current_user)],
)

LEAD_TYPES = ("cold", "warm", "hot", "after_sale")


@router.get("", response_model=list[PromptResponse])
async def list_prompts(rag: RAGClient = Depends(get_rag_client)) -> list[dict]:
    result = []
    for lt in LEAD_TYPES:
        try:
            data = await rag.get_prompt(lt)
            result.append(data)
        except Exception as exc:
            result.append({"lead_type": lt, "prompt": "", "error": str(exc)})
    return result


@router.get("/{lead_type}", response_model=PromptResponse)
async def get_prompt(
    lead_type: str,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.get_prompt(lead_type)


@router.put("", response_model=PromptResponse)
async def update_prompt(
    body: UpdatePromptRequest,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.update_prompt(body.lead_type, body.prompt)
