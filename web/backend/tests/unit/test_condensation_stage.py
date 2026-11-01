from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
from pymatgen.core import Lattice, Structure
from ssscreen.data.condense import condense_dataframe

from ssscreen_web.application.scientific_runtime import require_scientific_runtime
from ssscreen_web.application.stages.base import PreparedTask, TaskContext
from ssscreen_web.application.stages.condensation import CondensationStageRunner
from ssscreen_web.settings import Settings


def _structure() -> Structure:
    return Structure(Lattice.cubic(5.4), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]])


def _condensed(formula: str) -> dict[str, object]:
    return {
        "formula": formula,
        "spg_symbol": "Fm-3m",
        "crystal_system": "cubic",
        "mineral": {"type": "Halite"},
        "dimensionality": 3,
        "sites": [],
        "distances": {},
        "angles": {},
        "nnn_distances": {},
        "components": [],
        "component_makeup": {},
        "vdw_heterostructure_info": None,
    }


def _fake_batch(df_path, output_dir, **kwargs):
    return condense_dataframe(
        df_path,
        output_dir,
        manifest_path=kwargs["manifest_path"],
        overwrite=kwargs["overwrite"],
        continue_on_error=kwargs["continue_on_error"],
        condense_func=lambda structure, condenser=None: _condensed(
            structure.composition.reduced_formula
        ),
    )


def test_condensation_stage_batches_records_failures_and_publishes_contract(
    tmp_path: Path,
) -> None:
    dataset = pd.DataFrame(
        [{"structure": _structure()}],
        index=pd.Index(["mp-1"], name="material_id"),
    )
    dataset_path = tmp_path / "dataset.df"
    dataset.to_pickle(dataset_path)
    candidates_path = tmp_path / "composition-candidates.csv"
    pd.DataFrame({"material_id": ["mp-1", "mp-missing"]}).to_csv(candidates_path, index=False)
    candidates_provenance_path = tmp_path / "composition.provenance.json"
    candidates_provenance_path.write_text(json.dumps({"row_count": 2}), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        artifact_root=tmp_path / "artifacts",
        attempt_sandbox_root=tmp_path / "sandboxes",
    )
    identity = require_scientific_runtime(settings).as_dict()
    context = TaskContext(
        configuration={
            "candidate_count": 2,
            "batch_size": 1,
            "dataset_id": "00000000-0000-0000-0000-000000000001",
            "dataset_kind": "fixture",
            "dataset_artifact_id": "00000000-0000-0000-0000-000000000002",
            "dataset_artifact_sha256": "a" * 64,
            "composition_run_id": "00000000-0000-0000-0000-000000000003",
            "candidate_artifact_id": "00000000-0000-0000-0000-000000000004",
            "candidate_artifact_sha256": "b" * 64,
            "scientific_runtime": identity,
        },
        sandbox=tmp_path,
        settings=settings,
        attempt_number=1,
    )
    prepared = PreparedTask(
        output_path=tmp_path / "condensed-structures.zip",
        provenance_path=tmp_path / "condensation.provenance.json",
        inputs={
            "dataset": dataset_path,
            "candidates": candidates_path,
            "candidates_provenance": candidates_provenance_path,
            "condensed_dir": tmp_path / "condensed",
            "manifest": tmp_path / "condensation-manifest.jsonl",
            "index": tmp_path / "condensation-index.csv",
            "failures": tmp_path / "condensation-failures.csv",
        },
    )
    prepared.inputs["condensed_dir"].mkdir()
    runner = CondensationStageRunner(batch_runner=_fake_batch)

    result = runner.execute(prepared, context)

    assert runner.validate(result).valid is True
    assert result.row_count == 2
    assert result.provenance["summary"] == {
        "total": 2,
        "succeeded": 1,
        "written": 1,
        "skipped": 0,
        "failed": 1,
        "attempt": 1,
        "batch_size": 1,
        "batches": 1,
    }
    failures = pd.read_csv(prepared.inputs["failures"])
    assert failures.loc[0, "material_id"] == "mp-missing"
    assert "missing" in failures.loc[0, "error"]
    manifest = [json.loads(line) for line in prepared.inputs["manifest"].read_text().splitlines()]
    assert all(not str(record["output_path"]).startswith("/") for record in manifest)
    with zipfile.ZipFile(result.output_path) as archive:
        assert archive.namelist() == ["condensed/mp-1.json"]
    assert {artifact.kind for artifact in runner.publish(result, context)} == {
        "condensed-structures-archive",
        "condensation-index",
        "condensation-failures",
        "condensation-manifest",
        "condensation-provenance",
    }
