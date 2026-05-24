"""Mautic integration: field management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models import MauticFieldCreate, MauticFieldUpdate
from ..security import get_current_user
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/mautic",
    tags=["mautic"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/field")
async def create_field(
    body: MauticFieldCreate,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.create_mautic_field(body.name, body.type)


@router.patch("/field")
async def update_field(
    body: MauticFieldUpdate,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.update_mautic_field(body.lead_id, body.field, body.value)


@router.get("/contact/check")
async def check_contact(
    email: str = Query(...),
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.check_mautic_contact(email)
