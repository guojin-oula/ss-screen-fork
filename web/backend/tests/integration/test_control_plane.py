from __future__ import annotations

import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError
from ssscreen.data.condense import condense_dataframe

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.events import _stream_events
from ssscreen_web.domain.enums import AttemptStatus, RunStatus, TaskStatus
from ssscreen_web.infrastructure.database import get_session_factory
from ssscreen_web.infrastructure.models import (
    Artifact,
    Attempt,
    Dataset,
    Event,
    OutboxMessage,
    ProjectMember,
    Run,
    Task,
    User,
)
from ssscreen_web.main import create_app
from ssscreen_web.settings import get_settings
from ssscreen_web.workers.celery_app import reconcile_stale_published_outbox
from ssscreen_web.workers.composition_task import screen_composition
from ssscreen_web.workers.condensation_task import condense_batch
from ssscreen_web.workers.condensation_task import runner as condensation_runner
from ssscreen_web.workers.example_task import generate_json, recover_stale_demo_tasks
from ssscreen_web.workers.mp_dataset_task import (
    prepare_mp_offline_dataset,
    recover_stale_mp_dataset_tasks,
)
from ssscreen_web.workers.mp_dataset_task import runner as mp_runner
from ssscreen_web.workers.wbm_dataset_task import prepare_wbm_dataset

WBM_EXTXYZ = b"""1
Lattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3 WBM_idx=0 WBM_gap=1.2 WBM_e_hull=0.01 pbc="T T T"
Na 0 0 0
"""

WBM_COMPOSITION_EXTXYZ = b"""2
Lattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3 WBM_idx=0 WBM_gap=0.2 WBM_e_hull=0.0 pbc="T T T"
Na 0 0 0
Cl 1.5 1.5 1.5
2
Lattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3 WBM_idx=1 WBM_gap=0.5 WBM_e_hull=0.0 pbc="T T T"
K 0 0 0
Cl 1.5 1.5 1.5
"""


def test_development_identity_creation_is_concurrency_safe() -> None:
    client = TestClient(create_app())
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.get("/api/v1/me"), range(8)))
    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["id"] for response in responses}) == 1


def test_validation_errors_use_stable_api_envelope() -> None:
    response = TestClient(create_app()).post("/api/v1/projects", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "request.validation_failed"
    assert response.json()["field_errors"][0]["field"] == "name"
    assert response.json()["trace_id"] == response.headers["X-Trace-ID"]


def test_ready_reports_scientific_core_identity_check(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "uploads_quarantine_root", tmp_path / "quarantine")

    response = TestClient(create_app()).get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["scientific_core"] == "ok"


def test_demo_run_reaches_succeeded_and_downloads_hashed_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 1)
    client = TestClient(create_app())

    project = client.post("/api/v1/projects", json={"name": "Infrared alloys"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"pipeline": "control-plane-demo", "message": "deterministic"},
    ).json()
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    result = generate_json.run(task_id=task["id"])
    assert result["status"] == "succeeded"

    run_response = client.get(f"/api/v1/runs/{run['id']}")
    assert run_response.json()["status"] == "SUCCEEDED"
    tasks = client.get(f"/api/v1/runs/{run['id']}/tasks").json()
    assert tasks[0]["scientific_status"] == "not_applicable"
    artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()
    assert len(artifacts) == 1
    download = client.get(f"/api/v1/artifacts/{artifacts[0]['id']}/download")
    assert hashlib.sha256(download.content).hexdigest() == artifacts[0]["sha256"]
    assert b'"ssscreen_version": "1.0"' in download.content
    duplicate = generate_json.run(task_id=task["id"], attempt_number=1)
    assert duplicate["status"] == "duplicate"
    with get_session_factory()() as session:
        assert session.query(Artifact).count() == 1


def test_stage_1_mp_offline_run_registers_dataset_and_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite-fixture")
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "mp_offline_database_path", database)
    monkeypatch.setattr(settings, "mp_offline_database_reference", "fixture-snapshot")
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 1)

    def fake_loader(**kwargs):
        output = Path(kwargs["output"])
        provenance_path = Path(kwargs["provenance_path"])
        frame = pd.DataFrame({"formula": ["CaS"]}, index=["mp-1672"])
        frame.to_pickle(output)
        provenance = {
            "schema_version": 1,
            "backend": "offline",
            "row_count": 1,
            "query": {"energy_above_hull_eV_per_atom": {"min": 0.0, "max": 0.01}},
            "database": {
                "reference": kwargs["database_reference"],
                "size_bytes": database.stat().st_size,
                "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
            },
        }
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        return frame

    monkeypatch.setattr(mp_runner, "loader", fake_loader)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Stage 1"}).json()
    run_response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-1-mp-offline",
            "message": "Prepare MP snapshot",
            "dataset_label": "MP stable materials",
            "max_e_hull": 0.01,
        },
    )
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["pipeline_version"] == "stage-1-mp-offline-v1"
    assert run["configuration"]["scientific_runtime"]["version"] == "1.0"
    assert (
        run["configuration"]["scientific_runtime"]["version"]
        == run["configuration"]["scientific_runtime"]["distribution_version"]
    )
    assert len(run["configuration"]["scientific_runtime"]["source_sha256"]) == 64
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    assert task["task_type"] == "dataset.mp-offline"
    with get_session_factory()() as session:
        assert session.scalar(select(OutboxMessage.topic)) == "ssscreen_web.dataset.mp_offline"
    result = prepare_mp_offline_dataset.run(task_id=task["id"], attempt_number=1)
    assert result["status"] == "succeeded"

    datasets = client.get(f"/api/v1/projects/{project['id']}/datasets").json()
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset["label"] == "MP stable materials"
    assert dataset["row_count"] == 1
    assert dataset["provenance"]["database"]["reference"] == "fixture-snapshot"
    assert "path" not in dataset["provenance"]["database"]
    assert (
        dataset["provenance"]["execution"]["scientific_core"]
        == run["configuration"]["scientific_runtime"]
    )
    assert dataset["provenance"]["execution"]["pipeline"]["version"] == run["pipeline_version"]
    artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()
    assert {item["kind"] for item in artifacts} == {
        "mp-normalized-dataframe",
        "mp-dataset-provenance",
    }
    for artifact in artifacts:
        download = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        assert hashlib.sha256(download.content).hexdigest() == artifact["sha256"]
    with get_session_factory()() as session:
        assert session.query(Dataset).count() == 1


def test_stage_1_wbm_upload_is_quarantined_validated_and_registered(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "uploads_quarantine_root", quarantine)
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 1)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "WBM upload"}).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "WBM strict fixture"},
        files={"xyz_file": ("fixture.extxyz", WBM_EXTXYZ, "chemical/x-xyz")},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["pipeline_version"] == "stage-1-wbm-upload-v1"
    manifest = run["configuration"]["upload"]["structures"]
    assert manifest["filename"] == "fixture.extxyz"
    assert manifest["sha256"] == hashlib.sha256(WBM_EXTXYZ).hexdigest()
    assert not Path(manifest["key"]).is_absolute()
    assert (quarantine / manifest["key"]).read_bytes() == WBM_EXTXYZ

    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    assert task["task_type"] == "dataset.wbm-upload"
    result = prepare_wbm_dataset.run(task_id=task["id"], attempt_number=1)
    assert result["status"] == "succeeded"
    assert not (quarantine / manifest["key"]).exists()

    datasets = client.get(f"/api/v1/projects/{project['id']}/datasets").json()
    assert datasets[0]["kind"] == "wbm-upload"
    assert datasets[0]["row_count"] == 1
    provenance = datasets[0]["provenance"]
    assert provenance["inputs"]["structures"]["sha256"] == manifest["sha256"]
    assert "key" not in provenance["inputs"]["structures"]
    artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()
    assert {artifact["kind"] for artifact in artifacts} == {
        "wbm-source-structures",
        "wbm-normalized-dataframe",
        "wbm-dataset-provenance",
    }


def test_wbm_upload_rejects_unsafe_filename(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "uploads_quarantine_root", tmp_path / "quarantine")
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Unsafe upload"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Unsafe"},
        files={"xyz_file": ("../escape.extxyz", WBM_EXTXYZ, "chemical/x-xyz")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "upload.invalid_filename"


def test_cancelling_wbm_draft_removes_all_quarantine_inputs(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "uploads_quarantine_root", quarantine)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Cancel draft"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Disposable draft"},
        files={
            "xyz_file": ("fixture.extxyz", WBM_EXTXYZ, "chemical/x-xyz"),
            "summary_file": ("summary.csv", b"WBM_idx\n0\n", "text/csv"),
        },
    ).json()
    manifest = run["configuration"]["upload"]
    paths = [quarantine / manifest[role]["key"] for role in ("structures", "summary")]
    assert all(path.is_file() for path in paths)

    response = client.post(f"/api/v1/runs/{run['id']}/actions/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert all(not path.exists() for path in paths)


def test_cancelling_queued_wbm_task_removes_quarantine_input(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "uploads_quarantine_root", quarantine)
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Cancel queued"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Queued upload"},
        files={"xyz_file": ("fixture.extxyz", WBM_EXTXYZ, "chemical/x-xyz")},
    ).json()
    path = quarantine / run["configuration"]["upload"]["structures"]["key"]
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()

    response = client.post(f"/api/v1/tasks/{task['id']}/actions/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert not path.exists()


def test_worker_finishes_running_wbm_cancellation_and_removes_input(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "uploads_quarantine_root", quarantine)
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Cancel running"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Running upload"},
        files={"xyz_file": ("fixture.extxyz", WBM_EXTXYZ, "chemical/x-xyz")},
    ).json()
    path = quarantine / run["configuration"]["upload"]["structures"]["key"]
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    with get_session_factory()() as session:
        stored_run = session.get(Run, run["id"])
        stored_task = session.get(Task, task["id"])
        attempt = session.scalar(select(Attempt).where(Attempt.task_id == stored_task.id))
        stored_run.status = RunStatus.RUNNING
        stored_task.status = TaskStatus.CANCEL_REQUESTED
        attempt.status = AttemptStatus.RUNNING
        session.commit()

    result = prepare_wbm_dataset.run(task_id=task["id"], attempt_number=1)

    assert result["status"] == "cancelled"
    assert client.get(f"/api/v1/runs/{run['id']}").json()["status"] == "CANCELLED"
    assert not path.exists()


def test_failed_wbm_validation_retains_quarantine_input_for_retry(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    quarantine = tmp_path / "quarantine"
    invalid = WBM_EXTXYZ.replace(b" WBM_gap=1.2 WBM_e_hull=0.01", b"")
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "uploads_quarantine_root", quarantine)
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Retain failure"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Retryable upload"},
        files={"xyz_file": ("invalid.extxyz", invalid, "chemical/x-xyz")},
    ).json()
    path = quarantine / run["configuration"]["upload"]["structures"]["key"]
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()

    result = prepare_wbm_dataset.run(task_id=task["id"], attempt_number=1)

    assert result["status"] == "failed"
    assert result["error_code"] == "dataset.wbm_schema_invalid"
    assert path.is_file()


def test_stage_1a_composition_uses_frozen_dataset_artifact_and_publishes_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "uploads_quarantine_root", tmp_path / "quarantine")
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Composition"}).json()
    dataset_run = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Two salts"},
        files={
            "xyz_file": (
                "two-salts.extxyz",
                WBM_COMPOSITION_EXTXYZ,
                "chemical/x-xyz",
            )
        },
    ).json()
    dataset_task = client.post(f"/api/v1/runs/{dataset_run['id']}/actions/start").json()
    assert (
        prepare_wbm_dataset.run(task_id=dataset_task["id"], attempt_number=1)["status"]
        == "succeeded"
    )
    dataset = client.get(f"/api/v1/projects/{project['id']}/datasets").json()[0]

    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-1a-composition",
            "dataset_id": dataset["id"],
            "nelems": 2,
            "max_bandgap": 1.0,
            "max_e_hull": 0.0,
            "min_group_size": 2,
            "min_x_elements": 2,
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["pipeline_version"] == "stage-1a-composition-v1"
    assert run["configuration"]["dataset_id"] == dataset["id"]
    assert len(run["configuration"]["dataset_artifact_sha256"]) == 64
    assert "dataset_artifact_key" not in run["configuration"]
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()

    result = screen_composition.run(task_id=task["id"], attempt_number=1)

    assert result == {"status": "succeeded", "row_count": 2}
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["scientific_status"] == "composition_ready"
    artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()
    assert {artifact["kind"] for artifact in artifacts} == {
        "composition-candidates",
        "composition-provenance",
    }
    candidate = next(item for item in artifacts if item["kind"] == "composition-candidates")
    csv = client.get(f"/api/v1/artifacts/{candidate['id']}/download").text
    assert "Cl2X1" in csv
    assert "wbm-0" in csv and "wbm-1" in csv
    preview = client.get(f"/api/v1/runs/{run['id']}/composition-preview?limit=1")
    assert preview.status_code == 200
    assert preview.json()["artifact_id"] == candidate["id"]
    assert preview.json()["total_rows"] == 2
    assert preview.json()["limit"] == 1
    assert len(preview.json()["candidates"]) == 1
    assert preview.json()["candidates"][0] == {
        "template": "Cl2X1",
        "material_id": "wbm-0",
        "x_element": "Na",
        "formula": "NaCl",
        "composition": "NaCl",
        "band_gap": 0.2,
        "e_hull": 0.0,
        "source": "wbm",
    }
    with get_session_factory()() as session:
        assert session.query(Dataset).count() == 1


def test_stage_2_condensation_freezes_both_inputs_and_publishes_batch_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "attempt_sandbox_root", tmp_path / "sandboxes")
    monkeypatch.setattr(settings, "uploads_quarantine_root", tmp_path / "quarantine")
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)

    batch_calls = 0

    def fake_batch(df_path, output_dir, **kwargs):
        nonlocal batch_calls
        batch_calls += 1
        if batch_calls == 2:
            raise RuntimeError("simulated worker interruption after checkpoint")

        def fake_condense(structure, condenser=None):
            return {
                "formula": structure.composition.reduced_formula,
                "spg_symbol": "Pm-3m",
                "crystal_system": "cubic",
                "mineral": {"type": "test"},
                "dimensionality": 3,
                "sites": [],
                "distances": {},
                "angles": {},
                "nnn_distances": {},
                "components": [],
                "component_makeup": {},
                "vdw_heterostructure_info": None,
            }

        return condense_dataframe(
            df_path,
            output_dir,
            manifest_path=kwargs["manifest_path"],
            overwrite=kwargs["overwrite"],
            continue_on_error=kwargs["continue_on_error"],
            condense_func=fake_condense,
        )

    monkeypatch.setattr(condensation_runner, "batch_runner", fake_batch)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Condensation"}).json()
    dataset_run = client.post(
        f"/api/v1/projects/{project['id']}/datasets/wbm-upload",
        data={"dataset_label": "Two salts"},
        files={"xyz_file": ("two-salts.extxyz", WBM_COMPOSITION_EXTXYZ, "chemical/x-xyz")},
    ).json()
    dataset_task = client.post(f"/api/v1/runs/{dataset_run['id']}/actions/start").json()
    assert (
        prepare_wbm_dataset.run(task_id=dataset_task["id"], attempt_number=1)["status"]
        == "succeeded"
    )
    dataset = client.get(f"/api/v1/projects/{project['id']}/datasets").json()[0]
    composition_run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-1a-composition",
            "dataset_id": dataset["id"],
            "nelems": 2,
            "max_bandgap": 1.0,
            "max_e_hull": 0.0,
            "min_group_size": 2,
            "min_x_elements": 2,
        },
    ).json()
    composition_task = client.post(f"/api/v1/runs/{composition_run['id']}/actions/start").json()
    assert (
        screen_composition.run(task_id=composition_task["id"], attempt_number=1)["status"]
        == "succeeded"
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-2-condensation",
            "composition_run_id": composition_run["id"],
            "batch_size": 1,
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["pipeline_version"] == "stage-2-condensation-v1"
    assert run["configuration"]["candidate_count"] == 2
    assert len(run["configuration"]["candidate_artifact_sha256"]) == 64
    assert len(run["configuration"]["dataset_artifact_sha256"]) == 64
    assert all("key" not in key for key in run["configuration"])
    preview = client.get(f"/api/v1/runs/{run['id']}/condensation-preview").json()
    assert preview["total"] == 2
    assert preview["completed"] == 0

    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    first = condense_batch.run(task_id=task["id"], attempt_number=1)

    assert first["status"] == "failed"
    assert (tmp_path / "sandboxes" / "checkpoints" / task["id"]).is_dir()
    preview = client.get(f"/api/v1/runs/{run['id']}/condensation-preview").json()
    assert preview["completed"] == 1
    assert preview["written"] == 1

    retry = client.post(f"/api/v1/tasks/{task['id']}/actions/retry")
    assert retry.status_code == 200
    assert retry.json()["number"] == 2
    result = condense_batch.run(task_id=task["id"], attempt_number=2)

    assert result == {"status": "succeeded", "row_count": 2}
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["scientific_status"] == "condensation_ready"
    artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()
    assert {artifact["kind"] for artifact in artifacts} == {
        "condensed-structures-archive",
        "condensation-index",
        "condensation-failures",
        "condensation-manifest",
        "condensation-provenance",
    }
    preview = client.get(f"/api/v1/runs/{run['id']}/condensation-preview").json()
    assert preview == {
        "total": 2,
        "completed": 2,
        "succeeded": 2,
        "written": 1,
        "skipped": 1,
        "failed": 0,
        "batch": 2,
        "batches": 2,
        "attempt": 2,
        "failures": [],
    }
    assert not (tmp_path / "sandboxes" / "checkpoints" / task["id"]).exists()


def test_stage_1_run_requires_server_configured_snapshot(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "mp_offline_database_path", None)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "No snapshot"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-1-mp-offline",
            "message": "Unavailable",
            "dataset_label": "Unavailable",
            "max_e_hull": 0.01,
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "dataset.offline_not_configured"


def test_stage_1_run_rejects_core_identity_change_before_start(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite-fixture")
    monkeypatch.setattr(settings, "mp_offline_database_path", database)
    monkeypatch.setattr(settings, "ssscreen_core_revision", "git:revision-a")
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Core identity"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-1-mp-offline",
            "message": "Freeze identity",
            "dataset_label": "Frozen core",
            "max_e_hull": 0.01,
        },
    ).json()

    monkeypatch.setattr(settings, "ssscreen_core_revision", "git:revision-b")
    response = client.post(f"/api/v1/runs/{run['id']}/actions/start")

    assert response.status_code == 409
    assert response.json()["code"] == "runtime.core_identity_changed"
    assert client.get(f"/api/v1/runs/{run['id']}").json()["status"] == "DRAFT"


def test_stale_stage_1_worker_is_marked_failed(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite-fixture")
    monkeypatch.setattr(settings, "mp_offline_database_path", database)
    monkeypatch.setattr(settings, "mp_dataset_task_stale_seconds", 1.0)
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Stage recovery"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={
            "pipeline": "stage-1-mp-offline",
            "message": "Recover Stage 1",
            "dataset_label": "Recovery",
            "max_e_hull": 0.01,
        },
    ).json()
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    with get_session_factory()() as session:
        stored_run = session.get(Run, run["id"])
        stored_task = session.get(Task, task["id"])
        attempt = session.scalar(select(Attempt).where(Attempt.task_id == stored_task.id))
        stored_run.status = RunStatus.RUNNING
        stored_task.status = TaskStatus.RUNNING
        stored_task.started_at = datetime.now(UTC) - timedelta(seconds=5)
        attempt.status = AttemptStatus.RUNNING
        attempt.started_at = stored_task.started_at
        session.commit()

    assert recover_stale_mp_dataset_tasks() == 1
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["status"] == "FAILED"
    assert detail["attempts"][0]["error_code"] == "worker.lost"


def test_project_list_includes_owner_and_latest_run() -> None:
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Overview"}).json()
    run = client.post(f"/api/v1/projects/{project['id']}/runs", json={"message": "latest"}).json()
    listed = client.get("/api/v1/projects").json()[0]
    assert listed["owner_display_name"] == "SS-Screen Developer"
    assert listed["latest_run_id"] == run["id"]
    assert listed["latest_run_status"] == "DRAFT"


def test_viewer_cannot_start_and_cross_project_access_is_hidden(monkeypatch) -> None:
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 1)
    owner_client = TestClient(create_app())
    project = owner_client.post("/api/v1/projects", json={"name": "Private"}).json()
    run = owner_client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"message": "private"}
    ).json()

    with get_session_factory()() as session:
        viewer = User(oidc_subject="viewer", display_name="Viewer")
        outsider = User(oidc_subject="outsider", display_name="Outsider")
        session.add_all([viewer, outsider])
        session.flush()
        session.add(ProjectMember(project_id=project["id"], user_id=viewer.id, role="viewer"))
        session.commit()
        session.refresh(viewer)
        session.refresh(outsider)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: viewer
    viewer_client = TestClient(app)
    response = viewer_client.post(f"/api/v1/runs/{run['id']}/actions/start")
    assert response.status_code == 403
    assert response.json()["code"] == "project.forbidden"

    app.dependency_overrides[get_current_user] = lambda: outsider
    outsider_client = TestClient(app)
    assert outsider_client.get(f"/api/v1/runs/{run['id']}").status_code == 404


def test_editor_can_create_a_run() -> None:
    owner_client = TestClient(create_app())
    project = owner_client.post("/api/v1/projects", json={"name": "Shared"}).json()
    with get_session_factory()() as session:
        editor = User(oidc_subject="editor", display_name="Editor")
        session.add(editor)
        session.flush()
        session.add(ProjectMember(project_id=project["id"], user_id=editor.id, role="editor"))
        session.commit()
        session.refresh(editor)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: editor
    response = TestClient(app).post(
        f"/api/v1/projects/{project['id']}/runs", json={"message": "editor run"}
    )
    assert response.status_code == 201


def test_run_optimistic_lock_rejects_stale_update() -> None:
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Concurrency"}).json()
    run_id = client.post(f"/api/v1/projects/{project['id']}/runs", json={"message": "lock"}).json()[
        "id"
    ]
    factory = get_session_factory()
    with factory() as first, factory() as second:
        first_run = first.get(Run, run_id)
        second_run = second.get(Run, run_id)
        first_run.configuration = {"message": "first"}
        first.commit()
        second_run.configuration = {"message": "second"}
        with pytest.raises(StaleDataError):
            second.commit()


def test_sse_cursor_only_returns_newer_committed_events() -> None:
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "SSE"}).json()
    run = client.post(f"/api/v1/projects/{project['id']}/runs", json={"message": "events"}).json()
    with get_session_factory()() as session:
        ids = list(
            session.scalars(
                select(Event.id).where(Event.run_id == run["id"]).order_by(Event.id)
            ).all()
        )
    client.post(f"/api/v1/runs/{run['id']}/actions/cancel")

    class ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    async def first_resumed_event() -> str:
        stream = _stream_events(
            ConnectedRequest(), run["id"], ids[-1], get_settings()  # type: ignore[arg-type]
        )
        return await anext(stream)

    event = asyncio.run(first_resumed_event())
    assert "run.cancel_requested" in event
    assert f"id: {ids[-1]}\n" not in event


def test_failed_task_requires_explicit_retry(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 1)
    monkeypatch.setattr("ssscreen_web.api.tasks.dispatch_pending_outbox", lambda: 1)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Retry"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"message": "fail once", "simulate_failure": True},
    ).json()
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    assert generate_json.run(task_id=task["id"], attempt_number=1)["status"] == "failed"
    retry = client.post(f"/api/v1/tasks/{task['id']}/actions/retry")
    assert retry.status_code == 200
    assert retry.json()["number"] == 2
    assert generate_json.run(task_id=task["id"], attempt_number=1)["status"] == "superseded"
    assert generate_json.run(task_id=task["id"], attempt_number=2)["status"] == "succeeded"


def test_queued_task_cancel_is_consistent_and_removes_pending_delivery(monkeypatch) -> None:
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Cancel"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"message": "cancel me"}
    ).json()
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    response = client.post(f"/api/v1/tasks/{task['id']}/actions/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    with get_session_factory()() as session:
        attempt = session.scalar(select(Attempt).where(Attempt.task_id == task["id"]))
        stored_run = session.get(Run, run["id"])
        assert attempt.status == AttemptStatus.CANCELLED
        assert stored_run.status == RunStatus.CANCELLED
        assert session.query(OutboxMessage).count() == 0


def test_stale_demo_worker_is_marked_failed(monkeypatch) -> None:
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_task_stale_seconds", 1.0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Recovery"}).json()
    run = client.post(f"/api/v1/projects/{project['id']}/runs", json={"message": "recover"}).json()
    task = client.post(f"/api/v1/runs/{run['id']}/actions/start").json()
    with get_session_factory()() as session:
        stored_run = session.get(Run, run["id"])
        stored_task = session.get(Task, task["id"])
        attempt = session.scalar(select(Attempt).where(Attempt.task_id == stored_task.id))
        stored_run.status = RunStatus.RUNNING
        stored_task.status = TaskStatus.RUNNING
        stored_task.started_at = datetime.now(UTC) - timedelta(seconds=5)
        attempt.status = AttemptStatus.RUNNING
        attempt.started_at = stored_task.started_at
        session.commit()
    assert recover_stale_demo_tasks() == 1
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["status"] == "FAILED"
    assert detail["attempts"][0]["error_code"] == "worker.lost"


def test_unconfirmed_published_delivery_is_reconciled(monkeypatch) -> None:
    monkeypatch.setattr("ssscreen_web.api.runs.dispatch_pending_outbox", lambda: 0)
    settings = get_settings()
    monkeypatch.setattr(settings, "outbox_redelivery_seconds", 1.0)
    client = TestClient(create_app())
    project = client.post("/api/v1/projects", json={"name": "Redelivery"}).json()
    run = client.post(
        f"/api/v1/projects/{project['id']}/runs", json={"message": "redeliver"}
    ).json()
    client.post(f"/api/v1/runs/{run['id']}/actions/start")
    with get_session_factory()() as session:
        message = session.scalar(select(OutboxMessage))
        message.status = "PUBLISHED"
        message.published_at = datetime.now(UTC) - timedelta(seconds=5)
        session.commit()
    assert reconcile_stale_published_outbox() == 1
    with get_session_factory()() as session:
        message = session.scalar(select(OutboxMessage))
        assert message.status == "PENDING"
        assert message.last_error == "delivery.unconfirmed"
