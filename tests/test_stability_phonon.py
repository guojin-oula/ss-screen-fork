"""Tests for finite-displacement phonons driven by MLIP force records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from monty.serialization import dumpfn
from pymatgen.core import Lattice, Structure

pytest.importorskip("phonopy")

from ssscreen.stability.mlp import SinglePointOutcome
from ssscreen.stability.phonon import (
    _classify_frequencies,
    choose_supercell,
    collect_phonon_results,
    evaluate_phonon_forces,
    export_phonon_tasks,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relax_results(tmp_path: Path, *, max_force: float = 0.001) -> Path:
    structure_path = tmp_path / "relaxed.json"
    structure = Structure(Lattice.cubic(4.0), ["Al"], [[0, 0, 0]])
    dumpfn(structure, structure_path)
    record = {
        "schema_version": 1,
        "structure_id": "sqs-al",
        "structure_role": "sqs",
        "pair_index": 2,
        "target_fraction_b": 0.5,
        "actual_fraction_b": 0.5,
        "backend": {
            "name": "mace",
            "version": "0.3.14",
            "model_name": "fixture",
            "model_sha256": "fixture-model",
            "device": "cpu",
            "dtype": "float64",
        },
        "output_structure": {"path": str(structure_path), "sha256": _sha256(structure_path)},
        "max_force_eV_per_angstrom": max_force,
        "status": "success",
        "usable_for_thermodynamics": True,
    }
    results = tmp_path / "relaxation_results.jsonl"
    results.write_text(json.dumps(record) + "\n")
    return results


class HarmonicForceBackend:
    """Translation-invariant quadratic force fixture for displaced supercells."""

    def __init__(self, *, model_sha256: str = "fixture-model") -> None:
        self.model_sha256 = model_sha256
        self.reference: np.ndarray | None = None
        self.calls = 0

    @property
    def metadata(self):
        return {
            "name": "mace",
            "version": "0.3.14",
            "model_name": "fixture",
            "model_sha256": self.model_sha256,
            "device": "cpu",
            "dtype": "float64",
        }

    def evaluate(self, structure):
        self.calls += 1
        coordinates = np.asarray(structure.cart_coords, dtype=float)
        if self.reference is None:
            self.reference = coordinates.copy()
        displacement = coordinates - self.reference
        displacement -= np.mean(displacement, axis=0, keepdims=True)
        forces = -10.0 * displacement
        energy = 5.0 * float(np.sum(displacement**2))
        return SinglePointOutcome(
            energy_total_ev=energy,
            forces_ev_per_angstrom=forces.tolist(),
            stress_ev_per_angstrom3=np.zeros((3, 3)).tolist(),
        )


def test_choose_supercell_targets_minimum_length_and_atom_cap():
    structure = Structure(
        Lattice.orthorhombic(4.0, 6.0, 12.0),
        ["Al"],
        [[0, 0, 0]],
    )

    assert choose_supercell(
        structure,
        explicit=None,
        min_length=10.0,
        max_atoms=20,
    ) == (3, 2, 1)
    with pytest.raises(ValueError, match="above configured maximum"):
        choose_supercell(
            structure,
            explicit=(3, 3, 3),
            min_length=10.0,
            max_atoms=20,
        )


def test_export_force_collect_pipeline_writes_spectrum_and_resumes(tmp_path):
    manifest = tmp_path / "phonon_jobs.jsonl"
    export_records = export_phonon_tasks(
        relax_results_path=_relax_results(tmp_path),
        output_dir=tmp_path / "inputs",
        manifest_path=manifest,
        supercell=(2, 2, 2),
        max_supercell_atoms=20,
    )

    assert export_records[0]["task_role"] == "reference"
    assert export_records[0]["supercell_atom_count"] == 8
    assert export_records[0]["displacement_count"] >= 1
    assert len(export_records) == export_records[0]["displacement_count"] + 1
    assert Path(export_records[0]["phonopy_yaml_path"]).is_file()

    backend = HarmonicForceBackend()
    force_results = tmp_path / "phonon_force_results.jsonl"
    force_records = evaluate_phonon_forces(
        manifest_path=manifest,
        output_dir=tmp_path / "forces",
        results_path=force_results,
        backend=backend,
    )

    assert len(force_records) == len(export_records)
    assert {record["status"] for record in force_records} == {"success"}
    assert all("energy_total_eV" in record for record in force_records)
    call_count = backend.calls
    resumed = evaluate_phonon_forces(
        manifest_path=manifest,
        output_dir=tmp_path / "forces",
        results_path=force_results,
        backend=backend,
    )
    assert backend.calls == call_count
    assert resumed == force_records

    frame, report = collect_phonon_results(
        manifest_path=manifest,
        force_results_path=force_results,
        output_dir=tmp_path / "results",
        summary_path=tmp_path / "phonon_summary.csv",
        report_path=tmp_path / "phonon_summary.json",
        mesh=(4, 4, 4),
        band_points=5,
        imaginary_tolerance=0.1,
    )

    row = frame.iloc[0]
    assert row["status"] == "success"
    assert row["force_coverage"] == 1.0
    assert row["model_sha256"] == "fixture-model"
    result_dir = tmp_path / "results" / row["phonon_id"]
    assert (result_dir / "force_constants.hdf5").is_file()
    assert (result_dir / "mesh.npz").is_file()
    assert (result_dir / "phonon_band.csv").is_file()
    assert (result_dir / "phonon_band_dos.png").is_file()
    assert report["structure_count"] == 1


def test_export_marks_loose_relaxation_as_skipped(tmp_path):
    manifest = tmp_path / "phonon_jobs.jsonl"

    records = export_phonon_tasks(
        relax_results_path=_relax_results(tmp_path, max_force=0.03),
        output_dir=tmp_path / "inputs",
        manifest_path=manifest,
        supercell=(1, 1, 1),
        max_input_force=0.01,
    )

    assert records[0]["status"] == "skipped"
    assert "exceeds phonon limit" in records[0]["error"]


def test_force_evaluation_preserves_model_mismatch_failure(tmp_path):
    manifest = tmp_path / "phonon_jobs.jsonl"
    export_phonon_tasks(
        relax_results_path=_relax_results(tmp_path),
        output_dir=tmp_path / "inputs",
        manifest_path=manifest,
        supercell=(1, 1, 1),
    )

    records = evaluate_phonon_forces(
        manifest_path=manifest,
        output_dir=tmp_path / "forces",
        results_path=tmp_path / "forces.jsonl",
        backend=HarmonicForceBackend(model_sha256="different-model"),
    )

    assert {record["status"] for record in records} == {"failed"}
    assert all("does not match" in record["error"] for record in records)


def test_frequency_classification_uses_configured_imaginary_tolerance():
    stable = _classify_frequencies(np.array([[-0.02, 0.0, 1.0]]), 0.1)
    unstable = _classify_frequencies(np.array([[-0.2, 0.0, 1.0]]), 0.1)

    assert stable[:4] == ("stable", 0, 0, -0.02)
    assert "within tolerance" in stable[4][0]
    assert unstable[:4] == ("unstable", 1, 1, -0.2)
