"""I/O helpers: load condensed-structure JSONs, group tables, gap CSVs.

Consolidates the small loaders scattered across the notebooks:
  * ``CondenseLoader`` — ported from ``screening-binary.ipynb:24`` (cached,
    multi-directory JSON lookup by material ID).
  * ``load_group_df`` / ``dump_group_df`` — read/write the group table as JSON.
  * ``read_mbj_gaps`` — parse the ``mbj_gaps_*_pmg_info.csv`` schema.
  * ``write_pairs_csv`` — write ``mbj_result_*.csv`` with the canonical schema.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd
from monty.serialization import loadfn

from ..pair.envmatch import StructureGroup


class CondenseLoader:
    """Cached, multi-directory loader for robocrys condensed-structure JSONs.

    Each directory is expected to contain ``{material_id}.json`` files (e.g.
    ``mp-1234.json``, ``wbm-5678.json``). The first directory that has a hit
    wins; results are memoised.

    Ported from ``screening-binary.ipynb:24`` (``CondenseLoader`` class). The
    upstream version hard-coded ``['wbm-dataset/condense/condensed',
    '../mp-condense/condensed']``; here the directories are a constructor arg.
    """

    def __init__(self, basedirs: Sequence[str | Path], use_cache: bool = True):
        self.basedirs = [Path(b) for b in basedirs]
        self.use_cache = use_cache
        self.cache: dict[str, dict | None] = {}

    def get_condensed(self, entry_id: str) -> dict | None:
        if self.use_cache and entry_id in self.cache:
            return self.cache[entry_id]
        result: dict | None = None
        for basedir in self.basedirs:
            path = basedir / f"{entry_id}.json"
            if path.exists():
                result = loadfn(str(path))
                break
        if self.use_cache:
            self.cache[entry_id] = result
        return result


# ---------------------------------------------------------------------------
# Group table I/O
# ---------------------------------------------------------------------------
_GROUP_COLUMNS = [
    "entry_idx",
    "A_elements",
    "compositions",
    "X_element",
    "mp_ids",
    "band_gaps",
    "group_size",
]


def groups_to_records(groups: Iterable[StructureGroup]) -> list[dict]:
    """Serialise an iterable of :class:`StructureGroup` to JSON-friendly dicts."""
    return [g.to_dict() for g in groups]


def dump_group_df(groups: Iterable[StructureGroup], path: str | Path) -> None:
    """Write groups to a JSON file (array of records).

    Mirrors the role of ``binary-group-df.json`` in the source workspace.
    """
    records = groups_to_records(groups)
    with open(path, "w") as f:
        json.dump(records, f)


def load_group_df(path: str | Path) -> list[StructureGroup]:
    """Read a group-JSON file back into :class:`StructureGroup` objects.

    Accepts two formats:

      * **Records array** (produced by :func:`dump_group_df`):
        ``[{column: value, ...}, ...]``.
      * **Pandas column-oriented** (produced by ``DataFrame.to_json`` in the
        source notebooks, e.g. ``binary-group-df.json``):
        ``{column: {row_index: value, ...}, ...}``.

    ``group_repr`` is reconstructed as empty (it is not part of the persisted
    schema); pair enumeration does not need it.
    """
    with open(path) as f:
        data = json.load(f)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "entry_idx" in data:
        # Pandas column-oriented: transpose column->{row:val} into row->{col:val}.
        import pandas as pd

        records = pd.read_json(str(path)).to_dict(orient="records")
    else:
        raise ValueError(
            f"Unrecognised group JSON layout in {path}: expected a records array "
            f"or a column-oriented dict with key 'entry_idx'."
        )

    groups: list[StructureGroup] = []
    for r in records:
        groups.append(
            StructureGroup(
                entry_idx=r["entry_idx"],
                A_elements=r["A_elements"],
                compositions=r["compositions"],
                group_size=r["group_size"],
                X_element=r["X_element"],
                mp_ids=r["mp_ids"],
                band_gaps=r.get("band_gaps", []),
                group_repr=r.get("group_repr", ""),
            )
        )
    return groups


# ---------------------------------------------------------------------------
# Gap CSV I/O
# ---------------------------------------------------------------------------
def read_mbj_gaps(path: str | Path) -> dict[str, list]:
    """Parse an ``mbj_gaps_*_pmg_info.csv`` into a ``{material_id: [gap, direct]}`` map.

    The CSV schema (with an unnamed index column) is::

        ,formula,material_id,direct,transition,band_gap

    Returns ``{material_id: [band_gap: float, direct: bool]}``, matching what
    :func:`ssscreen.pair.pairing.enumerate_pairs` expects.
    """
    df = pd.read_csv(path, index_col=0)
    out: dict[str, list] = {}
    for _, row in df.iterrows():
        out[str(row["material_id"])] = [float(row["band_gap"]), bool(row["direct"])]
    return out


def write_pairs_csv(pairs: pd.DataFrame, path: str | Path) -> None:
    """Write the pair DataFrame to CSV in the canonical ``mbj_result_*.csv`` schema."""
    pairs.to_csv(path)
