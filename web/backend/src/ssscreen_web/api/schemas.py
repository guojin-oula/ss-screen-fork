from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeResponse(ORMModel):
    id: uuid.UUID
    oidc_subject: str
    display_name: str
    status: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class ProjectResponse(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    owner_id: uuid.UUID
    retention_policy: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    role: str | None = None
    owner_display_name: str | None = None
    latest_run_id: uuid.UUID | None = None
    latest_run_status: str | None = None


class RunCreate(BaseModel):
    pipeline: Literal[
        "control-plane-demo",
        "stage-1-mp-offline",
        "stage-1a-composition",
        "stage-2-condensation",
    ] = "control-plane-demo"
    message: str = Field(default="SS-Screen Web control plane", min_length=1, max_length=500)
    simulate_failure: bool = False
    dataset_label: str | None = Field(default=None, min_length=1, max_length=200)
    max_e_hull: float = Field(default=0.01, ge=0.0, le=1.0)
    dataset_id: uuid.UUID | None = None
    nelems: int = Field(default=2, ge=2, le=3)
    max_bandgap: float = Field(default=1.0, ge=0.0, le=20.0)
    min_group_size: int = Field(default=2, ge=2, le=1000)
    min_x_elements: int = Field(default=2, ge=2, le=1000)
    composition_run_id: uuid.UUID | None = None
    batch_size: int = Field(default=16, ge=1, le=100)

    @model_validator(mode="after")
    def validate_pipeline_fields(self) -> RunCreate:
        if self.pipeline == "stage-1-mp-offline":
            if self.dataset_label is None or not self.dataset_label.strip():
                raise ValueError("dataset_label is required for the Stage 1 MP offline pipeline")
            if self.simulate_failure:
                raise ValueError("simulate_failure is only supported by the control-plane demo")
        if self.pipeline == "stage-1a-composition":
            if self.dataset_id is None:
                raise ValueError("dataset_id is required for the Stage 1a composition pipeline")
            if self.nelems not in {2, 3}:
                raise ValueError("nelems must be 2 or 3")
            if self.min_x_elements > self.min_group_size:
                raise ValueError("min_x_elements must not exceed min_group_size")
            if self.simulate_failure:
                raise ValueError("simulate_failure is only supported by the control-plane demo")
        if self.pipeline == "stage-2-condensation":
            if self.composition_run_id is None:
                raise ValueError(
                    "composition_run_id is required for the Stage 2 condensation pipeline"
                )
            if self.simulate_failure:
                raise ValueError("simulate_failure is only supported by the control-plane demo")
        return self


class RunResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    pipeline_version: str
    status: str
    configuration: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    version_counter: int
    created_at: datetime
    updated_at: datetime


class TaskResponse(ORMModel):
    id: uuid.UUID
    run_id: uuid.UUID
    stage: str
    task_type: str
    status: str
    scientific_status: str | None
    depends_on: list[str]
    started_at: datetime | None
    finished_at: datetime | None
    version_counter: int
    created_at: datetime
    updated_at: datetime


class AttemptResponse(ORMModel):
    id: uuid.UUID
    task_id: uuid.UUID
    number: int
    status: str
    settings_hash: str
    worker_id: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskDetail(TaskResponse):
    attempts: list[AttemptResponse]


class ArtifactResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    attempt_id: uuid.UUID
    kind: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    schema_version: str
    created_at: datetime


class CompositionCandidateResponse(BaseModel):
    template: str
    material_id: str
    x_element: str
    formula: str
    composition: str
    band_gap: float
    e_hull: float
    source: str


class CompositionPreviewResponse(BaseModel):
    artifact_id: uuid.UUID
    total_rows: int
    limit: int
    summary: dict[str, Any]
    candidates: list[CompositionCandidateResponse]


class CondensationFailureResponse(BaseModel):
    material_id: str
    status: str
    error: str


class CondensationPreviewResponse(BaseModel):
    total: int
    completed: int
    succeeded: int
    written: int
    skipped: int
    failed: int
    batch: int
    batches: int
    attempt: int
    failures: list[CondensationFailureResponse]


class DatasetResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_run_id: uuid.UUID
    artifact_id: uuid.UUID
    provenance_artifact_id: uuid.UUID
    kind: str
    label: str
    row_count: int
    provenance: dict[str, Any]
    created_at: datetime


class EventResponse(ORMModel):
    id: int
    project_id: uuid.UUID
    run_id: uuid.UUID | None
    task_id: uuid.UUID | None
    kind: str
    payload: dict[str, Any]
    actor_id: uuid.UUID | None
    created_at: datetime
