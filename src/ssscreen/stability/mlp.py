"""Backend contracts and the MACE implementation for MLP structure relaxation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from pymatgen.core import Structure


@dataclass(frozen=True)
class RelaxationOutcome:
    """Backend-independent result returned after one structure optimization."""

    structure: Structure
    initial_energy_total_ev: float
    energy_total_ev: float
    forces_ev_per_angstrom: list[list[float]]
    stress_ev_per_angstrom3: list[list[float]]
    steps: int
    converged: bool


@dataclass(frozen=True)
class SinglePointOutcome:
    """Backend-independent energy, force, and stress result for one structure."""

    energy_total_ev: float
    forces_ev_per_angstrom: list[list[float]]
    stress_ev_per_angstrom3: list[list[float]]


class ForceBackend(Protocol):
    """Minimal contract for finite-displacement force evaluation."""

    @property
    def metadata(self) -> dict[str, Any]:
        """Return JSON-serializable model and runtime provenance."""

    def evaluate(self, structure: Structure) -> SinglePointOutcome:
        """Evaluate one fixed structure without changing positions or cell."""


class RelaxationBackend(Protocol):
    """Minimal contract implemented by an MLP relaxation backend."""

    @property
    def metadata(self) -> dict[str, Any]:
        """Return JSON-serializable model and runtime provenance."""

    def relax(
        self,
        structure: Structure,
        *,
        fmax: float,
        max_steps: int,
        relax_cell: bool,
    ) -> RelaxationOutcome:
        """Relax one structure and return final energy, forces, stress, and status."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MaceRelaxationBackend:
    """ASE-based MACE backend with one model load per process.

    The full-cell relaxation behavior follows the MACE/TorchSim research path in
    ``solid-solutions-all/solid-solutions-mace/stability/stability_line_mace.py``.
    ASE FIRE is used here so convergence and the actual step count remain explicit.
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str = "cpu",
        dtype: str = "float32",
        model_name: str | None = None,
    ) -> None:
        path = Path(model_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"MACE model does not exist: {path}")
        if dtype not in {"float32", "float64"}:
            raise ValueError("MACE dtype must be 'float32' or 'float64'")

        try:
            import torch
            from mace.calculators import MACECalculator
        except ImportError as exc:
            raise ImportError(
                "MACE relaxation requires the optional `mlp` dependencies; "
                "install `ss-screen[mlp]`"
            ) from exc

        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(f"CUDA device requested but unavailable: {device}")

        self._metadata = {
            "name": "mace",
            "version": version("mace-torch"),
            "model_name": model_name or path.stem,
            "model_sha256": _sha256_file(path),
            "device": device,
            "dtype": dtype,
        }
        self._calculator = MACECalculator(
            model_paths=str(path),
            device=device,
            default_dtype=dtype,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        """Return MACE model and runtime provenance without exposing the local path."""
        return dict(self._metadata)

    def evaluate(self, structure: Structure) -> SinglePointOutcome:
        """Evaluate MACE energy, forces, and Cartesian stress at fixed geometry."""
        from pymatgen.io.ase import AseAtomsAdaptor

        atoms = AseAtomsAdaptor.get_atoms(structure)
        atoms.pbc = True
        atoms.calc = self._calculator
        energy = float(atoms.get_potential_energy())
        forces = np.asarray(atoms.get_forces(), dtype=float)
        stress = np.asarray(atoms.get_stress(voigt=False), dtype=float)
        return SinglePointOutcome(
            energy_total_ev=energy,
            forces_ev_per_angstrom=forces.tolist(),
            stress_ev_per_angstrom3=stress.tolist(),
        )

    def relax(
        self,
        structure: Structure,
        *,
        fmax: float,
        max_steps: int,
        relax_cell: bool,
    ) -> RelaxationOutcome:
        """Relax atomic positions, optionally together with the periodic cell."""
        from ase.filters import FrechetCellFilter
        from ase.optimize import FIRE
        from pymatgen.io.ase import AseAtomsAdaptor

        atoms = AseAtomsAdaptor.get_atoms(structure)
        atoms.pbc = True
        atoms.calc = self._calculator
        initial_energy = float(atoms.get_potential_energy())

        optimizable = FrechetCellFilter(atoms) if relax_cell else atoms
        optimizer = FIRE(optimizable, logfile=None)
        converged = bool(optimizer.run(fmax=fmax, steps=max_steps))

        energy = float(atoms.get_potential_energy())
        forces = np.asarray(atoms.get_forces(), dtype=float)
        stress = np.asarray(atoms.get_stress(voigt=False), dtype=float)
        relaxed = AseAtomsAdaptor.get_structure(atoms)
        return RelaxationOutcome(
            structure=relaxed,
            initial_energy_total_ev=initial_energy,
            energy_total_ev=energy,
            forces_ev_per_angstrom=forces.tolist(),
            stress_ev_per_angstrom3=stress.tolist(),
            steps=int(optimizer.get_number_of_steps()),
            converged=converged,
        )
