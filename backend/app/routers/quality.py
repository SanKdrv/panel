"""Quality evaluation router (v2)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..security import get_current_user
from ..services import gold_dataset as gold_service
from ..services import quality as quality_service
from ..services.rag_client import RAGClient
from ..services.rag_client_factory import get_rag_client

router = APIRouter(
    prefix="/api/quality",
    tags=["quality"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)


# ----- models -----

class GoldEntryCreate(BaseModel):
    stage: str
    reference: str


class GoldEntryUpdate(BaseModel):
    stage: str | None = None
    reference: str | None = None


class FindLeadsRequest(BaseModel):
    min_id: int = Field(1, ge=1)
    max_id: int = Field(200, ge=1)
    n: int = Field(5, ge=1, le=50)
    min_actions: int = Field(1, ge=1, le=1000)


class StartEvalRequest(BaseModel):
    lead_ids: list[str]
    stages: list[str] | None = None


# ----- gold CRUD -----

@router.get("/gold")
async def list_gold(settings: Settings = Depends(get_settings)) -> dict:
    entries = await gold_service.list_entries(settings.quality_gold_dataset_path)
    return {"entries": entries, "stages": list(gold_service.VALID_STAGES)}


@router.post("/gold")
async def create_gold(
    body: GoldEntryCreate,
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await gold_service.add_entry(
            settings.quality_gold_dataset_path, body.stage, body.reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/gold/{entry_id}")
async def update_gold(
    entry_id: str,
    body: GoldEntryUpdate,
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await gold_service.update_entry(
            settings.quality_gold_dataset_path,
            entry_id,
            stage=body.stage,
            reference=body.reference,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="entry not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/gold/{entry_id}")
async def delete_gold(
    entry_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        await gold_service.delete_entry(
            settings.quality_gold_dataset_path, entry_id,
        )
        return {"status": "deleted", "id": entry_id}
    except KeyError:
        raise HTTPException(status_code=404, detail="entry not found")


# ----- find leads -----

@router.post("/leads/find")
async def find_leads(
    body: FindLeadsRequest,
    rag: RAGClient = Depends(get_rag_client),
) -> dict:
    if body.min_id > body.max_id:
        raise HTTPException(status_code=400, detail="min_id must be <= max_id")
    return await quality_service.find_valid_leads(
        rag, body.min_id, body.max_id, body.n, min_actions=body.min_actions,
    )


# ----- tasks -----

@router.post("/tasks")
async def start_eval(
    body: StartEvalRequest,
    rag: RAGClient = Depends(get_rag_client),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        task_id = await quality_service.start_evaluation(
            rag, settings, body.lead_ids, body.stages,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks")
async def list_eval_tasks(limit: int = 50) -> dict:
    tasks = quality_service.list_tasks(limit=max(1, min(limit, 200)))
    return {"tasks": [_task_to_dict(t) for t in tasks]}


@router.get("/tasks/{task_id}")
async def task_status(task_id: str) -> dict:
    task = quality_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return _task_to_dict(task, include_samples=True)


@router.post("/tasks/{task_id}/cancel")
async def cancel_eval(task_id: str) -> dict:
    ok = await quality_service.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="task not cancellable")
    return {"status": "cancelling"}


@router.get("/latest")
async def latest_completed() -> dict:
    for t in quality_service.list_tasks(limit=50):
        if t.status == "completed" and t.result:
            return _task_to_dict(t, include_samples=True)
    return {
        "status": "no_run",
        "metrics": None,
        "odz": quality_service.ODZ,
    }


def _task_to_dict(task, include_samples: bool = False) -> dict:
    d = {
        "id": task.id,
        "status": task.status,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "total": task.total,
        "done": task.done,
        "current_step": task.current_step,
        "error": task.error,
        "result": task.result,
    }
    if include_samples:
        d["samples"] = task.samples
    return d


def _reset_for_tests() -> None:
    quality_service._reset_for_tests()
