from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ssscreen_web.settings import Settings


@dataclass(frozen=True)
class TaskContext:
    configuration: dict[str, object]
    sandbox: Path
    settings: Settings
    task_id: str | None = None
    attempt_number: int | None = None


@dataclass(frozen=True)
class PreparedTask:
    output_path: Path
    provenance_path: Path
    inputs: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactSpec:
    path: Path
    filename: str
    kind: str
    content_type: str
    schema_version: str


@dataclass(frozen=True)
class StageResult:
    row_count: int
    provenance: dict[str, object]
    output_path: Path
    provenance_path: Path
    inputs: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str | None = None


class StageRunner(Protocol):
    stage: str
    task_type: str
    dataset_kind: str
    data_artifact_kind: str
    provenance_artifact_kind: str
    execution_error_message: str
    register_dataset: bool
    scientific_status: str

    def prepare(self, context: TaskContext) -> PreparedTask: ...

    def execute(self, prepared: PreparedTask, context: TaskContext) -> StageResult: ...

    def validate(self, result: StageResult) -> ValidationResult: ...

    def publish(self, result: StageResult, context: TaskContext) -> list[ArtifactSpec]: ...

    def cleanup(self, context: TaskContext) -> None: ...
