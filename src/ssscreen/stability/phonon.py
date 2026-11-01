"""Resumable finite-displacement phonons driven by MLIP forces."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from monty.serialization import dumpfn, loadfn
from pymatgen.core import Lattice, Structure

from ..config import PhononSettings
from .mlp import ForceBackend

PHONON_SCHEMA_VERSION = 1
FORCE_BACKEND_FIELDS = ("name", "version", "model_sha256", "dtype")
SOURCE_METADATA_FIELDS = (
    "structure_role",
    "pair_index",
    "source_group_index",
    "mp_id_a",
    "mp_id_b",
    "comp_a",
    "comp_b",
    "target_fraction_b",
    "actual_fraction_b",
    "material_id",
    "composition",
)
SUMMARY_COLUMNS = [
    "schema_version",
    "phonon_id",
    "structure_id",
    "structure_role",
    "pair_index",
    "target_fraction_b",
    "actual_fraction_b",
    "supercell_matrix",
    "unitcell_atom_count",
    "supercell_atom_count",
    "displacement_distance_angstrom",
    "displacement_count",
    "force_success_count",
    "force_coverage",
    "backend_name",
    "backend_version",
    "model_name",
    "model_sha256",
    "dtype",
    "mesh",
    "minimum_mesh_frequency_THz",
    "minimum_band_frequency_THz",
    "significant_imaginary_mode_count",
    "imaginary_qpoint_count",
    "imaginary_tolerance_THz",
    "force_constants_max_drift_before",
    "force_constants_max_drift_after",
    "nac_applied",
    "status",
    "dynamical_status",
    "warnings",
    "error",
]


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_write_dataframe(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix or ".csv", dir=path.parent
    )
    os.close(descriptor)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_write_structure(structure: Structure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix or ".json", dir=path.parent
    )
    os.close(descriptor)
    try:
        dumpfn(structure, temporary)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_name(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-.")
    return cleaned or "structure"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number} of {path}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number} of {path} is not a JSON object")
            records.append(record)
    return records


def _write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    _atomic_write_text(path, text)


def _resolve_artifact_path(raw_path: str | Path, source_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    relative = source_path.parent / path
    return relative if relative.exists() else path


def _structure_to_phonopy(structure: Structure):
    from phonopy.structure.atoms import PhonopyAtoms

    return PhonopyAtoms(
        symbols=[site.specie.symbol for site in structure],
        cell=np.asarray(structure.lattice.matrix, dtype=float),
        scaled_positions=np.asarray(structure.frac_coords, dtype=float),
    )


def _phonopy_to_structure(atoms) -> Structure:
    return Structure(
        Lattice(np.asarray(atoms.cell, dtype=float)),
        list(atoms.symbols),
        np.asarray(atoms.scaled_positions, dtype=float),
    )


def choose_supercell(
    structure: Structure,
    *,
    explicit: tuple[int, int, int] | None,
    min_length: float,
    max_atoms: int,
) -> tuple[int, int, int]:
    """Choose a diagonal supercell and enforce the configured atom-count cap."""
    if min_length <= 0:
        raise ValueError("minimum supercell length must be positive")
    if max_atoms <= 0:
        raise ValueError("maximum supercell atom count must be positive")
    if explicit is not None:
        if len(explicit) != 3 or any(value <= 0 for value in explicit):
            raise ValueError("supercell must contain three positive integers")
        dimensions = tuple(int(value) for value in explicit)
    else:
        dimensions = tuple(
            max(1, math.ceil(min_length / length)) for length in structure.lattice.abc
        )
    atom_count = len(structure) * math.prod(dimensions)
    if atom_count > max_atoms:
        raise ValueError(
            f"phonon supercell has {atom_count} atoms, above configured maximum {max_atoms}"
        )
    return dimensions


def _source_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record[field] for field in SOURCE_METADATA_FIELDS if field in record}


def _skipped_manifest_record(
    record: dict[str, Any], *, phonon_id: str, error: str
) -> dict[str, Any]:
    return {
        "schema_version": PHONON_SCHEMA_VERSION,
        "phonon_id": phonon_id,
        "structure_id": record.get("structure_id"),
        **_source_metadata(record),
        "status": "skipped",
        "error": error,
    }


def export_phonon_tasks(
    *,
    relax_results_path: str | Path,
    output_dir: str | Path,
    manifest_path: str | Path,
    structure_ids: tuple[str, ...] | list[str] = (),
    include_endmembers: bool = False,
    supercell: tuple[int, int, int] | None = None,
    displacement_distance: float = PhononSettings.displacement_distance,
    symmetry_tolerance: float = PhononSettings.symmetry_tolerance,
    min_supercell_length: float = PhononSettings.min_supercell_length,
    max_supercell_atoms: int = PhononSettings.max_supercell_atoms,
    max_input_force: float = PhononSettings.max_input_force,
    allow_loose_input: bool = False,
) -> list[dict[str, Any]]:
    """Generate reference and finite-displacement supercells from Stage 7 results."""
    if displacement_distance <= 0:
        raise ValueError("displacement distance must be positive")
    if symmetry_tolerance <= 0:
        raise ValueError("symmetry tolerance must be positive")
    if max_input_force <= 0:
        raise ValueError("maximum input force must be positive")

    try:
        from phonopy import Phonopy
    except ImportError as exc:
        raise ImportError(
            "phonon generation requires the optional `phonon` dependencies; "
            "install `ss-screen[phonon]`"
        ) from exc

    relax_results_path = Path(relax_results_path)
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path)
    selected_ids = set(structure_ids)
    records = _read_jsonl(relax_results_path)
    if selected_ids:
        missing_ids = selected_ids - {str(record.get("structure_id")) for record in records}
        if missing_ids:
            raise ValueError(f"relaxation results do not contain: {', '.join(sorted(missing_ids))}")

    manifest_records: list[dict[str, Any]] = []
    selected_count = 0
    for record in records:
        structure_id = record.get("structure_id")
        if not isinstance(structure_id, str) or not structure_id:
            continue
        if selected_ids and structure_id not in selected_ids:
            continue
        role = record.get("structure_role")
        if not selected_ids and role != "sqs" and not (include_endmembers and role == "endmember"):
            continue
        selected_count += 1

        base_settings = {
            "source_structure_id": structure_id,
            "requested_supercell": list(supercell) if supercell is not None else None,
            "displacement_distance_angstrom": float(displacement_distance),
            "symmetry_tolerance": float(symmetry_tolerance),
            "min_supercell_length_angstrom": float(min_supercell_length),
            "max_supercell_atoms": int(max_supercell_atoms),
        }
        provisional_id = f"{_safe_name(structure_id)}-{_json_sha256(base_settings)[:12]}"
        if record.get("status") != "success" or record.get("usable_for_thermodynamics") is not True:
            manifest_records.append(
                _skipped_manifest_record(
                    record,
                    phonon_id=provisional_id,
                    error="source relaxation is not successful and usable",
                )
            )
            continue
        try:
            residual_force = float(record["max_force_eV_per_angstrom"])
        except (KeyError, TypeError, ValueError):
            manifest_records.append(
                _skipped_manifest_record(
                    record,
                    phonon_id=provisional_id,
                    error="source relaxation has no valid maximum force",
                )
            )
            continue
        if not math.isfinite(residual_force):
            manifest_records.append(
                _skipped_manifest_record(
                    record,
                    phonon_id=provisional_id,
                    error="source relaxation maximum force is not finite",
                )
            )
            continue
        if residual_force > max_input_force and not allow_loose_input:
            manifest_records.append(
                _skipped_manifest_record(
                    record,
                    phonon_id=provisional_id,
                    error=(
                        f"source maximum force {residual_force:.6g} eV/Angstrom exceeds "
                        f"phonon limit {max_input_force:.6g}"
                    ),
                )
            )
            continue

        try:
            output_structure = record["output_structure"]
            if not isinstance(output_structure, dict) or "path" not in output_structure:
                raise ValueError("source relaxation has no output structure path")
            structure_path = _resolve_artifact_path(output_structure["path"], relax_results_path)
            if not structure_path.is_file():
                raise FileNotFoundError(f"relaxed structure does not exist: {structure_path}")
            structure_hash = _sha256_file(structure_path)
            declared_hash = output_structure.get("sha256")
            if declared_hash is not None and declared_hash != structure_hash:
                raise ValueError("relaxed structure SHA-256 differs from Stage 7 record")
            structure = loadfn(structure_path)
            if not isinstance(structure, Structure):
                raise TypeError("relaxed artifact is not a pymatgen Structure")
            dimensions = choose_supercell(
                structure,
                explicit=supercell,
                min_length=min_supercell_length,
                max_atoms=max_supercell_atoms,
            )
            settings = {
                **base_settings,
                "source_structure_sha256": structure_hash,
                "supercell_matrix": list(dimensions),
                "primitive_matrix": "identity",
                "phonopy_version": version("phonopy"),
            }
            settings_hash = _json_sha256(settings)
            phonon_id = f"{_safe_name(structure_id)}-{settings_hash[:12]}"
            workdir = output_dir / phonon_id
            workdir.mkdir(parents=True, exist_ok=True)
            phonon = Phonopy(
                _structure_to_phonopy(structure),
                supercell_matrix=np.diag(dimensions),
                primitive_matrix=np.eye(3),
                symprec=symmetry_tolerance,
            )
            phonon.generate_displacements(distance=displacement_distance)
            displaced = phonon.supercells_with_displacements
            if not displaced:
                raise RuntimeError("Phonopy generated no displaced supercells")
            phonopy_yaml = workdir / "phonopy_disp.yaml"
            phonon.save(filename=phonopy_yaml)

            shared = {
                "schema_version": PHONON_SCHEMA_VERSION,
                "phonon_id": phonon_id,
                "structure_id": structure_id,
                **_source_metadata(record),
                "source_relaxation_backend": record.get("backend"),
                "source_relaxed_structure": {
                    "path": str(structure_path),
                    "sha256": structure_hash,
                },
                "source_max_force_eV_per_angstrom": residual_force,
                "loose_input_allowed": bool(allow_loose_input),
                "settings": settings,
                "settings_sha256": settings_hash,
                "phonopy_yaml_path": str(phonopy_yaml),
                "unitcell_atom_count": len(structure),
                "supercell_atom_count": len(phonon.supercell),
                "displacement_count": len(displaced),
                "status": "written",
            }
            reference_path = workdir / "structures" / "reference.json"
            reference_structure = _phonopy_to_structure(phonon.supercell)
            _atomic_write_structure(reference_structure, reference_path)
            manifest_records.append(
                {
                    **shared,
                    "task_id": f"{phonon_id}-reference",
                    "task_role": "reference",
                    "displacement_index": None,
                    "structure_path": str(reference_path),
                    "structure_sha256": _sha256_file(reference_path),
                }
            )
            for displacement_index, atoms in enumerate(displaced, start=1):
                displacement_path = (
                    workdir / "structures" / f"displacement-{displacement_index:04d}.json"
                )
                _atomic_write_structure(_phonopy_to_structure(atoms), displacement_path)
                manifest_records.append(
                    {
                        **shared,
                        "task_id": f"{phonon_id}-displacement-{displacement_index:04d}",
                        "task_role": "displacement",
                        "displacement_index": displacement_index,
                        "structure_path": str(displacement_path),
                        "structure_sha256": _sha256_file(displacement_path),
                    }
                )
        except Exception as exc:
            manifest_records.append(
                _skipped_manifest_record(
                    record,
                    phonon_id=provisional_id,
                    error=f"{type(exc).__name__}: {exc}"[:2000],
                )
            )

    if selected_count == 0:
        raise ValueError("no relaxation records matched the requested phonon selection")
    _write_jsonl(manifest_records, manifest_path)
    return manifest_records


def _validate_single_point(outcome, atom_count: int) -> tuple[float, np.ndarray, np.ndarray]:
    energy = float(outcome.energy_total_ev)
    forces = np.asarray(outcome.forces_ev_per_angstrom, dtype=float)
    stress = np.asarray(outcome.stress_ev_per_angstrom3, dtype=float)
    if forces.shape != (atom_count, 3):
        raise ValueError(f"backend returned force shape {forces.shape}; expected {(atom_count, 3)}")
    if stress.shape != (3, 3):
        raise ValueError(f"backend returned stress shape {stress.shape}; expected (3, 3)")
    if not np.all(np.isfinite([energy, *forces.ravel(), *stress.ravel()])):
        raise ValueError("backend returned non-finite energy, force, or stress values")
    return energy, forces, stress


def _force_fingerprint(task: dict[str, Any], backend: dict[str, Any]) -> str:
    return _json_sha256(
        {
            "schema_version": PHONON_SCHEMA_VERSION,
            "task_id": task["task_id"],
            "structure_sha256": task["structure_sha256"],
            "settings_sha256": task["settings_sha256"],
            "backend": backend,
        }
    )


def _force_backend_compatible(task: dict[str, Any], backend: dict[str, Any]) -> bool:
    source = task.get("source_relaxation_backend")
    if not isinstance(source, dict):
        return False
    return source.get("name") == backend.get("name") and source.get("model_sha256") == backend.get(
        "model_sha256"
    )


def evaluate_phonon_forces(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    results_path: str | Path,
    backend: ForceBackend,
    overwrite: bool = False,
    retry_failed: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Evaluate reference and displaced structures with a fixed MLIP backend."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    results_path = Path(results_path)
    tasks = [record for record in _read_jsonl(manifest_path) if record.get("status") == "written"]
    task_ids = [str(task.get("task_id")) for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("phonon manifest contains duplicate task IDs")
    if limit is not None:
        tasks = tasks[:limit]
    backend_metadata = backend.metadata
    records: list[dict[str, Any]] = []

    for task in tasks:
        task_id = str(task["task_id"])
        structure_path = _resolve_artifact_path(task["structure_path"], manifest_path)
        structure_hash = _sha256_file(structure_path)
        if structure_hash != task.get("structure_sha256"):
            raise ValueError(f"phonon task structure SHA-256 differs for {task_id}")
        fingerprint = _force_fingerprint(task, backend_metadata)
        record_path = output_dir / "records" / f"{_safe_name(task_id)}.json"
        if record_path.exists() and not overwrite:
            existing = json.loads(record_path.read_text(encoding="utf-8"))
            if existing.get("run_fingerprint") != fingerprint:
                raise ValueError(f"existing force settings differ for {task_id}; use --overwrite")
            if existing.get("status") != "failed" or not retry_failed:
                records.append(existing)
                continue

        base = {
            "schema_version": PHONON_SCHEMA_VERSION,
            "phonon_id": task["phonon_id"],
            "structure_id": task["structure_id"],
            "task_id": task_id,
            "task_role": task["task_role"],
            "displacement_index": task.get("displacement_index"),
            "input_structure": {"path": str(structure_path), "sha256": structure_hash},
            "settings_sha256": task["settings_sha256"],
            "backend": backend_metadata,
            "run_fingerprint": fingerprint,
        }
        started = time.perf_counter()
        try:
            if not _force_backend_compatible(task, backend_metadata):
                raise ValueError(
                    "MACE force model name/hash does not match the Stage 7 relaxation backend"
                )
            structure = loadfn(structure_path)
            if not isinstance(structure, Structure):
                raise TypeError("phonon task artifact is not a pymatgen Structure")
            energy, forces, stress = _validate_single_point(
                backend.evaluate(structure), len(structure)
            )
            force_norms = np.linalg.norm(forces, axis=1)
            record = {
                **base,
                "energy_total_eV": energy,
                "energy_per_atom_eV": energy / len(structure),
                "forces_eV_per_angstrom": forces.tolist(),
                "max_force_eV_per_angstrom": float(np.max(force_norms)),
                "rms_force_eV_per_angstrom": float(np.sqrt(np.mean(force_norms**2))),
                "stress_eV_per_angstrom3": stress.tolist(),
                "status": "success",
                "runtime_seconds": float(time.perf_counter() - started),
                "error": None,
            }
        except Exception as exc:
            record = {
                **base,
                "status": "failed",
                "runtime_seconds": float(time.perf_counter() - started),
                "error": f"{type(exc).__name__}: {exc}"[:2000],
            }
        _atomic_write_text(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n")
        records.append(record)

    _write_jsonl(records, results_path)
    return records


def _force_signature(record: dict[str, Any]) -> str | None:
    backend = record.get("backend")
    if not isinstance(backend, dict) or any(
        backend.get(field) in (None, "") for field in FORCE_BACKEND_FIELDS
    ):
        return None
    return _json_sha256({field: backend[field] for field in FORCE_BACKEND_FIELDS})


def _base_summary(task: dict[str, Any]) -> dict[str, Any]:
    row = {column: None for column in SUMMARY_COLUMNS}
    settings = task.get("settings") if isinstance(task.get("settings"), dict) else {}
    row.update(
        {
            "schema_version": PHONON_SCHEMA_VERSION,
            "phonon_id": task.get("phonon_id"),
            "structure_id": task.get("structure_id"),
            "structure_role": task.get("structure_role"),
            "pair_index": task.get("pair_index"),
            "target_fraction_b": task.get("target_fraction_b"),
            "actual_fraction_b": task.get("actual_fraction_b"),
            "supercell_matrix": json.dumps(settings.get("supercell_matrix")),
            "unitcell_atom_count": task.get("unitcell_atom_count"),
            "supercell_atom_count": task.get("supercell_atom_count"),
            "displacement_distance_angstrom": settings.get("displacement_distance_angstrom"),
            "displacement_count": task.get("displacement_count"),
            "nac_applied": False,
            "status": "failed",
            "dynamical_status": "failed",
            "warnings": "",
        }
    )
    return row


def _write_band_csv(band_structure, path: Path) -> None:
    rows: list[dict[str, Any]] = []
    for path_index, (qpoints, distances, frequencies) in enumerate(
        zip(
            band_structure.qpoints,
            band_structure.distances,
            band_structure.frequencies,
            strict=True,
        )
    ):
        for point_index, (qpoint, distance, modes) in enumerate(
            zip(qpoints, distances, frequencies, strict=True)
        ):
            for mode_index, frequency in enumerate(modes):
                rows.append(
                    {
                        "path_index": path_index,
                        "point_index": point_index,
                        "distance": float(distance),
                        "q_x": float(qpoint[0]),
                        "q_y": float(qpoint[1]),
                        "q_z": float(qpoint[2]),
                        "mode_index": mode_index,
                        "frequency_THz": float(frequency),
                    }
                )
    _atomic_write_dataframe(pd.DataFrame(rows), path)


def _classify_frequencies(
    frequencies: np.ndarray, tolerance: float
) -> tuple[str, int, int, float, list[str]]:
    if tolerance < 0:
        raise ValueError("imaginary-frequency tolerance must be non-negative")
    array = np.asarray(frequencies, dtype=float)
    if array.ndim != 2 or not np.all(np.isfinite(array)):
        raise ValueError("mesh frequencies must be a finite qpoint-by-mode array")
    minimum = float(np.min(array))
    significant = array < -tolerance
    significant_count = int(np.count_nonzero(significant))
    qpoint_count = int(np.count_nonzero(np.any(significant, axis=1)))
    warnings: list[str] = []
    if significant_count:
        status = "unstable"
    else:
        status = "stable"
        if minimum < 0:
            warnings.append(f"minimum frequency {minimum:.6g} THz is negative but within tolerance")
    return status, significant_count, qpoint_count, minimum, warnings


def _force_constant_drift(force_constants: np.ndarray) -> float:
    array = np.asarray(force_constants, dtype=float)
    if array.ndim != 4:
        raise ValueError("force constants must be a four-dimensional array")
    return float(np.max(np.abs(np.sum(array, axis=1))))


def _collect_one(
    *,
    tasks: list[dict[str, Any]],
    force_records: dict[str, dict[str, Any]],
    manifest_path: Path,
    output_dir: Path,
    mesh: tuple[int, int, int],
    band_points: int,
    imaginary_tolerance: float,
    subtract_reference_forces: bool,
    symmetrize_force_constants: bool,
) -> dict[str, Any]:
    from phonopy import load as load_phonopy
    from phonopy.file_IO import write_force_constants_to_hdf5

    reference_tasks = [task for task in tasks if task.get("task_role") == "reference"]
    if len(reference_tasks) != 1:
        raise ValueError("phonon manifest must contain exactly one reference task")
    reference_task = reference_tasks[0]
    row = _base_summary(reference_task)
    expected_tasks = [task for task in tasks if task.get("status") == "written"]
    successful = [
        force_records.get(str(task["task_id"]))
        for task in expected_tasks
        if force_records.get(str(task["task_id"]), {}).get("status") == "success"
    ]
    row["force_success_count"] = len(successful)
    row["force_coverage"] = len(successful) / len(expected_tasks) if expected_tasks else 0.0
    if len(successful) != len(expected_tasks):
        missing = [
            str(task["task_id"])
            for task in expected_tasks
            if force_records.get(str(task["task_id"]), {}).get("status") != "success"
        ]
        raise ValueError(
            f"force coverage is incomplete; missing/failed tasks: {', '.join(missing[:8])}"
        )

    signatures = {_force_signature(record) for record in successful if record is not None}
    if None in signatures or len(signatures) != 1:
        raise ValueError("phonon force records do not share one complete model reference")
    backend = successful[0]["backend"]
    row.update(
        {
            "backend_name": backend.get("name"),
            "backend_version": backend.get("version"),
            "model_name": backend.get("model_name"),
            "model_sha256": backend.get("model_sha256"),
            "dtype": backend.get("dtype"),
        }
    )
    reference_record = force_records[str(reference_task["task_id"])]
    reference_forces = np.asarray(reference_record["forces_eV_per_angstrom"], dtype=float)
    displacement_tasks = sorted(
        [task for task in tasks if task.get("task_role") == "displacement"],
        key=lambda task: int(task["displacement_index"]),
    )
    sets_of_forces = []
    for task in displacement_tasks:
        forces = np.asarray(
            force_records[str(task["task_id"])]["forces_eV_per_angstrom"], dtype=float
        )
        if subtract_reference_forces:
            forces = forces - reference_forces
        sets_of_forces.append(forces)

    phonopy_yaml = _resolve_artifact_path(reference_task["phonopy_yaml_path"], manifest_path)
    phonon = load_phonopy(phonopy_yaml)
    phonon.forces = np.asarray(sets_of_forces, dtype=float)
    phonon.produce_force_constants(calculate_full_force_constants=True, show_drift=False)
    drift_before = _force_constant_drift(phonon.force_constants)
    if symmetrize_force_constants:
        phonon.symmetrize_force_constants(show_drift=False)
    drift_after = _force_constant_drift(phonon.force_constants)
    row["force_constants_max_drift_before"] = drift_before
    row["force_constants_max_drift_after"] = drift_after

    workdir = output_dir / str(reference_task["phonon_id"])
    workdir.mkdir(parents=True, exist_ok=True)
    write_force_constants_to_hdf5(
        phonon.force_constants,
        filename=str(workdir / "force_constants.hdf5"),
        physical_unit="eV/angstrom^2",
    )
    phonon.save(
        filename=workdir / "phonopy_params.yaml",
        settings={"force_constants": True},
    )

    mesh_result = phonon.run_mesh(list(mesh), is_gamma_center=True)
    mesh_frequencies = np.asarray(mesh_result.frequencies, dtype=float)
    np.savez_compressed(
        workdir / "mesh.npz",
        qpoints=np.asarray(mesh_result.qpoints, dtype=float),
        weights=np.asarray(mesh_result.weights, dtype=int),
        frequencies_THz=mesh_frequencies,
    )
    dynamical_status, imaginary_count, qpoint_count, minimum_mesh, warnings = _classify_frequencies(
        mesh_frequencies, imaginary_tolerance
    )
    row.update(
        {
            "mesh": json.dumps(list(mesh)),
            "minimum_mesh_frequency_THz": minimum_mesh,
            "significant_imaginary_mode_count": imaginary_count,
            "imaginary_qpoint_count": qpoint_count,
            "imaginary_tolerance_THz": imaginary_tolerance,
            "nac_applied": phonon.nac_params is not None,
        }
    )

    band_ok = False
    dos_ok = False
    try:
        phonon.auto_band_structure(
            npoints=band_points,
            write_yaml=True,
            filename=workdir / "band.yaml",
        )
        band = phonon.band_structure
        _write_band_csv(band, workdir / "phonon_band.csv")
        row["minimum_band_frequency_THz"] = float(
            min(np.min(frequencies) for frequencies in band.frequencies)
        )
        _atomic_write_text(
            workdir / "band_path.json",
            json.dumps(
                {
                    "labels": list(band.labels or []),
                    "path_connections": list(band.path_connections or []),
                    "band_points_per_segment": band_points,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        band_ok = True
    except Exception as exc:
        warnings.append(f"automatic band path failed: {type(exc).__name__}: {exc}")

    try:
        dos = phonon.run_total_dos()
        _atomic_write_dataframe(
            pd.DataFrame(
                {
                    "frequency_THz": np.asarray(dos.frequency_points, dtype=float),
                    "dos": np.asarray(dos.dos, dtype=float),
                }
            ),
            workdir / "phonon_dos.csv",
        )
        dos_ok = True
    except Exception as exc:
        warnings.append(f"phonon DOS failed: {type(exc).__name__}: {exc}")

    if band_ok:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            plotter = (
                phonon.plot_band_structure_and_dos() if dos_ok else phonon.plot_band_structure()
            )
            figure = plt.gcf()
            if figure.axes:
                figure.axes[0].set_ylabel("Frequency (THz)")
                if dos_ok:
                    figure.axes[-1].set_xlabel("DOS")
            plotter.savefig(workdir / "phonon_band_dos.png", dpi=200, bbox_inches="tight")
            plotter.savefig(workdir / "phonon_band_dos.pdf", bbox_inches="tight")
            plt.close("all")
        except Exception as exc:
            warnings.append(f"phonon plotting failed: {type(exc).__name__}: {exc}")
            dynamical_status = "uncertain" if dynamical_status == "stable" else dynamical_status
    if not row["nac_applied"]:
        warnings.append("non-analytical correction was not applied")
    if not band_ok:
        dynamical_status = "uncertain" if dynamical_status == "stable" else dynamical_status
    row.update(
        {
            "status": "success",
            "dynamical_status": dynamical_status,
            "warnings": "; ".join(warnings),
            "error": None,
        }
    )
    _atomic_write_text(
        workdir / "phonon_result.json",
        json.dumps(row, indent=2, sort_keys=True) + "\n",
    )
    return row


def collect_phonon_results(
    *,
    manifest_path: str | Path,
    force_results_path: str | Path,
    output_dir: str | Path,
    summary_path: str | Path,
    report_path: str | Path,
    mesh: tuple[int, int, int] = PhononSettings.mesh,
    band_points: int = PhononSettings.band_points,
    imaginary_tolerance: float = PhononSettings.imaginary_tolerance_thz,
    subtract_reference_forces: bool = True,
    symmetrize_force_constants: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build force constants, spectra, DOS, and stability summaries."""
    if len(mesh) != 3 or any(value <= 0 for value in mesh):
        raise ValueError("phonon mesh must contain three positive integers")
    if band_points < 2:
        raise ValueError("band points must be at least 2")
    if imaginary_tolerance < 0:
        raise ValueError("imaginary-frequency tolerance must be non-negative")

    manifest_path = Path(manifest_path)
    force_results_path = Path(force_results_path)
    output_dir = Path(output_dir)
    summary_path = Path(summary_path)
    report_path = Path(report_path)
    manifest = _read_jsonl(manifest_path)
    forces = _read_jsonl(force_results_path)
    force_by_task: dict[str, dict[str, Any]] = {}
    for record in forces:
        task_id = record.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("force result has no task_id")
        if task_id in force_by_task:
            raise ValueError(f"duplicate force result task_id: {task_id}")
        force_by_task[task_id] = record

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in manifest:
        phonon_id = task.get("phonon_id")
        if isinstance(phonon_id, str) and phonon_id:
            groups[phonon_id].append(task)

    rows: list[dict[str, Any]] = []
    for tasks in groups.values():
        written = [task for task in tasks if task.get("status") == "written"]
        if not written:
            row = _base_summary(tasks[0])
            row["error"] = tasks[0].get("error", "phonon task generation was skipped")
            rows.append(row)
            continue
        try:
            row = _collect_one(
                tasks=written,
                force_records=force_by_task,
                manifest_path=manifest_path,
                output_dir=output_dir,
                mesh=mesh,
                band_points=band_points,
                imaginary_tolerance=imaginary_tolerance,
                subtract_reference_forces=subtract_reference_forces,
                symmetrize_force_constants=symmetrize_force_constants,
            )
        except Exception as exc:
            row = _base_summary(written[0])
            expected = len(written)
            success_count = sum(
                force_by_task.get(str(task["task_id"]), {}).get("status") == "success"
                for task in written
            )
            row.update(
                {
                    "force_success_count": success_count,
                    "force_coverage": success_count / expected if expected else 0.0,
                    "mesh": json.dumps(list(mesh)),
                    "imaginary_tolerance_THz": imaginary_tolerance,
                    "error": f"{type(exc).__name__}: {exc}"[:2000],
                }
            )
        rows.append(row)

    frame = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    status_counts = Counter(str(value) for value in frame["status"])
    dynamical_counts = Counter(str(value) for value in frame["dynamical_status"])
    report = {
        "schema_version": PHONON_SCHEMA_VERSION,
        "manifest_path": str(manifest_path),
        "force_results_path": str(force_results_path),
        "output_dir": str(output_dir),
        "summary_path": str(summary_path),
        "structure_count": len(frame),
        "status_counts": dict(sorted(status_counts.items())),
        "dynamical_status_counts": dict(sorted(dynamical_counts.items())),
        "settings": {
            "mesh": list(mesh),
            "band_points": band_points,
            "imaginary_tolerance_THz": imaginary_tolerance,
            "subtract_reference_forces": subtract_reference_forces,
            "symmetrize_force_constants": symmetrize_force_constants,
        },
        "scientific_scope": (
            "harmonic finite-displacement MLIP screen; no significant imaginary modes "
            "does not establish finite-temperature miscibility or thermodynamic stability"
        ),
    }
    _atomic_write_dataframe(frame, summary_path)
    _atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return frame, report


def run_phonon_pipeline(
    *,
    relax_results_path: str | Path,
    output_dir: str | Path,
    backend: ForceBackend,
    settings: PhononSettings | None = None,
    structure_ids: tuple[str, ...] | list[str] = (),
    include_endmembers: bool = False,
    supercell: tuple[int, int, int] | None = None,
    allow_loose_input: bool = False,
    overwrite: bool = False,
    retry_failed: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run export, MACE force evaluation, and Phonopy collection end to end."""
    settings = settings or PhononSettings()
    output_dir = Path(output_dir)
    manifest_path = output_dir / "phonon_jobs.jsonl"
    force_results_path = output_dir / "phonon_force_results.jsonl"
    summary_path = output_dir / "phonon_summary.csv"
    report_path = output_dir / "phonon_summary.json"
    export_phonon_tasks(
        relax_results_path=relax_results_path,
        output_dir=output_dir / "inputs",
        manifest_path=manifest_path,
        structure_ids=structure_ids,
        include_endmembers=include_endmembers,
        supercell=supercell,
        displacement_distance=settings.displacement_distance,
        symmetry_tolerance=settings.symmetry_tolerance,
        min_supercell_length=settings.min_supercell_length,
        max_supercell_atoms=settings.max_supercell_atoms,
        max_input_force=settings.max_input_force,
        allow_loose_input=allow_loose_input,
    )
    evaluate_phonon_forces(
        manifest_path=manifest_path,
        output_dir=output_dir / "forces",
        results_path=force_results_path,
        backend=backend,
        overwrite=overwrite,
        retry_failed=retry_failed,
    )
    return collect_phonon_results(
        manifest_path=manifest_path,
        force_results_path=force_results_path,
        output_dir=output_dir / "results",
        summary_path=summary_path,
        report_path=report_path,
        mesh=settings.mesh,
        band_points=settings.band_points,
        imaginary_tolerance=settings.imaginary_tolerance_thz,
    )
