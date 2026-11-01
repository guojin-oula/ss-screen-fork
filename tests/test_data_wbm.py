"""Tests for WBM dataset normalization."""

from __future__ import annotations

import pandas as pd
import pytest
from ase import Atoms
from ase.io import write

from ssscreen.data.wbm import load_wbm_dataset


def test_load_wbm_dataset_normalizes_extxyz(tmp_path):
    xyz = tmp_path / "wbm.xyz"
    atoms = Atoms(
        "CaS",
        cell=[5.4, 5.4, 5.4],
        scaled_positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
        pbc=True,
    )
    atoms.info.update(
        {
            "WBM_idx": 7,
            "WBM_gap": 0.25,
            "WBM_e_hull": 0.01,
            "WBM_step": 3,
        }
    )
    write(xyz, [atoms], format="extxyz")

    df = load_wbm_dataset(xyz_path=xyz, output=tmp_path / "wbm.df")

    assert list(df.index) == ["wbm-7"]
    row = df.loc["wbm-7"]
    assert row.formula == "CaS"
    assert row.reduced_composition.reduced_formula == "CaS"
    assert row.nelems == 2
    assert row.band_gap == 0.25
    assert row.e_hull == 0.01
    assert row.source == "wbm"
    assert row.source_metadata["step"] == 3
    assert len(row.structure) == 2
    assert (tmp_path / "wbm.df").exists()


def test_strict_wbm_rejects_missing_gap_and_hull(tmp_path):
    xyz = tmp_path / "missing.xyz"
    atoms = Atoms(
        "CaS",
        cell=[5.4, 5.4, 5.4],
        scaled_positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
        pbc=True,
    )
    write(xyz, [atoms], format="extxyz")

    with pytest.raises(ValueError, match="missing required band_gap"):
        load_wbm_dataset(xyz_path=xyz, output=tmp_path / "wbm.df", strict=True)

    assert not (tmp_path / "wbm.df").exists()


def test_strict_wbm_requires_summary_row_alignment(tmp_path):
    xyz = tmp_path / "aligned.xyz"
    atoms = Atoms(
        "CaS",
        cell=[5.4, 5.4, 5.4],
        scaled_positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
        pbc=True,
    )
    write(xyz, [atoms, atoms.copy()], format="extxyz")
    summary = tmp_path / "summary.csv"
    pd.DataFrame([{"band_gap": 0.25, "e_hull": 0.01}]).to_csv(summary, index=False)

    with pytest.raises(ValueError, match="row count does not match"):
        load_wbm_dataset(
            xyz_path=xyz,
            summary_path=summary,
            output=tmp_path / "wbm.df",
            strict=True,
        )


def test_strict_wbm_accepts_aligned_summary_metadata(tmp_path):
    xyz = tmp_path / "summary.xyz"
    atoms = Atoms(
        "CaS",
        cell=[5.4, 5.4, 5.4],
        scaled_positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
        pbc=True,
    )
    atoms.info["WBM_idx"] = 7
    write(xyz, [atoms], format="extxyz")
    summary = tmp_path / "summary.csv"
    pd.DataFrame([{"WBM_idx": 7, "band_gap": 0.35, "energy_above_hull": 0.02}]).to_csv(
        summary, index=False
    )

    frame = load_wbm_dataset(
        xyz_path=xyz,
        summary_path=summary,
        output=tmp_path / "wbm.df",
        strict=True,
    )

    assert frame.loc["wbm-7", "band_gap"] == 0.35
    assert frame.loc["wbm-7", "e_hull"] == 0.02
