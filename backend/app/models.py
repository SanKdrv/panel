"""Pydantic models for request/response bodies."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# -------- Auth --------
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    username: str


# -------- Dashboard --------
class ComponentHealth(BaseModel):
    status: str
    latency_ms: float | None = None
    queue_depth: int | None = None


class HealthOverview(BaseModel):
    status: str
    timestamp: str
    components: dict[str, ComponentHealth]
    uptime_seconds: int | None = None


# -------- Knowledge base --------
class ResourceType(BaseModel):
    id: int
    name: str


class ResourceTypesResponse(BaseModel):
    resource_types: list[ResourceType]


class CreateResourceTypeRequest(BaseModel):
    name: str


class UploadResourceRequest(BaseModel):
    resource_type: str
    text: str
    url: str | None = None
    title: str | None = None


class UploadResourceResponse(BaseModel):
    resource_id: int
    status: str


class MauticImportRequest(BaseModel):
    id: int | None = None


# -------- Prompts --------
LeadType = Literal["cold", "warm", "hot", "after_sale"]


class PromptResponse(BaseModel):
    lead_type: str
    prompt: str


class UpdatePromptRequest(BaseModel):
    lead_type: LeadType
    prompt: str


# -------- Generation --------
class GenerateRequest(BaseModel):
    lead_id: str
    type: LeadType


class GenerateResponse(BaseModel):
    token: str
    status: str


class GenerationStatusResponse(BaseModel):
    status: str


# -------- Leads --------
class LeadAction(BaseModel):
    id: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class LeadActionsResponse(BaseModel):
    lead_id: str
    actions: list[LeadAction]


class LeadTask(BaseModel):
    id: str
    status: str
    type: str
    created_at: str | None = None
    updated_at: str | None = None


class LeadTasksResponse(BaseModel):
    lead_id: str
    tasks: list[LeadTask]


class LeadRecommendation(BaseModel):
    id: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class LeadRecommendationsResponse(BaseModel):
    lead_id: str
    recommendations: list[LeadRecommendation]


# -------- Mautic --------
class MauticFieldCreate(BaseModel):
    name: str
    type: str = "text"


class MauticFieldUpdate(BaseModel):
    lead_id: str
    field: str
    value: Any


# -------- Quality evaluation --------
class QualityMetrics(BaseModel):
    faithfulness: float
    answer_relevance: float
    context_precision: float
    tps: float
    samples: int


class QualityEvaluationResponse(BaseModel):
    status: str
    metrics: QualityMetrics | None = None
    odz: dict[str, float] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None


class QualityTriggerResponse(BaseModel):
    status: str
    message: str
