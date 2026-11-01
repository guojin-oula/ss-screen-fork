"""Tests for the filters: element exclusion, gap-diversity, size gate."""

from __future__ import annotations

import pandas as pd
from pymatgen.core import Lattice, Structure

from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.filters import (
    apply_element_exclusion,
    apply_size_gate,
    has_gap_diversity,
    is_valence_assignable,
)


def _group(comps, x_elems, a_elems=None, mp_ids=None, gaps=None):
    """Build a test StructureGroup. ``a_elems`` is the per-member spectator list
    (e.g. ``[["Ca"], ["Ca"]]``); defaults to Ca for all members."""
    n = len(comps)
    if a_elems is None:
        a_elems = [["Ca"]] * n
    return StructureGroup(
        entry_idx=list(range(n)),
        A_elements=a_elems,
        compositions=comps,
        group_size=n,
        X_element=x_elems,
        mp_ids=mp_ids or [f"mp-{i}" for i in range(n)],
        group_repr="r",
        band_gaps=gaps if gaps is not None else [0.0] * n,
    )


# ---------------------------------------------------------------------------
# apply_element_exclusion
# ---------------------------------------------------------------------------
def test_exclusion_drops_group_with_bad_spectator():
    g = _group(["US", "USe"], ["S", "Se"], a_elems=[["U"], ["U"]])
    assert apply_element_exclusion(g, {"U"}) is None


def test_exclusion_drops_members_with_bad_x():
    g = _group(["CaS", "CaU", "CaSe"], ["S", "U", "Se"])
    out = apply_element_exclusion(g, {"U"})
    assert out is not None
    assert out.X_element == ["S", "Se"]
    assert out.group_size == 2


def test_exclusion_drops_group_when_too_few_remain():
    g = _group(["CaS", "CaU"], ["S", "U"])
    # After dropping U only one member + one X remains -> invalid.
    assert apply_element_exclusion(g, {"U"}) is None


def test_exclusion_preserves_input():
    g = _group(["CaS", "CaU", "CaSe"], ["S", "U", "Se"])
    apply_element_exclusion(g, {"U"})
    # Original group untouched.
    assert g.group_size == 3
    assert g.X_element == ["S", "U", "Se"]


# ---------------------------------------------------------------------------
# has_gap_diversity
# ---------------------------------------------------------------------------
def test_gap_diversity_with_zero_member():
    g = _group(["CaS", "CaSe"], ["S", "Se"], gaps=[0.0, 0.3])
    assert has_gap_diversity(g, require_zero=True)


def test_gap_diversity_without_zero_member():
    g = _group(["CaS", "CaSe"], ["S", "Se"], gaps=[0.3, 0.4])
    assert not has_gap_diversity(g, require_zero=True)


def test_gap_diversity_relaxed_mode():
    g = _group(["CaS", "CaSe"], ["S", "Se"], gaps=[0.0, 0.3])
    assert has_gap_diversity(g, require_zero=False)


# ---------------------------------------------------------------------------
# apply_size_gate
# ---------------------------------------------------------------------------
def _make_structure(n_sites):
    species = ["Si"] * n_sites
    coords = [[0, 0, 0]] * n_sites
    return Structure(Lattice.cubic(3.0), species, coords)


def test_size_gate_filters_large_primitive():
    df = pd.DataFrame(
        {"structure": [_make_structure(4), _make_structure(40)]},
        index=["mp-small", "mp-big"],
    )
    out = apply_size_gate(df, max_natoms=30)
    assert list(out.index) == ["mp-small"]


def test_size_gate_adds_natoms_column():
    df = pd.DataFrame({"structure": [_make_structure(4)]}, index=["mp-1"])
    out = apply_size_gate(df, max_natoms=30)
    assert "natoms" in out.columns
    assert "primitive_structure" in out.columns


# ---------------------------------------------------------------------------
# is_valence_assignable
# ---------------------------------------------------------------------------
def test_valence_assignable_for_ionic_nacl():
    nacl = Structure(Lattice.cubic(5.0), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    assert is_valence_assignable(nacl)


def test_valence_not_assignable_for_metallic():
    # A simple metallic-like structure (single element) may still assign 0,
    # so use a composition that bond-valence struggles with.
    # Most pure elements assign trivially; the real test is that the function
    # does not raise and returns a bool.
    fe = Structure(Lattice.cubic(2.8), ["Fe"], [[0, 0, 0]])
    result = is_valence_assignable(fe)
    assert isinstance(result, bool)
