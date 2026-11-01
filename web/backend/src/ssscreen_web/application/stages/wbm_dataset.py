from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from ssscreen.data.wbm import load_wbm_dataset

from ssscreen_web.application.scientific_runtime import require_frozen_scientific_runtime
from ssscreen_web.application.stages.base import (
    ArtifactSpec,
    PreparedTask,
    StageResult,
    TaskContext,
    ValidationResult,
)
from ssscreen_web.application.upload_lifecycle import cleanup_wbm_quarantine
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore


class WBMUploadDatasetRunner:
    stage = "stage-1-dataset"
    task_type = "dataset.wbm-upload"
    dataset_kind = "wbm-upload"
    data_artifact_kind = "wbm-normalized-dataframe"
    provenance_artifact_kind = "wbm-dataset-provenance"
    execution_error_message = "The server could not validate the uploaded WBM dataset"
    register_dataset = True
    scientific_status = "dataset_ready"

    @staticmethod
    def _manifest(configuration: dict[str, object]) -> dict[str, dict[str, object]]:
        upload = configuration.get("upload")
        if not isinstance(upload, dict):
            raise DomainError("dataset.upload_manifest_invalid", "The upload manifest is invalid")
        manifest: dict[str, dict[str, object]] = {}
        for role in ("structures", "summary"):
            item = upload.get(role)
            if item is None and role == "summary":
                continue
            if not isinstance(item, dict):
                raise DomainError(
                    "dataset.upload_manifest_invalid", "The upload manifest is invalid"
                )
            if (
                not isinstance(item.get("key"), str)
                or not isinstance(item.get("filename"), str)
                or not isinstance(item.get("content_type"), str)
                or not isinstance(item.get("size_bytes"), int)
                or item["size_bytes"] <= 0
                or not isinstance(item.get("sha256"), str)
                or len(item["sha256"]) != 64
            ):
                raise DomainError(
                    "dataset.upload_manifest_invalid", "The upload manifest is invalid"
                )
            manifest[role] = item
        return manifest

    @staticmethod
    def _copy_verified(source: BinaryIO, target: Path, metadata: dict[str, object]) -> None:
        digest = hashlib.sha256()
        size = 0
        with target.open("xb") as handle:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size != metadata["size_bytes"] or digest.hexdigest() != metadata["sha256"]:
            target.unlink(missing_ok=True)
            raise DomainError(
                "dataset.upload_integrity_failed",
                "An uploaded file no longer matches its recorded SHA-256 and size",
            )

    def prepare(self, context: TaskContext) -> PreparedTask:
        require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        manifest = self._manifest(context.configuration)
        context.sandbox.mkdir(parents=True, exist_ok=True)
        quarantine = FileSystemArtifactStore(context.settings.uploads_quarantine_root)
        inputs: dict[str, Path] = {}
        for role, metadata in manifest.items():
            suffix = Path(str(metadata["filename"])).suffix.lower()
            target = context.sandbox / (
                "structures.extxyz" if role == "structures" else f"summary{suffix}"
            )
            with quarantine.open_read(str(metadata["key"])) as source:
                self._copy_verified(source, target, metadata)
            inputs[role] = target
        return PreparedTask(
            output_path=context.sandbox / "wbm.df",
            provenance_path=context.sandbox / "wbm.df.provenance.json",
            inputs=inputs,
        )

    def execute(self, prepared: PreparedTask, context: TaskContext) -> StageResult:
        try:
            frame = load_wbm_dataset(
                xyz_path=prepared.inputs["structures"],
                summary_path=prepared.inputs.get("summary"),
                output=prepared.output_path,
                strict=True,
            )
        except (OSError, TypeError, ValueError) as error:
            raise DomainError("dataset.wbm_schema_invalid", str(error)) from error
        manifest = self._manifest(context.configuration)
        identity = require_frozen_scientific_runtime(
            context.settings, context.configuration.get("scientific_runtime")
        )
        provenance_inputs = {
            role: {
                key: metadata[key] for key in ("filename", "content_type", "size_bytes", "sha256")
            }
            for role, metadata in manifest.items()
        }
        provenance: dict[str, object] = {
            "schema_version": 1,
            "backend": "upload",
            "source": "wbm",
            "row_count": len(frame),
            "inputs": provenance_inputs,
            "validation": {
                "strict": True,
                "summary_alignment": "row-count-and-identifiers-when-present",
                "required_numeric_fields": ["band_gap", "e_hull"],
            },
            "packages": {
                "ase": importlib.metadata.version("ase"),
                "pandas": pd.__version__,
                "pymatgen": importlib.metadata.version("pymatgen"),
            },
            "execution": {
                "pipeline": {
                    "name": "stage-1-wbm-upload",
                    "version": "stage-1-wbm-upload-v1",
                },
                "scientific_core": identity.as_dict(),
            },
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
            inputs=prepared.inputs,
        )

    def validate(self, result: StageResult) -> ValidationResult:
        if result.row_count <= 0:
            return ValidationResult(False, "The uploaded WBM dataset contains no structures")
        if not result.output_path.is_file() or not result.provenance_path.is_file():
            return ValidationResult(False, "The normalized dataset outputs are incomplete")
        frame = pd.read_pickle(result.output_path)
        required = {"formula", "band_gap", "e_hull", "structure", "source"}
        if len(frame) != result.row_count or not frame.index.is_unique:
            return ValidationResult(False, "The normalized dataset index is invalid")
        if not required.issubset(frame.columns):
            return ValidationResult(False, "The normalized dataset schema is incomplete")
        inputs = result.provenance.get("inputs")
        if not isinstance(inputs, dict) or "structures" not in inputs:
            return ValidationResult(False, "The upload provenance is incomplete")
        if any(
            not isinstance(item, dict)
            or "key" in item
            or "path" in item
            or len(str(item.get("sha256", ""))) != 64
            for item in inputs.values()
        ):
            return ValidationResult(False, "The upload provenance exposes storage details")
        execution = result.provenance.get("execution")
        pipeline = execution.get("pipeline") if isinstance(execution, dict) else None
        if not isinstance(pipeline, dict) or pipeline.get("version") != "stage-1-wbm-upload-v1":
            return ValidationResult(False, "The pipeline provenance is invalid")
        return ValidationResult(True)

    def publish(self, result: StageResult, context: TaskContext) -> list[ArtifactSpec]:
        del context
        specs = [
            ArtifactSpec(
                path=result.inputs["structures"],
                filename="structures.extxyz",
                kind="wbm-source-structures",
                content_type="chemical/x-xyz",
                schema_version="1",
            )
        ]
        if "summary" in result.inputs:
            suffix = result.inputs["summary"].suffix
            specs.append(
                ArtifactSpec(
                    path=result.inputs["summary"],
                    filename=f"summary{suffix}",
                    kind="wbm-source-summary",
                    content_type="text/tab-separated-values" if suffix == ".tsv" else "text/csv",
                    schema_version="1",
                )
            )
        specs.extend(
            [
                ArtifactSpec(
                    path=result.output_path,
                    filename="wbm.df",
                    kind=self.data_artifact_kind,
                    content_type="application/x-pandas-pickle",
                    schema_version="1",
                ),
                ArtifactSpec(
                    path=result.provenance_path,
                    filename="wbm.df.provenance.json",
                    kind=self.provenance_artifact_kind,
                    content_type="application/json",
                    schema_version="1",
                ),
            ]
        )
        return specs

    def cleanup(self, context: TaskContext) -> None:
        cleanup_wbm_quarantine(context.configuration, settings=context.settings)
