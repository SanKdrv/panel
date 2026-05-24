"""Knowledge base management (staging-area resources + Mautic import)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models import (
    CreateResourceTypeRequest,
    MauticImportRequest,
    UploadResourceRequest,
    UploadResourceResponse,
)
from ..security import get_current_user
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/resource-types")
async def list_resource_types(rag: RAGClient = Depends(get_rag_client)) -> dict:
    return await rag.list_resource_types()


@router.post("/resource-types")
async def create_resource_type(
    body: CreateResourceTypeRequest,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.create_resource_type(body.name)


@router.post("", response_model=UploadResourceResponse)
async def upload_resource(
    body: UploadResourceRequest,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.upload_resource(
        resource_type=body.resource_type,
        text=body.text,
        url=body.url,
        title=body.title,
    )


# NB: static routes must be declared before dynamic /{resource_id} —
# otherwise "/vector-db/status" gets eaten by /{resource_id}/status.
@router.get("/vector-db/status")
async def vector_db_status(rag: RAGClient = Depends(get_rag_client)) -> dict:
    return await rag.vector_db_status()


@router.post("/import/email")
async def import_email(
    body: MauticImportRequest,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.import_email(mautic_id=body.id)


@router.get("/{resource_id}")
async def get_resource(
    resource_id: int,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.get_resource(resource_id)


@router.get("/{resource_id}/status")
async def resource_status(
    resource_id: int,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    return await rag.resource_status(resource_id)
