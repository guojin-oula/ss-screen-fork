"""Tests for external band-gap candidate export and result schema."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from monty.serialization import loadfn
from pymatgen.core import Lattice, Structure

from ssscreen.data.io import dump_group_df
from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.gap_export import (
    GAP_SCHEMA_VERSION,
    export_gap_candidates,
    make_gap_task_id,
    validate_gap_results,
)


def _structure() -> Structure:
    return Structure(Lattice.cubic(5.4), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]])


def _supercell_structure() -> Structure:
    structure = _structure().copy()
    structure.make_supercell((2, 1, 1))
    return structure


def _dataset() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "material_id": "mp-1",
                "formula": "CaS",
                "composition": "CaS",
                "band_gap": 0.0,
                "e_hull": 0.0,
                "structure": _structure(),
                "source": "fixture",
            },
            {
                "material_id": "mp-2",
                "formula": "CaSe",
                "composition": "CaSe",
                "band_gap": 0.3,
                "e_hull": 0.0,
                "structure": _structure(),
                "source": "fixture",
            },
        ]
    ).set_index("material_id")


def test_export_gap_candidates_writes_unique_metadata_and_structures(tmp_path):
    groups = [
        StructureGroup(
            entry_idx=[0, 1],
            A_elements=[["Ca"], ["Ca"]],
            compositions=["CaS", "CaSe"],
            group_size=2,
            X_element=["S", "Se"],
            mp_ids=["mp-1", "mp-2"],
            group_repr="descriptor",
            band_gaps=[0.0, 0.3],
        )
    ]
    groups_path = tmp_path / "groups.json"
    dataset_path = tmp_path / "dataset.df"
    output = tmp_path / "gap_candidates.csv"
    structure_dir = tmp_path / "structures"
    dump_group_df(groups, groups_path)
    _dataset().to_pickle(dataset_path)

    exported = export_gap_candidates(
        groups_path,
        dataset_path,
        output,
        structure_dir=structure_dir,
        method="hse06",
    )

    assert list(exported["material_id"]) == ["mp-1", "mp-2"]
    assert set(exported.columns) >= {
        "method",
        "source_group_index",
        "material_id",
        "formula",
        "composition",
        "initial_band_gap",
        "e_hull",
        "natoms",
        "structure_path",
    }
    assert set(exported["method"]) == {"hse06"}
    assert set(exported["schema_version"]) == {GAP_SCHEMA_VERSION}
    assert exported["task_id"].str.fullmatch(r"gap-[0-9a-f]{24}").all()
    assert exported["structure_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert (structure_dir / "mp-1.json").exists()
    assert (structure_dir / "mp-2.json").exists()


def test_export_gap_candidates_writes_portable_bundle_templates(tmp_path):
    groups = [
        StructureGroup(
            entry_idx=[0],
            A_elements=[["Ca"]],
            compositions=["CaS"],
            group_size=1,
            X_element=["S"],
            mp_ids=["mp-1"],
            group_repr="descriptor",
        )
    ]
    groups_path = tmp_path / "groups.json"
    dataset_path = tmp_path / "dataset.df"
    output = tmp_path / "gap_tasks.csv"
    results_template = tmp_path / "gap_results_template.csv"
    method_template = tmp_path / "method_metadata.json"
    structure_dir = tmp_path / "structures"
    dump_group_df(groups, groups_path)
    _dataset().to_pickle(dataset_path)

    exported = export_gap_candidates(
        groups_path,
        dataset_path,
        output,
        structure_dir=structure_dir,
        structure_formats=("json", "cif", "poscar"),
        results_template=results_template,
        method_metadata_template=method_template,
        method="vasp-hse06-pbe54-nosoc-v1",
    )

    assert (structure_dir / "mp-1.json").exists()
    assert (structure_dir / "mp-1.cif").exists()
    assert (structure_dir / "mp-1.vasp").exists()
    assert exported.loc[0, "structure_json_path"].endswith("mp-1.json")
    assert exported.loc[0, "structure_cif_path"].endswith("mp-1.cif")
    assert exported.loc[0, "structure_poscar_path"].endswith("mp-1.vasp")

    result_rows = pd.read_csv(results_template, keep_default_na=False)
    assert result_rows.loc[0, "task_id"] == exported.loc[0, "task_id"]
    assert result_rows.loc[0, "status"] == "pending"
    assert result_rows.loc[0, "structure_sha256"] == exported.loc[0, "structure_sha256"]

    metadata = json.loads(method_template.read_text())
    assert metadata["schema_version"] == GAP_SCHEMA_VERSION
    assert metadata["method"] == "vasp-hse06-pbe54-nosoc-v1"
    assert metadata["calculator"] == ""


def test_export_gap_task_identity_is_deterministic(tmp_path):
    groups = [
        StructureGroup(
            entry_idx=[0],
            A_elements=[["Ca"]],
            compositions=["CaS"],
            group_size=1,
            X_element=["S"],
            mp_ids=["mp-1"],
            group_repr="descriptor",
        )
    ]
    groups_path = tmp_path / "groups.json"
    dataset_path = tmp_path / "dataset.df"
    dump_group_df(groups, groups_path)
    _dataset().to_pickle(dataset_path)

    first = export_gap_candidates(groups_path, dataset_path, tmp_path / "first.csv", method="hse06")
    second = export_gap_candidates(
        groups_path, dataset_path, tmp_path / "second.csv", method="hse06"
    )

    assert first.loc[0, "task_id"] == second.loc[0, "task_id"]
    assert first.loc[0, "structure_sha256"] == second.loc[0, "structure_sha256"]


def test_export_gap_candidates_applies_atom_count_gate(tmp_path):
    groups = [
        StructureGroup(
            entry_idx=[0, 1],
            A_elements=[["Ca"], ["Ca"]],
            compositions=["CaS", "CaSe"],
            group_size=2,
            X_element=["S", "Se"],
            mp_ids=["mp-1", "mp-2"],
            group_repr="descriptor",
        )
    ]
    groups_path = tmp_path / "groups.json"
    dataset_path = tmp_path / "dataset.df"
    dump_group_df(groups, groups_path)
    _dataset().to_pickle(dataset_path)

    exported = export_gap_candidates(
        groups_path,
        dataset_path,
        tmp_path / "gap_candidates.csv",
        max_natoms=1,
    )

    assert exported.empty


def test_export_gap_candidates_writes_the_structure_used_for_atom_count_gate(tmp_path):
    groups = [
        StructureGroup(
            entry_idx=[0],
            A_elements=[["Ca"]],
            compositions=["CaS"],
            group_size=1,
            X_element=["S"],
            mp_ids=["mp-1"],
            group_repr="descriptor",
        )
    ]
    groups_path = tmp_path / "groups.json"
    dataset_path = tmp_path / "dataset.df"
    structure_dir = tmp_path / "structures"
    df = _dataset()
    df["primitive_structure"] = None
    df.at["mp-1", "structure"] = _supercell_structure()
    df.at["mp-1", "primitive_structure"] = _structure()
    dump_group_df(groups, groups_path)
    df.to_pickle(dataset_path)

    exported = export_gap_candidates(
        groups_path,
        dataset_path,
        tmp_path / "gap_candidates.csv",
        structure_dir=structure_dir,
        max_natoms=2,
    )

    exported_structure = loadfn(exported.loc[0, "structure_path"])
    assert exported.loc[0, "natoms"] == 2
    assert len(exported_structure) == 2


def test_validate_gap_results_accepts_stable_schema(tmp_path):
    path = tmp_path / "gap_results.csv"
    pd.DataFrame(
        [
            {
                "material_id": "mp-1",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": 0.2,
                "is_direct": True,
                "transition": "G-G",
                "status": "success",
            }
        ]
    ).to_csv(path, index=False)

    results = validate_gap_results(path)

    assert list(results["material_id"]) == ["mp-1"]
    assert results.loc[0, "method"] == "hse06"
    assert results.loc[0, "band_gap"] == 0.2


def test_validate_gap_results_accepts_json_records(tmp_path):
    path = tmp_path / "gap_results.json"
    pd.DataFrame(
        [
            {
                "material_id": "mp-1",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": 0.2,
                "is_direct": True,
                "transition": "G-G",
                "status": "success",
            }
        ]
    ).to_json(path, orient="records")

    results = validate_gap_results(path)

    assert list(results["material_id"]) == ["mp-1"]


def test_validate_gap_results_rejects_missing_required_columns(tmp_path):
    path = tmp_path / "bad_gap_results.csv"
    pd.DataFrame([{"material_id": "mp-1", "band_gap": 0.2}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required gap-result columns"):
        validate_gap_results(path)


def test_validate_gap_results_allows_blank_band_gap_for_failed_rows(tmp_path):
    path = tmp_path / "gap_results.csv"
    pd.DataFrame(
        [
            {
                "material_id": "mp-1",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": "",
                "is_direct": "",
                "transition": "",
                "status": "failed",
            }
        ]
    ).to_csv(path, index=False)

    results = validate_gap_results(path)

    assert pd.isna(results.loc[0, "band_gap"])


def test_validate_gap_results_cross_checks_tasks_and_writes_audit_outputs(tmp_path):
    tasks_path = tmp_path / "gap_tasks.csv"
    results_path = tmp_path / "gap_results.csv"
    metadata_path = tmp_path / "method_metadata.json"
    normalized_path = tmp_path / "normalized.csv"
    rejected_path = tmp_path / "rejected.csv"
    report_path = tmp_path / "report.json"
    structure_hash = "a" * 64
    task_id = make_gap_task_id("mp-1", "hse06-v1", structure_hash)
    pd.DataFrame(
        [
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "task_id": task_id,
                "material_id": "mp-1",
                "formula": "CaS",
                "method": "hse06-v1",
                "structure_sha256": structure_hash,
            }
        ]
    ).to_csv(tasks_path, index=False)
    pd.DataFrame(
        [
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "task_id": task_id,
                "material_id": "mp-1",
                "formula": "CaS",
                "method": "hse06-v1",
                "band_gap": 0.2,
                "is_direct": "unknown",
                "transition": "",
                "status": "success",
                "structure_sha256": structure_hash,
                "settings_sha256": "",
            }
        ]
    ).to_csv(results_path, index=False)
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "method": "hse06-v1",
                "calculator": "vasp",
                "calculator_version": "6.3.2",
                "functional": "hse06",
                "soc": False,
            }
        )
    )

    normalized = validate_gap_results(
        results_path,
        tasks_path=tasks_path,
        method_metadata_path=metadata_path,
        output_path=normalized_path,
        rejected_path=rejected_path,
        report_path=report_path,
    )

    assert len(normalized) == 1
    assert pd.isna(normalized.loc[0, "is_direct"])
    assert normalized.loc[0, "settings_sha256"]
    assert normalized_path.exists()
    assert rejected_path.exists()
    assert pd.read_csv(rejected_path).empty
    report = json.loads(report_path.read_text())
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 0
    assert report["missing_task_ids"] == []
    assert report["unaccepted_task_ids"] == []


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ({"task_id": "gap-unknown"}, "unknown_task_id"),
        ({"structure_sha256": "b" * 64}, "structure_sha256_mismatch"),
        ({"structure_sha256": ""}, "missing_structure_sha256"),
        ({"band_gap": -0.1}, "invalid_band_gap"),
    ],
)
def test_validate_gap_results_rejects_invalid_task_rows(tmp_path, mutation, expected_error):
    tasks_path = tmp_path / "gap_tasks.csv"
    results_path = tmp_path / "gap_results.csv"
    rejected_path = tmp_path / "rejected.csv"
    structure_hash = "a" * 64
    task = {
        "schema_version": GAP_SCHEMA_VERSION,
        "task_id": make_gap_task_id("mp-1", "hse06", structure_hash),
        "material_id": "mp-1",
        "formula": "CaS",
        "method": "hse06",
        "structure_sha256": structure_hash,
    }
    result = {
        **task,
        "band_gap": 0.2,
        "is_direct": True,
        "transition": "G-G",
        "status": "success",
    }
    result.update(mutation)
    pd.DataFrame([task]).to_csv(tasks_path, index=False)
    pd.DataFrame([result]).to_csv(results_path, index=False)

    normalized = validate_gap_results(
        results_path,
        tasks_path=tasks_path,
        rejected_path=rejected_path,
    )

    assert normalized.empty
    rejected = pd.read_csv(rejected_path)
    assert expected_error in rejected.loc[0, "validation_errors"]
    assert normalized.attrs["validation_report"]["unaccepted_task_ids"] == [task["task_id"]]


def test_validate_gap_results_rejects_tampered_task_identity(tmp_path):
    tasks_path = tmp_path / "gap_tasks.csv"
    results_path = tmp_path / "gap_results.csv"
    structure_hash = "a" * 64
    task = {
        "schema_version": GAP_SCHEMA_VERSION,
        "task_id": make_gap_task_id("mp-1", "hse06", structure_hash),
        "material_id": "mp-2",
        "formula": "CaS",
        "method": "hse06",
        "structure_sha256": structure_hash,
    }
    result = {
        **task,
        "band_gap": 0.2,
        "is_direct": True,
        "transition": "G-G",
        "status": "success",
    }
    pd.DataFrame([task]).to_csv(tasks_path, index=False)
    pd.DataFrame([result]).to_csv(results_path, index=False)

    with pytest.raises(ValueError, match="task_identity_mismatch"):
        validate_gap_results(results_path, tasks_path=tasks_path)


def test_validate_gap_results_rejects_duplicate_task_rows(tmp_path):
    path = tmp_path / "gap_results.csv"
    row = {
        "schema_version": GAP_SCHEMA_VERSION,
        "task_id": "gap-0123456789abcdef01234567",
        "material_id": "mp-1",
        "formula": "CaS",
        "method": "hse06",
        "band_gap": 0.2,
        "is_direct": True,
        "transition": "G-G",
        "status": "success",
    }
    pd.DataFrame([row, row]).to_csv(path, index=False)

    normalized = validate_gap_results(path)

    assert normalized.empty
    assert normalized.attrs["validation_report"]["rejected_count"] == 2
    assert normalized.attrs["validation_report"]["error_counts"]["duplicate_result"] == 2
