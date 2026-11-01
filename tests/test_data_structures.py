"""Tests for local POSCAR/CIF dataset normalization."""

from __future__ import annotations

import pandas as pd
import pytest
from pymatgen.core import Lattice, Structure

from ssscreen.data.structures import load_structure_dataset


def _write_poscar(path, formula: str) -> None:
    comp = formula.replace("Se", "Q").replace("Te", "R")
    species = (
        comp.replace("Ca", "Ca ")
        .replace("S", "S ")
        .replace("Q", "Se ")
        .replace("R", "Te ")
        .split()
    )
    structure = Structure(Lattice.cubic(5.6), species, [[0, 0, 0], [0.5, 0.5, 0.5]])
    path.parent.mkdir(parents=True, exist_ok=True)
    structure.to(filename=str(path), fmt="poscar")


def test_load_structure_dataset_recurses_poscar_folders(tmp_path):
    root = tmp_path / "inputs"
    _write_poscar(root / "CaS" / "POSCAR", "CaS")
    _write_poscar(root / "CaSe" / "POSCAR", "CaSe")
    output = tmp_path / "local.df"
    provenance = tmp_path / "local.provenance.json"

    df = load_structure_dataset(
        input_dirs=[root],
        output=output,
        band_gap_default=0.2,
        e_hull_default=0.01,
        source="fixture-poscar",
        provenance_path=provenance,
    )

    assert output.exists()
    assert provenance.exists()
    assert list(df.index) == ["CaS", "CaSe"]
    assert set(df["formula"]) == {"CaS", "CaSe"}
    assert df["band_gap"].tolist() == [0.2, 0.2]
    assert df["e_hull"].tolist() == [0.01, 0.01]
    assert df["source"].tolist() == ["fixture-poscar", "fixture-poscar"]


def test_load_structure_dataset_uses_metadata(tmp_path):
    root = tmp_path / "inputs"
    _write_poscar(root / "CaS" / "POSCAR", "CaS")
    metadata = tmp_path / "metadata.csv"
    pd.DataFrame(
        [
            {
                "material_id": "CaS",
                "band_gap": 0.05,
                "e_hull": 0.0,
                "source": "mp-like",
            }
        ]
    ).to_csv(metadata, index=False)

    df = load_structure_dataset(input_dirs=[root], output=tmp_path / "local.df", metadata_path=metadata)

    assert df.loc["CaS", "band_gap"] == 0.05
    assert df.loc["CaS", "e_hull"] == 0.0
    assert df.loc["CaS", "source"] == "mp-like"


def test_load_structure_dataset_rejects_missing_inputs(tmp_path):
    with pytest.raises(ValueError, match="no supported structure files"):
        load_structure_dataset(input_dirs=[tmp_path], output=tmp_path / "local.df")
