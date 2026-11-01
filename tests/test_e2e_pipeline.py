"""Lightweight Stage 1--11 artifact-chain regression test."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from click.testing import CliRunner
from pymatgen.core import Composition, Lattice, Structure

from ssscreen.cli.app import cli

FIXTURES = Path(__file__).parent / "data" / "e2e"
MODEL_SHA256 = "f" * 64
GAP_METHOD = "fixture-hse-v1"


def _invoke(runner: CliRunner, arguments: list[str]) -> None:
    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output


def _write_normalized_dataset(path: Path) -> pd.DataFrame:
    rows = []
    for source in pd.read_csv(FIXTURES / "materials.csv").to_dict(orient="records"):
        composition = Composition(source["formula"])
        species = [str(element) for element in composition.elements]
        structure = Structure(
            Lattice.cubic(float(source["lattice_a"])),
            species,
            [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        )
        rows.append(
            {
                "material_id": source["material_id"],
                "formula": source["formula"],
                "composition": composition,
                "reduced_composition": composition.reduced_composition,
                "nelems": len(composition),
                "band_gap": float(source["band_gap"]),
                "e_hull": float(source["e_hull"]),
                "structure": structure,
                "source": source["source"],
            }
        )
    frame = pd.DataFrame.from_records(rows).set_index("material_id")
    frame.to_pickle(path)
    return frame


def _complete_gap_results(template_path: Path, output_path: Path) -> None:
    results = pd.read_csv(template_path, keep_default_na=False)
    evidence = pd.read_csv(FIXTURES / "gap_evidence.csv").set_index("material_id")
    for index, row in results.iterrows():
        values = evidence.loc[row["material_id"]]
        results.loc[index, "band_gap"] = float(values["band_gap"])
        results.loc[index, "is_direct"] = str(values["is_direct"]).lower() == "true"
        results.loc[index, "transition"] = values["transition"]
        results.loc[index, "status"] = "success"
        results.loc[index, "backend"] = "fixture"
        results.loc[index, "backend_version"] = "1"
        results.loc[index, "completed_at"] = "2026-01-01T00:00:00Z"
    results.to_csv(output_path, index=False)


def _backend() -> dict:
    return {
        "name": "fixture-mlip",
        "version": "1",
        "model_name": "deterministic-fixture",
        "model_sha256": MODEL_SHA256,
        "device": "cpu",
        "dtype": "float64",
    }


def _settings() -> dict:
    return {
        "optimizer": "fixture",
        "cell_mode": "full",
        "fmax_ev_per_angstrom": 0.03,
        "max_steps": 1,
        "quality_control": {
            "min_volume_ratio": 0.5,
            "max_volume_ratio": 2.0,
            "min_distance_angstrom": 0.5,
        },
    }


def _relax_record(structure_id: str, role: str, energy: float, **metadata) -> dict:
    return {
        "schema_version": 1,
        "structure_id": structure_id,
        "structure_role": role,
        **metadata,
        "backend": _backend(),
        "settings": _settings(),
        "energy_per_atom_eV": energy,
        "status": "success",
        "converged": True,
        "usable_for_thermodynamics": True,
    }


def _write_fixture_relaxations(
    manifest_path: Path,
    dataset: pd.DataFrame,
    output_path: Path,
) -> None:
    endpoint_energies = {
        "mp-cas": -2.0,
        "mp-case": -1.8,
        "mp-cate": -1.6,
    }
    records = [
        _relax_record(
            f"fixture-endmember-{material_id}",
            "endmember",
            energy,
            material_id=material_id,
            composition=dataset.loc[material_id, "formula"],
        )
        for material_id, energy in endpoint_energies.items()
    ]

    manifest = [json.loads(line) for line in manifest_path.read_text().splitlines()]
    assert len(manifest) == 2
    assert {record["status"] for record in manifest} == {"written"}
    for source in manifest:
        pair_index = int(source["pair_index"])
        fraction = float(source["actual_fraction_b"])
        reference = (1.0 - fraction) * endpoint_energies[source["mp_id_a"]] + fraction * (
            endpoint_energies[source["mp_id_b"]]
        )
        penalty = (
            0.01
            if {source["mp_id_a"], source["mp_id_b"]}
            == {
                "mp-cas",
                "mp-case",
            }
            else 0.08
        )
        records.append(
            _relax_record(
                f"fixture-sqs-{pair_index:05d}",
                "sqs",
                reference + penalty,
                pair_index=pair_index,
                source_group_index=source.get("source_group_index"),
                mp_id_a=source["mp_id_a"],
                mp_id_b=source["mp_id_b"],
                comp_a=source["comp_a"],
                comp_b=source["comp_b"],
                target_fraction_b=float(source["target_fraction_b"]),
                actual_fraction_b=fraction,
            )
        )
    output_path.write_text("".join(json.dumps(record) + "\n" for record in records))


def _write_downstream_summaries(mixing_path: Path, root: Path) -> tuple[Path, Path]:
    mixing = pd.read_csv(mixing_path)
    phonon_rows = []
    phase_rows = []
    for row in mixing.to_dict(orient="records"):
        is_promising_pair = {row["mp_id_a"], row["mp_id_b"]} == {"mp-cas", "mp-case"}
        phonon_rows.append(
            {
                "pair_index": int(row["pair_index"]),
                "structure_id": row["sqs_structure_id"],
                "structure_role": "sqs",
                "target_fraction_b": row["target_fraction_b"],
                "actual_fraction_b": row["actual_fraction_b"],
                "minimum_mesh_frequency_THz": -1e-8 if is_promising_pair else -2.7,
                "nac_applied": False,
                "model_sha256": MODEL_SHA256,
                "status": "success",
                "dynamical_status": "stable" if is_promising_pair else "unstable",
                "warnings": "fixture evidence; NAC not applied",
            }
        )
        phase_rows.append(
            {
                "pair_index": int(row["pair_index"]),
                "structure_id": row["sqs_structure_id"],
                "energy_above_hull_eV_per_atom": 0.01 if is_promising_pair else 0.08,
                "hull_signal": "metastable_within_cutoff",
                "competing_set_complete": True,
                "mp_source_backend": "fixture",
                "mp_source_scope": "ci_fixture",
                "model_sha256": MODEL_SHA256,
                "status": "success",
                "usable_for_screening": True,
                "warnings": "fixture evidence",
            }
        )
    phonons = root / "phonon_summary.csv"
    phases = root / "phase_stability.csv"
    pd.DataFrame.from_records(phonon_rows).to_csv(phonons, index=False)
    pd.DataFrame.from_records(phase_rows).to_csv(phases, index=False)
    return phonons, phases


def _run_pipeline(root: Path) -> dict[str, Path]:
    root.mkdir()
    runner = CliRunner()
    dataset_path = root / "stage1_materials.df"
    dataset = _write_normalized_dataset(dataset_path)

    candidates = root / "composition_candidates.csv"
    _invoke(
        runner,
        [
            "composition-screen",
            "--df",
            str(dataset_path),
            "--max-e-hull",
            "0.01",
            "--output",
            str(candidates),
            "--summary",
            str(root / "composition_summary.json"),
        ],
    )

    groups = root / "groups.json"
    _invoke(
        runner,
        [
            "structure-match",
            "--candidates",
            str(candidates),
            "--condensed-dir",
            str(FIXTURES / "condensed"),
            "--output",
            str(groups),
            "--summary",
            str(root / "structure_summary.json"),
        ],
    )

    gap_tasks = root / "gap_tasks.csv"
    gap_template = root / "gap_results_template.csv"
    _invoke(
        runner,
        [
            "gap-export",
            "--groups",
            str(groups),
            "--dataset",
            str(dataset_path),
            "--method",
            GAP_METHOD,
            "--structure-dir",
            str(root / "gap_structures"),
            "--structure-format",
            "json",
            "--results-template",
            str(gap_template),
            "--output",
            str(gap_tasks),
        ],
    )

    raw_gaps = root / "gap_results.returned.csv"
    normalized_gaps = root / "gap_results.normalized.csv"
    _complete_gap_results(gap_template, raw_gaps)
    _invoke(
        runner,
        [
            "gap-validate",
            "--gaps",
            str(raw_gaps),
            "--tasks",
            str(gap_tasks),
            "--output",
            str(normalized_gaps),
            "--rejected",
            str(root / "gap_results.rejected.csv"),
            "--report",
            str(root / "gap_validation.json"),
        ],
    )

    pairs = root / "final_pairs.csv"
    _invoke(
        runner,
        [
            "pair",
            "--groups",
            str(groups),
            "--gap-results",
            str(normalized_gaps),
            "--method",
            GAP_METHOD,
            "--summary",
            str(root / "pair_summary.json"),
            "--output",
            str(pairs),
        ],
    )

    sqs_manifest = root / "sqs_manifest.jsonl"
    _invoke(
        runner,
        [
            "stability",
            "sqs-generate",
            "--pairs",
            str(pairs),
            "--dataset",
            str(dataset_path),
            "--supercell",
            "2,1,1",
            "--backend",
            "random",
            "--seed",
            "7",
            "--output-dir",
            str(root / "sqs"),
            "--manifest",
            str(sqs_manifest),
        ],
    )

    relax_results = root / "relaxation_results.fixture.jsonl"
    _write_fixture_relaxations(sqs_manifest, dataset, relax_results)
    mixing = root / "mixing_enthalpy.csv"
    _invoke(
        runner,
        [
            "stability",
            "mixing-enthalpy",
            "--pairs",
            str(pairs),
            "--relax-results",
            str(relax_results),
            "--output",
            str(mixing),
            "--summary",
            str(root / "mixing_summary.json"),
        ],
    )
    phonons, phases = _write_downstream_summaries(mixing, root)

    recommendations = root / "recommendations.csv"
    report = root / "recommendation_report.md"
    summary = root / "recommendation_summary.json"
    _invoke(
        runner,
        [
            "recommend",
            "--pairs",
            str(pairs),
            "--gap-results",
            str(normalized_gaps),
            "--mixing-enthalpy",
            str(mixing),
            "--phonons",
            str(phonons),
            "--phase-stability",
            str(phases),
            "--output",
            str(recommendations),
            "--report",
            str(report),
            "--summary",
            str(summary),
        ],
    )
    return {
        "candidates": candidates,
        "groups": groups,
        "gap_tasks": gap_tasks,
        "normalized_gaps": normalized_gaps,
        "pairs": pairs,
        "sqs_manifest": sqs_manifest,
        "mixing": mixing,
        "phonons": phonons,
        "phases": phases,
        "recommendations": recommendations,
        "report": report,
        "summary": summary,
    }


def test_stage1_to_stage11_artifact_chain_is_reproducible(tmp_path):
    first = _run_pipeline(tmp_path / "first")
    second = _run_pipeline(tmp_path / "second")

    assert all(path.is_file() for path in first.values())
    assert len(pd.read_csv(first["candidates"])) == 3
    assert len(json.loads(first["groups"].read_text())) == 1
    assert len(pd.read_csv(first["gap_tasks"])) == 3
    assert len(pd.read_csv(first["normalized_gaps"])) == 3
    assert len(pd.read_csv(first["pairs"])) == 2
    assert len(first["sqs_manifest"].read_text().splitlines()) == 2
    assert set(pd.read_csv(first["mixing"])["status"]) == {"success"}

    columns = ["mp_id_a", "mp_id_b", "classification", "evidence_level"]
    expected = pd.read_csv(FIXTURES / "expected_recommendations.csv")
    actual = pd.read_csv(first["recommendations"])[columns]
    repeated = pd.read_csv(second["recommendations"])[columns]
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
    pd.testing.assert_frame_equal(repeated, expected, check_dtype=False)

    recommendations = pd.read_csv(first["recommendations"])
    assert list(recommendations["rank"]) == [1, 2]
    assert recommendations["recommendation_id"].is_unique
    assert set(recommendations["model_compatibility_status"]) == {"compatible"}
    assert all(
        json.loads(value) == ["defects:not_requested"] for value in recommendations["missing_data"]
    )
    assert "phonon:unstable" in json.loads(recommendations.iloc[1]["risks"])
    assert "mixing:above_low_priority_threshold" in json.loads(recommendations.iloc[1]["risks"])
    assert "Decision-support output only" in first["report"].read_text()
    summary = json.loads(first["summary"].read_text())
    assert summary["classification_counts"] == {"low-priority": 1, "promising": 1}
