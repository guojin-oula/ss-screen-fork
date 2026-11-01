"""Tests for Stage 8 mixing-enthalpy calculation and provenance checks."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from ssscreen.stability.thermodynamics import calculate_mixing_enthalpies


def _backend(model_sha256: str = "model-a", device: str = "cuda:0") -> dict:
    return {
        "name": "mace",
        "version": "0.3.14",
        "model_name": "MACE-MPA-0-medium",
        "model_sha256": model_sha256,
        "device": device,
        "dtype": "float32",
    }


def _settings() -> dict:
    return {
        "optimizer": "FIRE",
        "cell_mode": "full",
        "fmax_ev_per_angstrom": 0.03,
        "max_steps": 500,
        "quality_control": {
            "min_volume_ratio": 0.5,
            "max_volume_ratio": 2.0,
            "min_distance_angstrom": 0.5,
        },
    }


def _record(
    structure_id: str,
    role: str,
    energy: float,
    *,
    backend: dict | None = None,
    usable: bool = True,
    **metadata,
) -> dict:
    return {
        "schema_version": 1,
        "structure_id": structure_id,
        "structure_role": role,
        **metadata,
        "backend": backend or _backend(),
        "settings": _settings(),
        "energy_per_atom_eV": energy,
        "status": "success" if usable else "not_converged",
        "converged": usable,
        "usable_for_thermodynamics": usable,
    }


def _write_inputs(tmp_path, records):
    pairs = tmp_path / "pairs.csv"
    pd.DataFrame(
        [
            {
                "source_group_index": 7,
                "mp_id_a": "mp-a",
                "mp_id_b": "mp-b",
                "comp_a": "CaS",
                "comp_b": "CaSe",
            }
        ]
    ).to_csv(pairs, index=False)
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("".join(json.dumps(record) + "\n" for record in records))
    return pairs, relax_results


def _base_records(**sqs_metadata):
    return [
        _record("endmember-a", "endmember", -2.0, material_id="mp-a", composition="CaS"),
        _record(
            "endmember-b",
            "endmember",
            -1.0,
            backend=_backend(device="cuda:1"),
            material_id="mp-b",
            composition="CaSe",
        ),
        _record(
            "sqs-0.5",
            "sqs",
            -1.6,
            pair_index=0,
            mp_id_a="mp-a",
            mp_id_b="mp-b",
            comp_a="CaS",
            comp_b="CaSe",
            target_fraction_b=0.5,
            actual_fraction_b=0.5,
            **sqs_metadata,
        ),
    ]


def test_calculate_mixing_enthalpy_writes_energy_profile_and_summary(tmp_path):
    pairs, relax_results = _write_inputs(tmp_path, _base_records())
    output = tmp_path / "mixing.csv"
    summary_path = tmp_path / "summary.json"

    frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs,
        relax_results_path=relax_results,
        output_path=output,
        summary_path=summary_path,
    )

    row = frame.iloc[0]
    assert row["status"] == "success"
    assert row["actual_fraction_b"] == 0.5
    assert row["fraction_basis"] == "actual"
    assert row["reference_energy_per_atom_eV"] == pytest.approx(-1.5)
    assert row["mixing_enthalpy_eV_per_atom"] == pytest.approx(-0.1)
    assert row["mixing_enthalpy_meV_per_atom"] == pytest.approx(-100.0)
    assert row["mixing_signal"] == "exothermic"
    assert row["endmember_a_device"] == "cuda:0"
    assert row["endmember_b_device"] == "cuda:1"
    assert row["usable_for_screening"]
    assert output.is_file()
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 0
    assert json.loads(summary_path.read_text()) == summary


def test_calculate_mixing_enthalpy_prefers_site_counts_and_warns_on_rounding(tmp_path):
    records = _base_records()
    sqs = records[-1]
    sqs.pop("actual_fraction_b")
    sqs["target_fraction_b"] = 0.3
    sqs["replaced_sites"] = 1
    sqs["available_substitution_sites"] = 4
    pairs, relax_results = _write_inputs(tmp_path, records)

    frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs,
        relax_results_path=relax_results,
        output_path=tmp_path / "mixing.csv",
        summary_path=tmp_path / "summary.json",
    )

    row = frame.iloc[0]
    assert row["actual_fraction_b"] == 0.25
    assert row["fraction_basis"] == "site_counts"
    assert "differs from target_fraction_b" in row["warnings"]
    assert summary["target_fraction_fallback_count"] == 0


def test_calculate_mixing_enthalpy_marks_target_fraction_fallback(tmp_path):
    records = _base_records()
    records[-1].pop("actual_fraction_b")
    pairs, relax_results = _write_inputs(tmp_path, records)

    frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs,
        relax_results_path=relax_results,
        output_path=tmp_path / "mixing.csv",
        summary_path=tmp_path / "summary.json",
    )

    assert frame.iloc[0]["status"] == "success"
    assert frame.iloc[0]["fraction_basis"] == "target_fallback"
    assert "actual fraction unavailable" in frame.iloc[0]["warnings"]
    assert summary["target_fraction_fallback_count"] == 1


def test_calculate_mixing_enthalpy_rejects_incompatible_model(tmp_path):
    records = _base_records()
    records[1]["backend"] = _backend(model_sha256="model-b")
    pairs, relax_results = _write_inputs(tmp_path, records)

    frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs,
        relax_results_path=relax_results,
        output_path=tmp_path / "mixing.csv",
        summary_path=tmp_path / "summary.json",
    )

    row = frame.iloc[0]
    assert row["status"] == "incompatible_provenance"
    assert pd.isna(row["mixing_enthalpy_eV_per_atom"])
    assert not row["usable_for_screening"]
    assert summary["status_counts"] == {"incompatible_provenance": 1}


def test_calculate_mixing_enthalpy_rejects_incomplete_settings(tmp_path):
    records = _base_records()
    records[-1]["settings"] = {}
    pairs, relax_results = _write_inputs(tmp_path, records)

    frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs,
        relax_results_path=relax_results,
        output_path=tmp_path / "mixing.csv",
        summary_path=tmp_path / "summary.json",
    )

    assert frame.iloc[0]["status"] == "invalid_provenance"
    assert summary["status_counts"] == {"invalid_provenance": 1}


def test_calculate_mixing_enthalpy_preserves_unusable_endpoint_failure(tmp_path):
    records = _base_records()
    records[0]["status"] = "not_converged"
    records[0]["converged"] = False
    records[0]["usable_for_thermodynamics"] = False
    pairs, relax_results = _write_inputs(tmp_path, records)

    frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs,
        relax_results_path=relax_results,
        output_path=tmp_path / "mixing.csv",
        summary_path=tmp_path / "summary.json",
    )

    assert frame.iloc[0]["status"] == "unusable_endmember"
    assert summary["failed_count"] == 1
    assert summary["missing_pair_indices"] == [0]
