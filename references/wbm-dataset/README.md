# WBM preparation

WBM entry reconciliation, metadata validation, extxyz conversion, and condensation helpers.

**Current package coverage:** Extxyz consumption is migrated; raw entry/summary reconciliation remains partial.

**Historical cautions:** The full WBM dataset remains external; historical scripts rely on fixed clean/dirty boundaries.

Notebook outputs and execution state are preserved. External datasets and calculation artifacts referenced by these files are not included.

## Artifacts

- [`wbm-dataset/README.txt`](source/README.txt) — stored
- `wbm-dataset/condense/condense.py` — alias of `mp-condense/condense.py`
- `wbm-dataset/condense/condense_one.py` — alias of `mp-condense/condense_one.py`
- [`wbm-dataset/condense/convert-json.py`](source/condense/convert-json.py) — stored
- [`wbm-dataset/convert_to_extxyz.py`](source/convert_to_extxyz.py) — stored
