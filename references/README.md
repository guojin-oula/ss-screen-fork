# Historical upstream references

These files preserve read-only research provenance. They are not canonical package code and must not be executed as a workflow without review.

Snapshot: `2026-07-21`. Stored: 78; redacted: 2; aliases: 35; excluded: 101.

Large datasets, calculation directories, archives, `.aiida` data, generated scheduler artifacts, and secrets remain external.

## Source families

- [Robocrys condensation](mp-condense/README.md) — Single and batch robocrys condensation plus combined-archive construction.
- [Historical screening baseline](old-screen-202411/README.md) — Older grouping/pairing logic and its threshold/direct-gap behavior.
- [Pair screening](pair-screening/README.md) — MP/WBM loading, valence filtering, structure grouping, gap feedback, and pair enumeration.
- [Chalcopyrite prototype studies](prototypes/chalcopyrite/README.md) — CdSnSb2 PBE/HSE/mBJ/SOC workflows and executed band-analysis plots.
- [Rocksalt prototype studies](prototypes/rocksalt/README.md) — Rocksalt builders, endmember HSE/mBJ/SOC studies, PbSe-Te SQS, and band plots.
- [Zincblende prototype studies](prototypes/zincblend/README.md) — Zincblende builders and HSE/mBJ/SOC comparisons, including ABACUS launch knowledge.
- [Antiperovskite screening](screen-antiperovskite/README.md) — Prototype enumeration, MACE relaxation, mBJ/HSE launch, and hull analysis.
- [Band screening workflows](screen-mbj/README.md) — VASP and ABACUS PBE/HSE06/mBJ launch, recovery, k-path, analysis, and export flows.
- [Promising-material band verification](screen-promising/README.md) — PBE/HSE band workflows, MP structure acquisition, analysis, and result plots.
- [Vacancy and defect workflows](simple-defects/README.md) — Elemental references, manual/workchain vacancies, chemical potentials, SQS vacancies, and ranking.
- [WBM preparation](wbm-dataset/README.md) — WBM entry reconciliation, metadata validation, extxyz conversion, and condensation helpers.

See [`manifest.json`](manifest.json) for original paths, hashes, aliases, transformations, exclusions, and provenance.
