"""Selection and group filters: valence, element-exclusion, gap-diversity, size.

Each filter is a small named function so the criteria are auditable and
unit-testable. Mirrors ``valence-filter.ipynb`` (cell 11) and
``screening-binary.ipynb`` (cells 29, 36, 41).
"""

from __future__ import annotations

import pandas as pd
from pymatgen.analysis.bond_valence import BVAnalyzer
from pymatgen.core import Structure
from tqdm.auto import tqdm

from .envmatch import StructureGroup


# ---------------------------------------------------------------------------
# Valence filter
# ---------------------------------------------------------------------------
def is_valence_assignable(structure: Structure, analyzer: BVAnalyzer | None = None) -> bool:
    """Return ``True`` if oxidation states can be assigned by bond valence.

    Structures that raise ``ValueError`` are assumed metallic or mixed-valence
    and therefore unsuitable for tunable-gap solid solutions — they are dropped.

    Mirrors ``valence-filter.ipynb:11``.
    """
    analyzer = analyzer if analyzer is not None else BVAnalyzer()
    try:
        analyzer.get_valences(structure)
        return True
    except ValueError:
        return False


def valence_filter(
    df: pd.DataFrame,
    *,
    structure_col: str = "structure",
    verbose: bool = True,
) -> list[str]:
    """Return the list of material IDs whose valences are assignable.

    Mirrors ``valence-filter.ipynb:11-12``.
    """
    ana = BVAnalyzer()
    iterator = df.iterrows()
    if verbose:
        iterator = tqdm(df.iterrows(), total=len(df), desc="valence filter")
    valid_ids: list[str] = []
    for mp_id, row in iterator:
        if is_valence_assignable(row[structure_col], ana):
            valid_ids.append(str(mp_id))
    return valid_ids


# ---------------------------------------------------------------------------
# Element exclusion (operates on a single group)
# ---------------------------------------------------------------------------
def apply_element_exclusion(
    group: StructureGroup,
    excluded: set[str] | frozenset[str],
) -> StructureGroup | None:
    """Drop excluded elements from a group; return ``None`` if it becomes invalid.

    Rules (mirrors ``screening-binary.ipynb:29``):
      * If any excluded element appears in the spectator ``A_elements``, drop
        the whole group.
      * Otherwise drop individual members whose ``X_element`` is excluded.
      * The group survives only if it still has ``> 1`` members and ``> 1``
        distinct X elements remain.

    Returns a *new* :class:`StructureGroup`; the input is not mutated.
    """
    import dataclasses

    if any(x in group.A_elements[0] for x in excluded):
        return None

    keep = [i for i, x in enumerate(group.X_element) if x not in excluded]
    if len(keep) <= 1 or len({group.X_element[i] for i in keep}) <= 1:
        return None

    new = dataclasses.replace(group)
    for f in ("entry_idx", "A_elements", "compositions", "X_element", "mp_ids", "band_gaps"):
        setattr(new, f, [getattr(group, f)[i] for i in keep])
    new.group_size = len(new.mp_ids)
    return new


# ---------------------------------------------------------------------------
# Gap-diversity gate
# ---------------------------------------------------------------------------
def has_gap_diversity(group: StructureGroup, require_zero: bool = True) -> bool:
    """Check the group has the gap diversity needed for tunable alloying.

    With ``require_zero=True`` (default, cell 29): the group must contain at
    least one zero-gap member (``any(x == 0)``). The upstream code only checked
    for a zero member; the original commented-out line also required a member
    in ``(0.1, 0.5)``.
    """
    gaps = group.band_gaps
    if require_zero:
        return any(x == 0 for x in gaps)
    # Relaxed rule: at least two distinct gap regimes.
    return any(x == 0 for x in gaps) and any(x > 0 for x in gaps)


# ---------------------------------------------------------------------------
# Size gate (primitive-cell atom count)
# ---------------------------------------------------------------------------
def apply_size_gate(
    calc_df: pd.DataFrame,
    max_natoms: int,
    *,
    structure_col: str = "structure",
    prim_col: str = "primitive_structure",
) -> pd.DataFrame:
    """Keep only rows whose primitive cell has at most ``max_natoms`` atoms.

    Adds a ``primitive_structure`` column (via ``get_primitive_structure``) and
    a ``natoms`` column if absent. Mirrors ``screening-binary.ipynb:36,41``.
    """
    df = calc_df.copy()
    if prim_col not in df.columns:
        df[prim_col] = df[structure_col].apply(lambda s: s.get_primitive_structure())
    if "natoms" not in df.columns:
        df["natoms"] = df[prim_col].apply(len)
    return df.loc[df["natoms"] < max_natoms, :]
