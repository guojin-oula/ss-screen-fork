"""Tests for Stage 6 alloy/SQS input artifact generation."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from monty.serialization import loadfn
from pymatgen.core import Lattice, Structure

from ssscreen.stability.sqs import generate_sqs_inputs


def _dataset() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "material_id": "mp-cas",
                "formula": "CaS",
                "composition": "CaS",
                "structure": Structure(
                    Lattice.cubic(5.6),
                    ["Ca", "S"],
                    [[0, 0, 0], [0.5, 0.5, 0.5]],
                ),
            },
            {
                "material_id": "mp-case",
                "formula": "CaSe",
                "composition": "CaSe",
                "structure": Structure(
                    Lattice.cubic(5.8),
                    ["Ca", "Se"],
                    [[0, 0, 0], [0.5, 0.5, 0.5]],
                ),
            },
        ]
    ).set_index("material_id")


def test_generate_sqs_inputs_writes_structures_and_manifest(tmp_path):
    pairs_path = tmp_path / "pairs.csv"
    dataset_path = tmp_path / "dataset.df"
    output_dir = tmp_path / "sqs"
    manifest = tmp_path / "manifest.jsonl"
    pd.DataFrame(
        [
            {
                "comp_a": "CaS",
                "comp_b": "CaSe",
                "mp_id_a": "mp-cas",
                "mp_id_b": "mp-case",
            }
        ]
    ).to_csv(pairs_path)
    _dataset().to_pickle(dataset_path)

    records = generate_sqs_inputs(
        pairs_path=pairs_path,
        dataset_path=dataset_path,
        output_dir=output_dir,
        manifest_path=manifest,
        target_fractions=[0.5],
        supercell=(2, 1, 1),
        seed=7,
    )

    assert len(records) == 1
    record = records[0]
    assert record["status"] == "written"
    assert record["generator"] == "random-substitution"
    assert record["mp_id_a"] == "mp-cas"
    assert record["mp_id_b"] == "mp-case"
    assert record["substitution"] == {"from": "S", "to": "Se"}
    assert record["target_fraction_b"] == 0.5
    assert record["actual_fraction_b"] == 0.5
    assert loadfn(record["endpoint_a_structure_path"]).composition.reduced_formula == "CaS"
    assert loadfn(record["endpoint_b_structure_path"]).composition.reduced_formula == "CaSe"
    assert len(record["endpoint_a_structure_sha256"]) == 64
    assert len(record["endpoint_b_structure_sha256"]) == 64
    assert len(record["structure_sha256"]) == 64
    structure = loadfn(record["structure_path"])
    assert structure.composition["Ca"] == 2
    assert structure.composition["S"] == 1
    assert structure.composition["Se"] == 1
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    assert rows == records


def test_generate_sqs_inputs_records_skipped_pairs(tmp_path):
    pairs_path = tmp_path / "pairs.csv"
    dataset_path = tmp_path / "dataset.df"
    manifest = tmp_path / "manifest.jsonl"
    pd.DataFrame(
        [
            {
                "comp_a": "CaS",
                "comp_b": "SrSe",
                "mp_id_a": "mp-cas",
                "mp_id_b": "mp-case",
            }
        ]
    ).to_csv(pairs_path)
    _dataset().to_pickle(dataset_path)

    records = generate_sqs_inputs(
        pairs_path=pairs_path,
        dataset_path=dataset_path,
        output_dir=tmp_path / "sqs",
        manifest_path=manifest,
        target_fractions=[0.5],
    )

    assert records[0]["status"] == "skipped"
    assert "single-site substitution" in records[0]["limitation"]


@pytest.mark.parametrize("fraction", [-0.1, 1.1])
def test_generate_sqs_inputs_rejects_invalid_target_fraction(tmp_path, fraction):
    pairs_path = tmp_path / "pairs.csv"
    dataset_path = tmp_path / "dataset.df"
    pd.DataFrame(
        [
            {
                "comp_a": "CaS",
                "comp_b": "CaSe",
                "mp_id_a": "mp-cas",
                "mp_id_b": "mp-case",
            }
        ]
    ).to_csv(pairs_path)
    _dataset().to_pickle(dataset_path)

    with pytest.raises(ValueError, match="target fractions must be between 0 and 1"):
        generate_sqs_inputs(
            pairs_path=pairs_path,
            dataset_path=dataset_path,
            output_dir=tmp_path / "sqs",
            manifest_path=tmp_path / "manifest.jsonl",
            target_fractions=[fraction],
        )


def test_generate_sqs_inputs_can_use_icet_backend(tmp_path):
    pytest.importorskip("icet")
    pairs_path = tmp_path / "pairs.csv"
    dataset_path = tmp_path / "dataset.df"
    manifest = tmp_path / "manifest.jsonl"
    pd.DataFrame(
        [
            {
                "comp_a": "CaS",
                "comp_b": "CaSe",
                "mp_id_a": "mp-cas",
                "mp_id_b": "mp-case",
            }
        ]
    ).to_csv(pairs_path)
    _dataset().to_pickle(dataset_path)

    records = generate_sqs_inputs(
        pairs_path=pairs_path,
        dataset_path=dataset_path,
        output_dir=tmp_path / "sqs",
        manifest_path=manifest,
        target_fractions=[0.5],
        supercell=(2, 1, 1),
        seed=7,
        backend="icet",
        cutoffs=[4.0],
        sqs_steps=10,
    )

    assert records[0]["status"] == "written"
    assert records[0]["generator"] == "icet-generate_sqs_from_supercells"
    structure = loadfn(records[0]["structure_path"])
    assert structure.composition["Ca"] == 2
    assert structure.composition["S"] == 1
    assert structure.composition["Se"] == 1


def test_icet_fraction_excludes_target_element_on_inactive_sites(tmp_path):
    pytest.importorskip("icet")
    pairs_path = tmp_path / "pairs.csv"
    dataset_path = tmp_path / "dataset.df"
    pd.DataFrame(
        [
            {
                "comp_a": "NaClF",
                "comp_b": "NaCl2",
                "mp_id_a": "mp-a",
                "mp_id_b": "mp-b",
            }
        ]
    ).to_csv(pairs_path, index=False)
    lattice = Lattice.cubic(5.0)
    pd.DataFrame(
        [
            {
                "material_id": "mp-a",
                "structure": Structure(
                    lattice,
                    ["Na", "Cl", "F"],
                    [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5]],
                ),
            },
            {
                "material_id": "mp-b",
                "structure": Structure(
                    lattice,
                    ["Na", "Cl", "Cl"],
                    [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5]],
                ),
            },
        ]
    ).set_index("material_id").to_pickle(dataset_path)

    records = generate_sqs_inputs(
        pairs_path=pairs_path,
        dataset_path=dataset_path,
        output_dir=tmp_path / "sqs",
        manifest_path=tmp_path / "manifest.jsonl",
        target_fractions=[0.5],
        supercell=(2, 1, 1),
        backend="icet",
        cutoffs=[4.0],
        sqs_steps=10,
    )

    assert records[0]["status"] == "written"
    assert records[0]["replaced_sites"] == 1
    assert records[0]["available_substitution_sites"] == 2
    assert records[0]["actual_fraction_b"] == 0.5
