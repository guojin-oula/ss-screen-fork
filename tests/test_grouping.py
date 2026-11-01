"""Tests for composition-template grouping (merged binary/ternary)."""

from __future__ import annotations

import pandas as pd
import pytest
from pymatgen.core import Composition

from ssscreen.config import composition_permutations
from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.grouping import (
    _template_key,
    attach_band_gaps,
    group_by_composition_template,
)


def _df(rows):
    """Build a tiny dataset. rows: list of (mp_id, formula, gap)."""
    records = []
    for mp_id, formula, gap in rows:
        comp = Composition(formula)
        records.append(
            {
                "material_id": mp_id,
                "reduced_composition": comp.get_reduced_composition_and_factor()[0],
                "band_gap": gap,
                "nelems": len(comp),
            }
        )
    return pd.DataFrame.from_records(records).set_index("material_id")


# ---------------------------------------------------------------------------
# template key construction
# ---------------------------------------------------------------------------
def test_template_key_binary():
    comp = Composition("CaS").get_reduced_composition_and_factor()[0]
    # perm [0,1] -> Ca fixed, S is X -> "CaX1"
    assert _template_key(comp, [0, 1]) == "CaX1"
    # perm [1,0] -> S fixed, Ca is X -> "S1X1" (S amount is 1)
    assert _template_key(comp, [1, 0]) == "SX1"


def test_template_key_ternary():
    comp = Composition("CaSnO3").get_reduced_composition_and_factor()[0]
    # perm [0,1,2] -> Ca,Sn fixed, O is X -> "CaSnX3"
    assert _template_key(comp, [0, 1, 2]) == "CaSnX3"
    # perm [0,2,1] -> Ca,O fixed, Sn is X -> "CaO3X1"
    assert _template_key(comp, [0, 2, 1]) == "CaO3X1"


def test_composition_permutations_validation():
    assert composition_permutations(2) == [[0, 1], [1, 0]]
    assert composition_permutations(3) == [[0, 1, 2], [0, 2, 1], [1, 2, 0]]
    with pytest.raises(ValueError):
        composition_permutations(4)


# ---------------------------------------------------------------------------
# group_by_composition_template
# ---------------------------------------------------------------------------
def test_binary_grouping_buckets_shared_template():
    """CaS and CaSe share the CaX template; CaS also generates SX."""
    df = _df([("mp-1", "CaS", 0.0), ("mp-2", "CaSe", 0.3), ("mp-3", "MgO", 1.5)])
    out = group_by_composition_template(df, nelems=2)
    # CaX1 contains both CaS and CaSe (Ca fixed, chalcogen varies).
    assert "CaX1" in out
    ca_members = {e[0] for e in out["CaX1"]}
    assert ca_members == {"mp-1", "mp-2"}
    # The X element recorded is the variable (S, Se).
    x_elems = sorted(e[1] for e in out["CaX1"])
    assert x_elems == ["S", "Se"]
    # MgO is alone in both its templates -> dropped (min_group_size=2).
    assert all("Mg" not in str(k) for k in out.keys())


def test_binary_template_two_directions():
    """CaS also produces the SX1 template (S fixed, Ca varies); with one member
    it is dropped, but if we add SrS it joins."""
    df = _df([("mp-1", "CaS", 0.0), ("mp-2", "SrS", 0.4)])
    out = group_by_composition_template(df, nelems=2)
    assert "SX1" in out
    members = {e[0] for e in out["SX1"]}
    assert members == {"mp-1", "mp-2"}


def test_min_group_size_filter():
    df = _df([("mp-1", "CaS", 0.0), ("mp-2", "MgO", 0.0)])
    # Each pair shares no template with size>=2 in either direction.
    out = group_by_composition_template(df, nelems=2, min_group_size=2)
    assert out == {}


def test_ternary_grouping():
    df = _df(
        [
            ("mp-1", "CaSnO", 0.0),
            ("mp-2", "CaPbO", 0.3),
            ("mp-3", "SrSnO", 0.5),
        ]
    )
    out = group_by_composition_template(df, nelems=3)
    # CaO1 fixed, Sn/Pb vary -> "CaOX1"
    assert "CaOX1" in out
    ca_o_members = {e[0] for e in out["CaOX1"]}
    assert ca_o_members == {"mp-1", "mp-2"}


# ---------------------------------------------------------------------------
# attach_band_gaps
# ---------------------------------------------------------------------------
def test_attach_band_gaps():
    entries = [["mp-1", "S", 0.0], ["mp-2", "Se", 0.3]]
    g = StructureGroup(
        entry_idx=[0, 1],
        A_elements=[["Ca"]],
        compositions=["CaS", "CaSe"],
        group_size=2,
        X_element=["S", "Se"],
        mp_ids=["mp-1", "mp-2"],
        group_repr="x",
    )
    attach_band_gaps([g], entries)
    assert g.band_gaps == [0.0, 0.3]
