from __future__ import annotations

import json
from collections.abc import Callable

import pandas as pd
from ssscreen.data.mp import load_mp_dataset_offline

from ssscreen_web.application.scientific_runtime import require_frozen_scientific_runtime
from ssscreen_web.application.stages.base import (
    ArtifactSpec,
    PreparedTask,
    StageResult,
    TaskContext,
    ValidationResult,
)
from ssscreen_web.domain.errors import DomainError


class MPOfflineDatasetRunner:
    stage = "stage-1-dataset"
    task_type = "dataset.mp-offline"
    dataset_kind = "mp-offline"
    data_artifact_kind = "mp-normalized-dataframe"
    provenance_artifact_kind = "mp-dataset-provenance"
    execution_error_message = "The server could not prepare the Materials Project dataset"
    register_dataset = True
    scientific_status = "dataset_ready"

    def __init__(self, loader: Callable[..., pd.DataFrame] = load_mp_dataset_offline) -> None:
        self.loader = loader

    def prepare(self, context: TaskContext) -> PreparedTask:
        require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        database = context.settings.mp_offline_database_path
        if database is None:
            raise DomainError(
                "dataset.offline_not_configured",
                "The server has no Materials Project offline snapshot configured",
            )
        resolved = database.expanduser().resolve(strict=False)
        if not resolved.is_file():
            raise DomainError(
                "dataset.offline_unavailable",
                "The configured Materials Project offline snapshot is unavailable",
            )
        context.sandbox.mkdir(parents=True, exist_ok=True)
        return PreparedTask(
            output_path=context.sandbox / "mp.df",
            provenance_path=context.sandbox / "mp.df.provenance.json",
        )

    def execute(self, prepared: PreparedTask, context: TaskContext) -> StageResult:
        database = context.settings.mp_offline_database_path
        if database is None:  # prepare owns the user-facing error; keeps the type narrow here.
            raise RuntimeError("MP offline database disappeared after preparation")
        frame = self.loader(
            output=prepared.output_path,
            provenance_path=prepared.provenance_path,
            max_e_hull=float(context.configuration["max_e_hull"]),
            offline_db=database,
            database_reference=context.settings.mp_offline_database_reference,
        )
        provenance = json.loads(prepared.provenance_path.read_text(encoding="utf-8"))
        identity = require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        provenance["execution"] = {
            "pipeline": {
                "name": "stage-1-mp-offline",
                "version": "stage-1-mp-offline-v1",
            },
            "scientific_core": identity.as_dict(),
        }
        prepared.provenance_path.write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return StageResult(
            row_count=len(frame),
            provenance=provenance,
            output_path=prepared.output_path,
            provenance_path=prepared.provenance_path,
        )

    def validate(self, result: StageResult) -> ValidationResult:
        if result.row_count <= 0:
            return ValidationResult(False, "The configured query returned no materials")
        if not result.output_path.is_file() or result.output_path.stat().st_size <= 0:
            return ValidationResult(False, "The normalized DataFrame was not written")
        if not result.provenance_path.is_file():
            return ValidationResult(False, "The provenance sidecar was not written")
        if result.provenance.get("backend") != "offline":
            return ValidationResult(False, "The provenance backend is not offline")
        if result.provenance.get("row_count") != result.row_count:
            return ValidationResult(False, "The provenance row count does not match the dataset")
        database = result.provenance.get("database")
        if not isinstance(database, dict) or "sha256" not in database or "path" in database:
            return ValidationResult(
                False, "The database provenance is incomplete or exposes a path"
            )
        execution = result.provenance.get("execution")
        if not isinstance(execution, dict):
            return ValidationResult(False, "The execution provenance is missing")
        pipeline = execution.get("pipeline")
        if not isinstance(pipeline, dict) or pipeline.get("version") != "stage-1-mp-offline-v1":
            return ValidationResult(False, "The pipeline provenance is invalid")
        core = execution.get("scientific_core")
        if (
            not isinstance(core, dict)
            or core.get("version") != core.get("distribution_version")
            or len(str(core.get("source_sha256", ""))) != 64
            or not core.get("revision")
        ):
            return ValidationResult(False, "The scientific core provenance is invalid")
        return ValidationResult(True)

    def publish(self, result: StageResult, context: TaskContext) -> list[ArtifactSpec]:
        del context
        return [
            ArtifactSpec(
                path=result.output_path,
                filename="mp.df",
                kind="mp-normalized-dataframe",
                content_type="application/x-pandas-pickle",
                schema_version="1",
            ),
            ArtifactSpec(
                path=result.provenance_path,
                filename="mp.df.provenance.json",
                kind="mp-dataset-provenance",
                content_type="application/json",
                schema_version="1",
            ),
        ]

    def cleanup(self, context: TaskContext) -> None:
        del context
