from __future__ import annotations

import hashlib
import json
import uuid

import pandas as pd
from sqlalchemy import select
from ssscreen.pair.grouping import screen_composition_candidates

from ssscreen_web.application.scientific_runtime import require_frozen_scientific_runtime
from ssscreen_web.application.stages.base import (
    ArtifactSpec,
    PreparedTask,
    StageResult,
    TaskContext,
    ValidationResult,
)
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_session_factory
from ssscreen_web.infrastructure.models import Artifact, Dataset


class CompositionStageRunner:
    stage = "stage-1a-composition"
    task_type = "composition.screen"
    dataset_kind = "not-applicable"
    data_artifact_kind = "composition-candidates"
    provenance_artifact_kind = "composition-provenance"
    execution_error_message = "The server could not screen composition candidates"
    register_dataset = False
    scientific_status = "composition_ready"

    def prepare(self, context: TaskContext) -> PreparedTask:
        require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        try:
            dataset_id = uuid.UUID(str(context.configuration["dataset_id"]))
            artifact_id = uuid.UUID(str(context.configuration["dataset_artifact_id"]))
        except (KeyError, ValueError) as error:
            raise DomainError(
                "composition.input_invalid", "The frozen Dataset input is invalid"
            ) from error
        with get_session_factory()() as session:
            dataset = session.scalar(select(Dataset).where(Dataset.id == dataset_id))
            artifact = session.scalar(select(Artifact).where(Artifact.id == artifact_id))
            if dataset is None or artifact is None or dataset.artifact_id != artifact.id:
                raise DomainError(
                    "composition.input_unavailable", "The input Dataset artifact is unavailable"
                )
            if artifact.sha256 != context.configuration.get("dataset_artifact_sha256"):
                raise DomainError(
                    "composition.input_changed", "The input Dataset artifact identity changed"
                )
            artifact_key = artifact.key
            expected_size = artifact.size_bytes
            expected_sha = artifact.sha256
        context.sandbox.mkdir(parents=True, exist_ok=True)
        input_path = context.sandbox / "dataset.df"
        digest = hashlib.sha256()
        size = 0
        store = FileSystemArtifactStore(context.settings.artifact_root)
        with store.open_read(artifact_key) as source, input_path.open("xb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size != expected_size or digest.hexdigest() != expected_sha:
            input_path.unlink(missing_ok=True)
            raise DomainError(
                "composition.input_integrity_failed",
                "The input Dataset artifact failed its size or SHA-256 check",
            )
        return PreparedTask(
            output_path=context.sandbox / "composition-candidates.csv",
            provenance_path=context.sandbox / "composition.provenance.json",
            inputs={"dataset": input_path},
        )

    def execute(self, prepared: PreparedTask, context: TaskContext) -> StageResult:
        configuration = context.configuration
        frame = pd.read_pickle(prepared.inputs["dataset"])
        candidates, summary = screen_composition_candidates(
            frame,
            nelems=int(configuration["nelems"]),
            max_bandgap=float(configuration["max_bandgap"]),
            max_e_hull=float(configuration["max_e_hull"]),
            excluded_elements=frozenset(configuration["excluded_elements"]),
            min_group_size=int(configuration["min_group_size"]),
            min_x_elements=int(configuration["min_x_elements"]),
        )
        candidates.to_csv(prepared.output_path, index=False)
        identity = require_frozen_scientific_runtime(
            context.settings, configuration.get("scientific_runtime")
        )
        provenance: dict[str, object] = {
            "schema_version": 1,
            "row_count": len(candidates),
            "summary": summary,
            "input": {
                "dataset_id": str(configuration["dataset_id"]),
                "dataset_kind": str(configuration["dataset_kind"]),
                "artifact_id": str(configuration["dataset_artifact_id"]),
                "artifact_sha256": str(configuration["dataset_artifact_sha256"]),
            },
            "parameters": {
                key: configuration[key]
                for key in (
                    "nelems",
                    "max_bandgap",
                    "max_e_hull",
                    "min_group_size",
                    "min_x_elements",
                    "excluded_elements",
                )
            },
            "execution": {
                "pipeline": {
                    "name": "stage-1a-composition",
                    "version": "stage-1a-composition-v1",
                },
                "scientific_core": identity.as_dict(),
            },
        }
        prepared.provenance_path.write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return StageResult(
            row_count=len(candidates),
            provenance=provenance,
            output_path=prepared.output_path,
            provenance_path=prepared.provenance_path,
            inputs=prepared.inputs,
        )

    def validate(self, result: StageResult) -> ValidationResult:
        if not result.output_path.is_file() or not result.provenance_path.is_file():
            return ValidationResult(False, "The composition outputs are incomplete")
        frame = pd.read_csv(result.output_path)
        required = {
            "template",
            "material_id",
            "x_element",
            "formula",
            "composition",
            "band_gap",
            "e_hull",
            "source",
        }
        if len(frame) != result.row_count or set(frame.columns) != required:
            return ValidationResult(False, "The composition candidate schema is invalid")
        if result.provenance.get("row_count") != result.row_count:
            return ValidationResult(False, "The composition provenance row count is invalid")
        input_identity = result.provenance.get("input")
        if (
            not isinstance(input_identity, dict)
            or len(str(input_identity.get("artifact_sha256", ""))) != 64
        ):
            return ValidationResult(False, "The composition input provenance is invalid")
        return ValidationResult(True)

    def publish(self, result: StageResult, context: TaskContext) -> list[ArtifactSpec]:
        del context
        return [
            ArtifactSpec(
                path=result.output_path,
                filename="composition-candidates.csv",
                kind=self.data_artifact_kind,
                content_type="text/csv",
                schema_version="1",
            ),
            ArtifactSpec(
                path=result.provenance_path,
                filename="composition.provenance.json",
                kind=self.provenance_artifact_kind,
                content_type="application/json",
                schema_version="1",
            ),
        ]

    def cleanup(self, context: TaskContext) -> None:
        del context
