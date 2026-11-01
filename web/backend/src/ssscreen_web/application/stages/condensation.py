from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import uuid
import zipfile
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from ssscreen.data.condense import condense_dataframe, validate_archive

from ssscreen_web.application.scientific_runtime import require_frozen_scientific_runtime
from ssscreen_web.application.stages.base import (
    ArtifactSpec,
    PreparedTask,
    StageResult,
    TaskContext,
    ValidationResult,
)
from ssscreen_web.domain.enums import TaskStatus
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_session_factory
from ssscreen_web.infrastructure.models import Artifact, Event, Run, Task

MATERIAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
INDEX_COLUMNS = [
    "material_id",
    "status",
    "output_path",
    "source_path",
    "formula",
    "error",
    "file_size",
    "sha256",
]


class CondensationStageRunner:
    stage = "stage-2-condensation"
    task_type = "condensation.batch"
    dataset_kind = "not-applicable"
    data_artifact_kind = "condensed-structures-archive"
    provenance_artifact_kind = "condensation-provenance"
    execution_error_message = "The server could not condense the selected structures"
    register_dataset = False
    scientific_status = "condensation_ready"

    def __init__(self, batch_runner: Callable[..., object] = condense_dataframe) -> None:
        self.batch_runner = batch_runner

    @staticmethod
    def _checkpoint_root(context: TaskContext) -> Path | None:
        if context.task_id is None:
            return None
        try:
            task_id = uuid.UUID(context.task_id)
        except ValueError:
            return None
        return context.settings.attempt_sandbox_root / "checkpoints" / str(task_id)

    @staticmethod
    def _copy_artifact(
        *, artifact: Artifact, destination: Path, context: TaskContext, error_code: str
    ) -> None:
        store = FileSystemArtifactStore(context.settings.artifact_root)
        digest = hashlib.sha256()
        size = 0
        with store.open_read(artifact.key) as source, destination.open("xb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size != artifact.size_bytes or digest.hexdigest() != artifact.sha256:
            destination.unlink(missing_ok=True)
            raise DomainError(error_code, "A frozen Stage 2 input failed its integrity check")

    def prepare(self, context: TaskContext) -> PreparedTask:
        require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        try:
            dataset_artifact_id = uuid.UUID(str(context.configuration["dataset_artifact_id"]))
            candidates_artifact_id = uuid.UUID(str(context.configuration["candidate_artifact_id"]))
            candidates_provenance_artifact_id = uuid.UUID(
                str(context.configuration["candidate_provenance_artifact_id"])
            )
        except (KeyError, ValueError) as error:
            raise DomainError(
                "condensation.input_invalid", "The frozen Stage 2 inputs are invalid"
            ) from error

        with get_session_factory()() as session:
            dataset_artifact = session.get(Artifact, dataset_artifact_id)
            candidates_artifact = session.get(Artifact, candidates_artifact_id)
            candidates_provenance_artifact = session.get(
                Artifact, candidates_provenance_artifact_id
            )
            if (
                dataset_artifact is None
                or candidates_artifact is None
                or candidates_provenance_artifact is None
                or dataset_artifact.kind
                not in {"mp-normalized-dataframe", "wbm-normalized-dataframe"}
                or candidates_artifact.kind != "composition-candidates"
                or candidates_provenance_artifact.kind != "composition-provenance"
                or candidates_provenance_artifact.attempt_id != candidates_artifact.attempt_id
            ):
                raise DomainError(
                    "condensation.input_unavailable", "A frozen Stage 2 input is unavailable"
                )
            if (
                dataset_artifact.sha256 != context.configuration.get("dataset_artifact_sha256")
                or candidates_artifact.sha256
                != context.configuration.get("candidate_artifact_sha256")
                or candidates_provenance_artifact.sha256
                != context.configuration.get("candidate_provenance_artifact_sha256")
            ):
                raise DomainError(
                    "condensation.input_changed", "A frozen Stage 2 input identity changed"
                )
            context.sandbox.mkdir(parents=True, exist_ok=True)
            dataset_path = context.sandbox / "dataset.df"
            candidates_path = context.sandbox / "composition-candidates.csv"
            candidates_provenance_path = context.sandbox / "composition.provenance.json"
            self._copy_artifact(
                artifact=dataset_artifact,
                destination=dataset_path,
                context=context,
                error_code="condensation.dataset_integrity_failed",
            )
            self._copy_artifact(
                artifact=candidates_artifact,
                destination=candidates_path,
                context=context,
                error_code="condensation.candidates_integrity_failed",
            )
            self._copy_artifact(
                artifact=candidates_provenance_artifact,
                destination=candidates_provenance_path,
                context=context,
                error_code="condensation.candidates_provenance_integrity_failed",
            )

        condensed_dir = context.sandbox / "condensed"
        checkpoint = self._checkpoint_root(context)
        if checkpoint is not None and (checkpoint / "condensed").is_dir():
            shutil.copytree(checkpoint / "condensed", condensed_dir, dirs_exist_ok=True)
        condensed_dir.mkdir(parents=True, exist_ok=True)
        return PreparedTask(
            output_path=context.sandbox / "condensed-structures.zip",
            provenance_path=context.sandbox / "condensation.provenance.json",
            inputs={
                "dataset": dataset_path,
                "candidates": candidates_path,
                "candidates_provenance": candidates_provenance_path,
                "condensed_dir": condensed_dir,
                "manifest": context.sandbox / "condensation-manifest.jsonl",
                "index": context.sandbox / "condensation-index.csv",
                "failures": context.sandbox / "condensation-failures.csv",
            },
        )

    @staticmethod
    def _cancel_requested(context: TaskContext) -> bool:
        if context.task_id is None:
            return False
        try:
            parsed = uuid.UUID(context.task_id)
        except ValueError:
            return False
        with get_session_factory()() as session:
            status = session.scalar(select(Task.status).where(Task.id == parsed))
        return status == TaskStatus.CANCEL_REQUESTED

    @staticmethod
    def _publish_progress(
        context: TaskContext,
        *,
        total: int,
        records: dict[str, dict[str, object]],
        batch: int,
        batches: int,
    ) -> None:
        if context.task_id is None:
            return
        try:
            parsed = uuid.UUID(context.task_id)
        except ValueError:
            return
        counts = {
            status: sum(record["status"] == status for record in records.values())
            for status in ("written", "skipped", "failed")
        }
        with get_session_factory()() as session:
            task = session.get(Task, parsed)
            if task is None:
                return
            run = session.get(Run, task.run_id)
            if run is None:
                return
            session.add(
                Event(
                    project_id=run.project_id,
                    run_id=task.run_id,
                    task_id=task.id,
                    kind="stage.progress",
                    payload={
                        "total": total,
                        "completed": len(records),
                        "written": counts["written"],
                        "skipped": counts["skipped"],
                        "failed": counts["failed"],
                        "batch": batch,
                        "batches": batches,
                        "attempt": context.attempt_number or 1,
                    },
                )
            )
            session.commit()

    @staticmethod
    def _normalized_record(record: dict[str, object]) -> dict[str, object]:
        material_id = str(record.get("material_id", ""))
        return {
            "material_id": material_id,
            "status": str(record.get("status", "failed")),
            "output_path": f"condensed/{material_id}.json",
            "source_path": "",
            "formula": str(record.get("formula", "")),
            "error": str(record.get("error", "")),
            "file_size": int(record.get("file_size", 0) or 0),
            "sha256": str(record.get("sha256", "")),
        }

    @staticmethod
    def _failure(material_id: str, error: str) -> dict[str, object]:
        output_path = (
            f"condensed/{material_id}.json" if MATERIAL_ID_PATTERN.fullmatch(material_id) else ""
        )
        return {
            "material_id": material_id,
            "status": "failed",
            "output_path": output_path,
            "source_path": "",
            "formula": "",
            "error": error,
            "file_size": 0,
            "sha256": "",
        }

    @staticmethod
    def _write_records(
        records: list[dict[str, object]], *, manifest: Path, index: Path, failures: Path
    ) -> None:
        manifest.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
            ),
            encoding="utf-8",
        )
        pd.DataFrame.from_records(records, columns=INDEX_COLUMNS).to_csv(index, index=False)
        failed = [record for record in records if record["status"] == "failed"]
        pd.DataFrame.from_records(failed, columns=INDEX_COLUMNS).to_csv(failures, index=False)

    def _persist_checkpoint(
        self,
        context: TaskContext,
        condensed_dir: Path,
        records: list[dict[str, object]],
        *,
        updated_ids: set[str],
    ) -> None:
        checkpoint = self._checkpoint_root(context)
        if checkpoint is None:
            return
        checkpoint_condensed = checkpoint / "condensed"
        checkpoint_condensed.mkdir(parents=True, exist_ok=True)
        for record in records:
            material_id = str(record["material_id"])
            if material_id not in updated_ids or record["status"] == "failed":
                continue
            source = condensed_dir / f"{material_id}.json"
            destination = checkpoint_condensed / source.name
            if record["status"] == "skipped" and destination.is_file():
                continue
            if source.is_file():
                shutil.copy2(source, destination)
        checkpoint.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint / ".progress.json.tmp"
        temporary.write_text(
            json.dumps(
                {"completed": len(records), "updated_ids": sorted(updated_ids)},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(checkpoint / "progress.json")

    def execute(self, prepared: PreparedTask, context: TaskContext) -> StageResult:
        candidates = pd.read_csv(prepared.inputs["candidates"], usecols=["material_id"])
        candidate_ids = list(dict.fromkeys(candidates["material_id"].astype(str)))
        expected_count = int(context.configuration["candidate_count"])
        try:
            candidate_provenance = json.loads(
                prepared.inputs["candidates_provenance"].read_text(encoding="utf-8")
            )
            provenance_count = int(candidate_provenance["row_count"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DomainError(
                "condensation.candidates_invalid",
                "The frozen candidate provenance is invalid",
            ) from error
        if len(candidates) != expected_count or provenance_count != expected_count:
            raise DomainError(
                "condensation.candidates_changed",
                "The candidate row count does not match the frozen provenance",
            )

        source = pd.read_pickle(prepared.inputs["dataset"])
        source.index = source.index.map(str)
        if source.index.has_duplicates:
            raise DomainError(
                "condensation.dataset_invalid", "The input Dataset has duplicate material IDs"
            )
        if "structure" not in source.columns:
            raise DomainError(
                "condensation.dataset_invalid", "The input Dataset has no structure column"
            )

        records: dict[str, dict[str, object]] = {}
        runnable: list[str] = []
        for material_id in candidate_ids:
            if not MATERIAL_ID_PATTERN.fullmatch(material_id):
                records[material_id] = self._failure(material_id, "Invalid material ID")
            elif material_id not in source.index:
                records[material_id] = self._failure(
                    material_id, "Candidate material is missing from the frozen Dataset"
                )
            else:
                runnable.append(material_id)

        batch_size = int(context.configuration["batch_size"])
        batches = max(1, (len(runnable) + batch_size - 1) // batch_size)
        condensed_dir = prepared.inputs["condensed_dir"]
        for offset in range(0, len(runnable), batch_size):
            if self._cancel_requested(context):
                raise DomainError("condensation.cancelled", "Stage 2 cancellation requested")
            material_ids = runnable[offset : offset + batch_size]
            batch_number = offset // batch_size + 1
            batch_frame = source.loc[material_ids]
            batch_path = context.sandbox / f"batch-{batch_number}.df"
            batch_manifest = context.sandbox / f"batch-{batch_number}.jsonl"
            batch_frame.to_pickle(batch_path)
            self.batch_runner(
                batch_path,
                condensed_dir,
                manifest_path=batch_manifest,
                overwrite=False,
                continue_on_error=True,
            )
            with batch_manifest.open(encoding="utf-8") as handle:
                for line in handle:
                    record = self._normalized_record(json.loads(line))
                    records[str(record["material_id"])] = record
            ordered = [
                records[material_id] for material_id in candidate_ids if material_id in records
            ]
            self._persist_checkpoint(context, condensed_dir, ordered, updated_ids=set(material_ids))
            self._publish_progress(
                context,
                total=len(candidate_ids),
                records=records,
                batch=batch_number,
                batches=batches,
            )
            if self._cancel_requested(context):
                raise DomainError("condensation.cancelled", "Stage 2 cancellation requested")

        validation = validate_archive(condensed_dir)
        for row in validation.itertuples(index=False):
            if row.status == "invalid":
                records[str(row.material_id)] = self._failure(
                    str(row.material_id), f"Condensed structure schema invalid: {row.error}"
                )
                (condensed_dir / f"{row.material_id}.json").unlink(missing_ok=True)

        ordered = [records[material_id] for material_id in candidate_ids]
        self._write_records(
            ordered,
            manifest=prepared.inputs["manifest"],
            index=prepared.inputs["index"],
            failures=prepared.inputs["failures"],
        )
        with zipfile.ZipFile(
            prepared.output_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in sorted(condensed_dir.glob("*.json")):
                archive.write(path, arcname=f"condensed/{path.name}")

        counts = {
            status: sum(record["status"] == status for record in ordered)
            for status in ("written", "skipped", "failed")
        }
        try:
            robocrys_version = version("robocrys")
        except PackageNotFoundError:
            robocrys_version = "unknown"
        identity = require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        provenance: dict[str, object] = {
            "schema_version": 1,
            "row_count": len(candidate_ids),
            "summary": {
                "total": len(candidate_ids),
                "succeeded": counts["written"] + counts["skipped"],
                "written": counts["written"],
                "skipped": counts["skipped"],
                "failed": counts["failed"],
                "attempt": context.attempt_number or 1,
                "batch_size": batch_size,
                "batches": batches,
            },
            "inputs": {
                "dataset": {
                    "id": str(context.configuration["dataset_id"]),
                    "kind": str(context.configuration["dataset_kind"]),
                    "artifact_id": str(context.configuration["dataset_artifact_id"]),
                    "artifact_sha256": str(context.configuration["dataset_artifact_sha256"]),
                },
                "composition": {
                    "run_id": str(context.configuration["composition_run_id"]),
                    "artifact_id": str(context.configuration["candidate_artifact_id"]),
                    "artifact_sha256": str(context.configuration["candidate_artifact_sha256"]),
                },
            },
            "execution": {
                "pipeline": {
                    "name": "stage-2-condensation",
                    "version": "stage-2-condensation-v1",
                },
                "scientific_core": identity.as_dict(),
                "robocrys_version": robocrys_version,
            },
        }
        prepared.provenance_path.write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return StageResult(
            row_count=len(candidate_ids),
            provenance=provenance,
            output_path=prepared.output_path,
            provenance_path=prepared.provenance_path,
            inputs=prepared.inputs,
        )

    def validate(self, result: StageResult) -> ValidationResult:
        required = [
            result.output_path,
            result.provenance_path,
            result.inputs["manifest"],
            result.inputs["index"],
            result.inputs["failures"],
        ]
        if not all(path.is_file() for path in required):
            return ValidationResult(False, "The condensation outputs are incomplete")
        try:
            index = pd.read_csv(result.inputs["index"], keep_default_na=False)
            if list(index.columns) != INDEX_COLUMNS or len(index) != result.row_count:
                return ValidationResult(False, "The condensation index schema is invalid")
            if not set(index["status"]).issubset({"written", "skipped", "failed"}):
                return ValidationResult(False, "The condensation index status is invalid")
            with zipfile.ZipFile(result.output_path) as archive:
                names = archive.namelist()
                if any(not name.startswith("condensed/") or name.endswith("/") for name in names):
                    return ValidationResult(False, "The condensation archive layout is invalid")
                if len(names) != int((index["status"] != "failed").sum()):
                    return ValidationResult(False, "The condensation archive count is invalid")
                if archive.testzip() is not None:
                    return ValidationResult(False, "The condensation archive is corrupt")
            summary = result.provenance["summary"]
            if not isinstance(summary, dict) or summary.get("total") != result.row_count:
                return ValidationResult(False, "The condensation provenance is invalid")
        except (KeyError, TypeError, ValueError, csv.Error, zipfile.BadZipFile):
            return ValidationResult(False, "The condensation outputs could not be validated")
        return ValidationResult(True)

    def publish(self, result: StageResult, context: TaskContext) -> list[ArtifactSpec]:
        del context
        return [
            ArtifactSpec(
                path=result.output_path,
                filename="condensed-structures.zip",
                kind=self.data_artifact_kind,
                content_type="application/zip",
                schema_version="1",
            ),
            ArtifactSpec(
                path=result.inputs["index"],
                filename="condensation-index.csv",
                kind="condensation-index",
                content_type="text/csv",
                schema_version="1",
            ),
            ArtifactSpec(
                path=result.inputs["failures"],
                filename="condensation-failures.csv",
                kind="condensation-failures",
                content_type="text/csv",
                schema_version="1",
            ),
            ArtifactSpec(
                path=result.inputs["manifest"],
                filename="condensation-manifest.jsonl",
                kind="condensation-manifest",
                content_type="application/x-ndjson",
                schema_version="1",
            ),
            ArtifactSpec(
                path=result.provenance_path,
                filename="condensation.provenance.json",
                kind=self.provenance_artifact_kind,
                content_type="application/json",
                schema_version="1",
            ),
        ]

    def cleanup(self, context: TaskContext) -> None:
        checkpoint = self._checkpoint_root(context)
        if checkpoint is None or context.task_id is None:
            return
        try:
            task_id = uuid.UUID(context.task_id)
        except ValueError:
            return
        with get_session_factory()() as session:
            status = session.scalar(select(Task.status).where(Task.id == task_id))
        if status == TaskStatus.SUCCEEDED:
            shutil.rmtree(checkpoint, ignore_errors=True)
