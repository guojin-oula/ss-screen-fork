"""Tests for Stage 10 MP competing phases and same-MLIP convex hulls."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import pytest
from monty.serialization import dumpfn
from pymatgen.core import Lattice, Structure

from ssscreen.config import CompetingPhaseSettings
from ssscreen.stability.competing import (
    collect_convex_hulls,
    export_competing_phases,
    relax_competing_phases,
)
from ssscreen.stability.mlp import RelaxationOutcome


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _structure(species: list[str]) -> Structure:
    coordinates = [[index / len(species)] * 3 for index in range(len(species))]
    return Structure(Lattice.cubic(4.0), species, coordinates)


def _backend(model_sha256: str = "fixture-model", device: str = "cpu") -> dict:
    return {
        "name": "mace",
        "version": "0.3.14",
        "model_name": "fixture",
        "model_sha256": model_sha256,
        "device": device,
        "dtype": "float64",
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


def _relax_record(
    tmp_path: Path,
    structure_id: str,
    role: str,
    species: list[str],
    energy: float,
    *,
    backend: dict | None = None,
    usable: bool = True,
    **metadata,
) -> dict:
    structure_path = tmp_path / f"{structure_id}.json"
    dumpfn(_structure(species), structure_path)
    return {
        "schema_version": 1,
        "structure_id": structure_id,
        "structure_role": role,
        **metadata,
        "backend": backend or _backend(),
        "settings": _settings(),
        "output_structure": {"path": str(structure_path), "sha256": _sha256(structure_path)},
        "energy_total_eV": energy,
        "energy_per_atom_eV": energy / len(species),
        "status": "success" if usable else "not_converged",
        "converged": usable,
        "usable_for_thermodynamics": usable,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


class FakeMPEntry:
    def __init__(self, entry_id: str, species: list[str], e_hull: float = 0.0) -> None:
        self.entry_id = entry_id
        self.structure = _structure(species)
        self.composition = self.structure.composition
        self.data = {"energy_above_hull": e_hull}


class FakeMPRester:
    calls: list[dict] = []

    def __init__(self, **kwargs) -> None:
        assert kwargs == {"mute_progress_bars": True}
        assert os.environ["MP_API_KEY"] == "testing-secret"
        self.db_version = "fixture-db"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_entries_in_chemsys(self, elements, **kwargs):
        self.calls.append({"elements": elements, **kwargs})
        return [
            FakeMPEntry("mp-li", ["Li"]),
            FakeMPEntry("mp-o", ["O"]),
            FakeMPEntry("mp-lio", ["Li", "O"], 0.02),
        ]


class FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name

    def in_(self, values):
        return (self.name, "in", tuple(values))

    def __ge__(self, value):
        return (self.name, ">=", value)

    def __le__(self, value):
        return (self.name, "<=", value)

    def is_(self, value):
        return (self.name, "is", value)


class FakeMaterialSummary:
    chemsys = FakeColumn("chemsys")
    energy_above_hull = FakeColumn("energy_above_hull")
    deprecated = FakeColumn("deprecated")


class FakeOfflineClient:
    calls: list[dict] = []

    def __init__(self, database) -> None:
        self.database = database

    def query_all(self, *criteria, project=None):
        self.calls.append({"database": self.database, "criteria": criteria, "project": project})
        structures = {
            "mp-li": _structure(["Li"]),
            "mp-o": _structure(["O"]),
            "mp-lio": _structure(["Li", "O"]),
        }
        return [
            {
                "material_id": material_id,
                "structure": structure.as_dict(),
                "composition": structure.composition.as_dict(),
                "chemsys": structure.composition.chemical_system,
                "formula_pretty": structure.composition.reduced_formula,
                "nsites": len(structure),
                "energy_above_hull": 0.02 if material_id == "mp-lio" else 0.0,
            }
            for material_id, structure in structures.items()
        ]


def test_export_competing_phases_prompts_boundary_without_persisting_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MP_API_KEY", raising=False)
    candidate = _relax_record(
        tmp_path,
        "sqs-lio",
        "sqs",
        ["Li", "O"],
        -3.2,
        pair_index=0,
    )
    candidate_results = tmp_path / "candidate.jsonl"
    _write_jsonl(candidate_results, [candidate])
    manifest = tmp_path / "competing.jsonl"
    report_path = tmp_path / "export.json"
    FakeMPRester.calls.clear()

    records, report = export_competing_phases(
        relax_results_path=candidate_results,
        output_dir=tmp_path / "inputs",
        manifest_path=manifest,
        report_path=report_path,
        api_key="testing-secret",
        settings=CompetingPhaseSettings(max_mp_energy_above_hull=0.05),
        mpr_factory=FakeMPRester,
    )

    assert os.environ.get("MP_API_KEY") is None
    assert len(records) == 3
    assert {record["status"] for record in records} == {"written"}
    assert all(Path(record["structure_path"]).is_file() for record in records)
    assert report["mp_database_version"] == "fixture-db"
    assert report["api_key_persisted"] is False
    assert "testing-secret" not in manifest.read_text()
    assert "testing-secret" not in report_path.read_text()
    assert FakeMPRester.calls[0]["elements"] == ["Li", "O"]
    assert FakeMPRester.calls[0]["additional_criteria"]["energy_above_hull"] == (
        0.0,
        0.05,
    )


def test_export_competing_phases_reads_offline_snapshot_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MP_API_KEY", raising=False)
    candidate = _relax_record(
        tmp_path,
        "sqs-lio",
        "sqs",
        ["Li", "O"],
        -3.2,
    )
    candidate_results = tmp_path / "candidate.jsonl"
    _write_jsonl(candidate_results, [candidate])
    database = tmp_path / "default.db"
    database.write_bytes(b"offline-snapshot")
    FakeOfflineClient.calls.clear()

    records, report = export_competing_phases(
        relax_results_path=candidate_results,
        output_dir=tmp_path / "inputs",
        manifest_path=tmp_path / "manifest.jsonl",
        report_path=tmp_path / "report.json",
        mp_backend="offline",
        offline_db=database,
        settings=CompetingPhaseSettings(max_mp_energy_above_hull=0.05),
        offline_client_factory=FakeOfflineClient,
        material_summary_cls=FakeMaterialSummary,
    )

    assert os.environ.get("MP_API_KEY") is None
    assert {record["mp_entry_id"] for record in records} == {"mp-li", "mp-o", "mp-lio"}
    assert {record["mp_source_backend"] for record in records} == {"offline"}
    assert {record["mp_thermo_type"] for record in records} == {None}
    assert not any(record["mp_thermo_type_filter_applied"] for record in records)
    assert report["mp_source_scope"] == "offline_summary_snapshot"
    assert report["mp_database_sha256"] == _sha256(database)
    assert report["mp_source_warning"]
    call = FakeOfflineClient.calls[0]
    assert call["database"] == database.resolve()
    assert call["criteria"][0] == ("chemsys", "in", ("Li", "Li-O", "O"))
    assert call["criteria"][1:] == (
        ("energy_above_hull", ">=", 0.0),
        ("energy_above_hull", "<=", 0.05),
        ("deprecated", "is", False),
    )
    assert "json_data" not in call["project"]


def test_export_competing_phases_records_query_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("MP_API_KEY", raising=False)
    candidate = _relax_record(
        tmp_path,
        "sqs-lio",
        "sqs",
        ["Li", "O"],
        -3.2,
    )
    candidate_results = tmp_path / "candidate.jsonl"
    _write_jsonl(candidate_results, [candidate])

    class FailingMPRester(FakeMPRester):
        def get_entries_in_chemsys(self, elements, **kwargs):
            raise TimeoutError("fixture timeout")

    records, report = export_competing_phases(
        relax_results_path=candidate_results,
        output_dir=tmp_path / "inputs",
        manifest_path=tmp_path / "manifest.jsonl",
        report_path=tmp_path / "report.json",
        api_key="testing-secret",
        mpr_factory=FailingMPRester,
    )

    assert records[0]["status"] == "failed"
    assert records[0]["structure_id"] == "query-failure-Li-O"
    assert "fixture timeout" in records[0]["error"]
    assert report["query_failure_count"] == 1


class FakeRelaxationBackend:
    @property
    def metadata(self):
        return _backend()

    def relax(self, structure, *, fmax, max_steps, relax_cell):
        return RelaxationOutcome(
            structure=structure.copy(),
            initial_energy_total_ev=-1.0 * len(structure),
            energy_total_ev=-1.1 * len(structure),
            forces_ev_per_angstrom=[[0.0, 0.0, 0.0] for _ in structure],
            stress_ev_per_angstrom3=[[0.0, 0.0, 0.0] for _ in range(3)],
            steps=2,
            converged=True,
        )


def test_relax_competing_phases_preserves_mp_provenance(tmp_path):
    structure_path = tmp_path / "phase.json"
    dumpfn(_structure(["Li"]), structure_path)
    manifest = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest,
        [
            {
                "status": "written",
                "structure_role": "competing_phase",
                "structure_id": "competing-mp-li",
                "mp_entry_id": "mp-li",
                "reduced_formula": "Li",
                "chemical_system": "Li",
                "parent_chemical_systems": ["Li-O"],
                "mp_database_version": "fixture-db",
                "structure_path": str(structure_path),
                "structure_sha256": _sha256(structure_path),
            }
        ],
    )

    records = relax_competing_phases(
        manifest_path=manifest,
        output_dir=tmp_path / "relax",
        results_path=tmp_path / "results.jsonl",
        backend=FakeRelaxationBackend(),
    )

    assert records[0]["structure_role"] == "competing_phase"
    assert records[0]["mp_entry_id"] == "mp-li"
    assert records[0]["parent_chemical_systems"] == ["Li-O"]
    assert records[0]["status"] == "success"


def _hull_inputs(tmp_path: Path, *, incompatible: bool = False, unusable: bool = False):
    candidate = _relax_record(
        tmp_path,
        "sqs-lio",
        "sqs",
        ["Li", "O"],
        -3.2,
        pair_index=0,
    )
    candidate_path = tmp_path / "candidates.jsonl"
    _write_jsonl(candidate_path, [candidate])

    phases = [
        ("competing-li", ["Li"], -0.8),
        ("competing-o", ["O"], -1.8),
        ("competing-lio", ["Li", "O"], -3.0),
    ]
    manifest_records = []
    result_records = []
    for index, (phase_id, species, energy) in enumerate(phases):
        manifest_records.append(
            {
                "status": "written",
                "structure_role": "competing_phase",
                "structure_id": phase_id,
                "parent_chemical_systems": ["Li-O"],
                "mp_source_backend": "offline",
                "mp_source_scope": "offline_summary_snapshot",
                "mp_database_version": "offline-fixture",
                "mp_database_sha256": "a" * 64,
                "mp_source_warning": "complete only relative to offline snapshot",
            }
        )
        phase_backend = (
            _backend(model_sha256="other-model") if incompatible and index == 2 else None
        )
        result_records.append(
            _relax_record(
                tmp_path,
                phase_id,
                "competing_phase",
                species,
                energy,
                backend=phase_backend,
                usable=not (unusable and index == 2),
                parent_chemical_systems=["Li-O"],
            )
        )
    manifest_path = tmp_path / "manifest.jsonl"
    result_path = tmp_path / "competing-results.jsonl"
    _write_jsonl(manifest_path, manifest_records)
    _write_jsonl(result_path, result_records)
    return candidate_path, manifest_path, result_path


def test_collect_convex_hull_reports_candidate_margin_and_entries(tmp_path):
    candidates, manifest, competing = _hull_inputs(tmp_path)

    frame, entries, summary = collect_convex_hulls(
        candidate_relax_results_path=candidates,
        competing_manifest_path=manifest,
        competing_relax_results_path=competing,
        output_path=tmp_path / "phase_stability.csv",
        entries_output_path=tmp_path / "hull_entries.csv",
        summary_path=tmp_path / "summary.json",
    )

    row = frame.iloc[0]
    assert row["status"] == "success"
    assert row["competing_set_complete"]
    assert row["energy_relative_to_competing_hull_eV_per_atom"] == pytest.approx(-0.1)
    assert row["energy_above_hull_eV_per_atom"] == 0.0
    assert row["candidate_lowers_hull"]
    assert row["mp_source_backend"] == "offline"
    assert row["mp_source_scope"] == "offline_summary_snapshot"
    assert row["mp_database_sha256"] == "a" * 64
    assert "complete only relative" in row["warnings"]
    assert row["hull_signal"] == "stable"
    assert json.loads(row["decomposition"])["competing-lio"]["fraction"] == 1.0
    assert set(entries["phase_structure_id"]) == {
        "competing-li",
        "competing-o",
        "competing-lio",
        "sqs-lio",
    }
    assert summary["success_count"] == 1
    assert summary["mp_source_backends"] == ["offline"]


def test_collect_convex_hull_rejects_mixed_mp_sources_even_when_incomplete_allowed(tmp_path):
    candidates, manifest, competing = _hull_inputs(tmp_path)
    manifest_records = [json.loads(line) for line in manifest.read_text().splitlines()]
    manifest_records[-1]["mp_source_backend"] = "api"
    _write_jsonl(manifest, manifest_records)

    frame, entries, summary = collect_convex_hulls(
        candidate_relax_results_path=candidates,
        competing_manifest_path=manifest,
        competing_relax_results_path=competing,
        output_path=tmp_path / "phase_stability.csv",
        entries_output_path=tmp_path / "hull_entries.csv",
        summary_path=tmp_path / "summary.json",
        allow_incomplete=True,
    )

    assert frame.iloc[0]["status"] == "incompatible_competing_sources"
    assert not frame.iloc[0]["usable_for_screening"]
    assert entries.empty
    assert summary["failed_count"] == 1


@pytest.mark.parametrize("mode", ["incompatible", "unusable"])
def test_collect_convex_hull_rejects_incomplete_competing_set(tmp_path, mode):
    candidates, manifest, competing = _hull_inputs(
        tmp_path,
        incompatible=mode == "incompatible",
        unusable=mode == "unusable",
    )

    frame, entries, summary = collect_convex_hulls(
        candidate_relax_results_path=candidates,
        competing_manifest_path=manifest,
        competing_relax_results_path=competing,
        output_path=tmp_path / "phase_stability.csv",
        entries_output_path=tmp_path / "hull_entries.csv",
        summary_path=tmp_path / "summary.json",
    )

    assert frame.iloc[0]["status"] == "incomplete_competing_set"
    assert not frame.iloc[0]["usable_for_screening"]
    assert pd.isna(frame.iloc[0]["energy_above_hull_eV_per_atom"])
    assert entries.empty
    assert summary["failed_count"] == 1
