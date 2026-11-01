"""Pair enumeration: turn environment groups + computed gaps into alloying pairs.

The final stage. Two distinct rules from the source notebooks:

  * :func:`gaps_valid` — a *group* is promising iff it has both a "low" member
    (``gap < low_gap``) and a "direct small-gap" member
    (``direct_min < gap < direct_max``). Source: ``pairing_mbj_gaps_binary.ipynb:6``.
  * :func:`enumerate_pairs` — within a valid group, enumerate unordered member
    pairs ``(i, j)`` kept iff ``some member < pair_any_below``,
    ``some member > pair_any_above``, and ``neither > pair_both_below``.
    Source: ``pairing_mbj_gaps_binary.ipynb:8``.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence

import pandas as pd

from ..config import PairThresholds
from .envmatch import StructureGroup

# Type alias: a member's gap entry is ``[gap_eV: float, is_direct: bool]``.
GapEntry = tuple[float, bool] | list


def gaps_valid(gaps: Sequence[GapEntry], t: PairThresholds) -> bool:
    """Whether a group has the low + direct-small-gap diversity to be promising.

    Parameters mirror ``gaps_valid`` in ``pairing_mbj_gaps_binary.ipynb:6``.
    """
    has_direct = any(t.direct_min < g[0] < t.direct_max for g in gaps)
    has_low = any(g[0] < t.low_gap for g in gaps)
    return has_direct and has_low


def _pair_ok(gi: float, gj: float, t: PairThresholds) -> bool:
    """The cell-8 pair predicate on two member gaps."""
    if not (gi < t.pair_any_below or gj < t.pair_any_below):
        return False
    if not (gi > t.pair_any_above or gj > t.pair_any_above):
        return False
    if gi > t.pair_both_below or gj > t.pair_both_below:
        return False
    return True


def enumerate_pairs(
    group: StructureGroup,
    gaps: Sequence[GapEntry],
    t: PairThresholds,
) -> list[dict]:
    """Enumerate the kept unordered pairs within one group.

    ``gaps[k]`` is the ``[gap, is_direct]`` entry for member ``k`` of ``group``
    (parallel to ``group.compositions`` etc.). Returns a list of dicts with
    keys ``comp_a, comp_b, gap_a, gap_b, mp_id_a, mp_id_b, gap_direct_a,
    gap_direct_b`` — the schema of ``mbj_result_binary_20250426.csv``.

    Mirrors ``pairing_mbj_gaps_binary.ipynb:8``.
    """
    pairs: list[dict] = []
    n = len(group.compositions)
    for i, j in itertools.combinations(range(n), 2):
        gi, gj = gaps[i][0], gaps[j][0]
        if not _pair_ok(gi, gj, t):
            continue
        if group.compositions[i] == group.compositions[j]:
            continue
        pairs.append(
            {
                "comp_a": group.compositions[i],
                "comp_b": group.compositions[j],
                "gap_a": gi,
                "gap_b": gj,
                "mp_id_a": group.mp_ids[i],
                "mp_id_b": group.mp_ids[j],
                "gap_direct_a": gaps[i][1],
                "gap_direct_b": gaps[j][1],
            }
        )
    return pairs


def pairs_to_dataframe(pairs: Iterable[dict]) -> pd.DataFrame:
    """Collect pair dicts into the result DataFrame (empty if no pairs)."""
    return pd.DataFrame(list(pairs))


def attach_gaps_and_compress(
    group: StructureGroup,
    gap_map: dict[str, Sequence],
) -> tuple[StructureGroup, list] | None:
    """Attach per-member gaps, dropping members without a computed gap.

    Mirrors ``pairing_mbj_gaps_binary.ipynb`` cell 4: the group's
    ``compositions``/``mp_ids``/``X_element``/... are filtered in lockstep with
    the gap availability, so the returned (group, gaps) pair stays aligned.

    Returns ``None`` if fewer than 2 members retain a gap.
    """
    import dataclasses

    per_member = [gap_map.get(str(mid)) for mid in group.mp_ids]
    keep = [i for i, x in enumerate(per_member) if x is not None]
    if len(keep) < 2:
        return None

    new = dataclasses.replace(group)
    for fld in ("entry_idx", "A_elements", "compositions", "X_element", "mp_ids", "band_gaps"):
        old_val = getattr(group, fld)
        if old_val:  # only re-index non-empty lists
            setattr(new, fld, [old_val[i] for i in keep])
    new.group_size = len(keep)
    gaps = [per_member[i] for i in keep]
    return new, gaps


def filter_groups_by_gaps(
    groups: Iterable[StructureGroup],
    group_gaps: dict[str, Sequence[GapEntry]],
    t: PairThresholds,
) -> list[tuple[StructureGroup, Sequence[GapEntry]]]:
    """Yield ``(group, gaps)`` pairs whose gaps satisfy :func:`gaps_valid`.

    ``group_gaps`` maps a group identifier (``group.group_repr``) to the
    per-member gap entries. Groups need more than one member with a computed
    gap to be considered (mirrors ``pairing_mbj_gaps_binary.ipynb:4-5``).
    """
    out = []
    for group in groups:
        gaps = group_gaps.get(group.group_repr)
        if gaps is None or len(gaps) < 2:
            continue
        if gaps_valid(gaps, t):
            out.append((group, gaps))
    return out
