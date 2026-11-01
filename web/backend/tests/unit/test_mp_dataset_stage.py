from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ssscreen_web.application.scientific_runtime import require_scientific_runtime
from ssscreen_web.application.stages.base import TaskContext
from ssscreen_web.application.stages.mp_dataset import MPOfflineDatasetRunner
from ssscreen_web.settings import Settings


def test_mp_offline_stage_runs_validates_and_sanitizes_database_path(tmp_path: Path) -> None:
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite-fixture")

    def fake_loader(**kwargs):
        output = Path(kwargs["output"])
        provenance_path = Path(kwargs["provenance_path"])
        frame = pd.DataFrame({"formula": ["CaS"]}, index=["mp-1672"])
        frame.to_pickle(output)
        provenance = {
            "backend": "offline",
            "row_count": 1,
            "database": {
                "reference": kwargs["database_reference"],
                "sha256": "a" * 64,
            },
        }
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        return frame

    settings = Settings(
        _env_file=None,
        mp_offline_database_path=database,
        mp_offline_database_reference="fixture-snapshot",
    )
    identity = require_scientific_runtime(settings).as_dict()
    context = TaskContext(
        configuration={"max_e_hull": 0.01, "scientific_runtime": identity},
        sandbox=tmp_path / "sandbox",
        settings=settings,
    )
    runner = MPOfflineDatasetRunner(loader=fake_loader)

    prepared = runner.prepare(context)
    result = runner.execute(prepared, context)
    validation = runner.validate(result)
    artifacts = runner.publish(result, context)

    assert validation.valid is True
    assert result.row_count == 1
    assert result.provenance["database"] == {
        "reference": "fixture-snapshot",
        "sha256": "a" * 64,
    }
    assert result.provenance["execution"] == {
        "pipeline": {"name": "stage-1-mp-offline", "version": "stage-1-mp-offline-v1"},
        "scientific_core": identity,
    }
    assert {artifact.kind for artifact in artifacts} == {
        "mp-normalized-dataframe",
        "mp-dataset-provenance",
    }


def test_mp_offline_stage_rejects_empty_dataset(tmp_path: Path) -> None:
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite-fixture")

    def fake_loader(**kwargs):
        output = Path(kwargs["output"])
        provenance_path = Path(kwargs["provenance_path"])
        frame = pd.DataFrame()
        frame.to_pickle(output)
        provenance_path.write_text(
            json.dumps(
                {
                    "backend": "offline",
                    "row_count": 0,
                    "database": {"reference": "fixture", "sha256": "a" * 64},
                }
            ),
            encoding="utf-8",
        )
        return frame

    settings = Settings(_env_file=None, mp_offline_database_path=database)
    identity = require_scientific_runtime(settings).as_dict()
    context = TaskContext(
        configuration={"max_e_hull": 0.01, "scientific_runtime": identity},
        sandbox=tmp_path / "sandbox",
        settings=settings,
    )
    runner = MPOfflineDatasetRunner(loader=fake_loader)
    result = runner.execute(runner.prepare(context), context)

    assert runner.validate(result).valid is False
