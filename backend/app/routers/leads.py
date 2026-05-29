"""Lead card: recommendations, actions timeline, tasks."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..security import get_current_user
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/leads",
    tags=["leads"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/by-email")
async def lead_by_email(
    email: str = Query(..., description="Email-адрес контакта в Mautic"),
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    """Resolve lead_id from email via Mautic contact check."""
    result = await rag.check_mautic_contact(email)
    if result.get("unique") is False:
        raise HTTPException(
            status_code=409,
            detail="Найдено несколько контактов с таким email",
        )
    contact_id = result.get("contact_id")
    if not contact_id:
        raise HTTPException(
            status_code=404,
            detail="Контакт с таким email не найден",
        )
    return {"lead_id": str(contact_id), "email": email}


@router.get("/{lead_id}")
async def lead_card(
    lead_id: str,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    """Aggregated lead card with actions, tasks and recommendations."""
    actions = {"lead_id": lead_id, "actions": []}
    tasks = {"lead_id": lead_id, "tasks": []}
    recs = {"lead_id": lead_id, "recommendations": []}
    errors: dict[str, str] = {}

    try:
        actions = await rag.get_lead_actions(lead_id)
    except Exception as exc:
        errors["actions"] = str(exc)
    try:
        tasks = await rag.get_lead_tasks(lead_id)
    except Exception as exc:
        errors["tasks"] = str(exc)
    try:
        recs = await rag.get_recommendations(lead_id)
    except Exception as exc:
        errors["recommendations"] = str(exc)

    return {
        "lead_id": lead_id,
        "actions": actions.get("actions", []),
        "tasks": tasks.get("tasks", []),
        "recommendations": recs.get("recommendations", []),
        "errors": errors,
    }


@router.get("/{lead_id}/actions")
async def lead_actions(
    lead_id: str,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.get_lead_actions(lead_id)


@router.get("/{lead_id}/tasks")
async def lead_tasks(
    lead_id: str,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.get_lead_tasks(lead_id)


@router.get("/{lead_id}/recommendations")
async def lead_recommendations(
    lead_id: str,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.get_recommendations(lead_id)
