# ss-screen — Project Plan

A formal Python package + CLI + documentation for **screening materials pairs that
form solid-solutions (alloys) with tunable band gaps**.

This document is the living blueprint for migrating the research workspace in
`/home/bonan/work/HC` (a collection of Jupyter notebooks and helper modules) into
a versioned, tested, documented package located at
`/home/bonan/work/HC/ss-screen`.

---

## 1. Scientific mission

Identify **isostructural prototype groups** in large materials databases (Materials
Project, WBM) such that:

- one endmember is a near-zero-gap semiconductor (`Eg < 0.1 eV`), and
- another endmember is a small *direct*-gap semiconductor (`0.1 < Eg < 0.8 eV`),

so that alloying (element substitution on the "variable" site `X`) tunes the gap
across the useful range. Promising pairs are then verified by high-fidelity DFT
band-structure calculations (HSE06 / mBJ) and ranked by cation vacancy formation
energies.

The central scientific insight encoded in the code: **group materials by a
robocrystallographer local-environment fingerprint in which the variable element
is relabeled to a placeholder `X`**, so that chemically distinct but
structurally identical prototypes collapse together. This is the `envmatch`
algorithm.

## 2. Current state (source workspace audit)

| Source dir | Stage | Reuse value |
|---|---|---|
| `pair-screening/envmatch.py` | Pair-screening core | **HIGH** — already modular; scientific heart |
| `pair-screening/datacollect.py` | Data loading | HIGH — dataset builders |
| `pair-screening/screening-*.ipynb` | Pair drivers | MEDIUM — logic to extract, paths to fix |
| `pair-screening/valence-filter.ipynb` | Pre-filter | MEDIUM — small reusable step |
| `pair-screening/pairing_mbj_*.ipynb` | Pair enumeration | MEDIUM — `gaps_valid` + pair builder |
| `mp-condense/condense.py`, `condense_one.py` | Robocrys condense worker | HIGH — already CLI-shaped, resumable |
| `mp-condense/combined_condensed.py` | Bundle JSONs | LOW — trivial helper |
| `wbm-dataset/convert_to_extxyz.py` | WBM data prep | MEDIUM — entry-to-summary matcher |
| `screen-mbj/*.ipynb` | AiiDA mBJ/HSE/PBE launch | REFERENCE — external task/result mapping only |
| `rocksalt/`, `zincblend/`, `Chalcopyrite /` | Prototype studies | LOW — keep as reference notebooks |
| `screen-antiperovskite/*.ipynb` | Combinatorial + hull | MEDIUM — scientific reference |
| `screen-promising/*.ipynb` | HSE06 verification | REFERENCE — external result provenance |
| `simple-defects/*.ipynb` | Vacancy ranking | MEDIUM — future defect design reference |
| `old-screen-202411/` | Baseline snapshot | LOW — historical reference only |

### Known defects to fix on migration
- `envmatch.StructureGroup.__getitem___` — misspelled dunder (3 trailing `_`); indexing silently broken.
- `screening-tenary.ipynb` ships a stale inlined copy of envmatch functions.
- Hardcoded relative paths everywhere (`wbm-dataset/condense/condensed`, `../mp-condense/condensed`).
- **Live Materials Project API key committed** in `screen-antiperovskite/satbility-mp.ipynb` and `simple-defects/` — must be externalized to env var.
- `condense.py` checkpoint copy has `if name ==` (missing `__main__`).
- Magic thresholds (`0.3/0.2/0.8 eV`, `natoms<30/45`, `e_hull<0.01`) scattered as literals.
- DFT-band-launcher functions (`launch_hse06`/`launch_mbj`/`get_upd*`) duplicated verbatim across 6+ notebooks; `rocksalt.ipynb` ≡ `zincblend.ipynb` cells 9–11.

## 3. Target package layout

```
ss-screen/
├── pyproject.toml              # packaging, deps, console_scripts, extras
├── README.md
├── LICENSE
├── src/ssscreen/
│   ├── __init__.py
│   ├── config.py               # central thresholds, element-exclusion lists, paths
│   ├── data/                   # data-layer (no AiiDA)
│   │   ├── __init__.py
│   │   ├── mp.py               # load_mp_dataset (MPOffline / mp_api)
│   │   ├── wbm.py              # load_wbm_data + entry-to-summary matcher
│   │   ├── condense.py         # robocrys StructureCondenser worker, resumable
│   │   └── io.py               # extxyz<->Structure, bundle_json_dir
│   ├── pair/                   # pair-screening core (no AiiDA)
│   │   ├── __init__.py
│   │   ├── envmatch.py         # find_unique_envs, group_similar_structures, StructureGroup
│   │   ├── grouping.py         # composition-template grouping (binary/ternary)
│   │   ├── filters.py          # valence filter, element exclusion, size/stability gates
│   │   └── pairing.py          # gaps_valid predicate + pair enumeration
│   ├── stability/              # SQS + optional MLP stability triage
│   │   ├── __init__.py
│   │   ├── sqs.py              # random/icet SQS and endpoint artifacts
│   │   ├── mlp.py              # backend protocol + MACE implementation [extra: mlp]
│   │   ├── relax.py            # resumable relaxation records and quality control
│   │   ├── thermodynamics.py   # compatible-energy mixing enthalpies and audit summary
│   │   ├── phonon.py           # Phonopy displacements, MACE forces, bands/DOS and QC
│   │   ├── competing.py        # MP competing structures + same-MLIP convex hulls
│   │   └── recommendation.py   # auditable Stage 11 evidence aggregation and ranking
│   ├── defects/                # future vacancy ranking; execution design TBD
│   │   ├── __init__.py
│   │   ├── elemental.py        # elemental reference builder
│   │   ├── vacancy.py          # SimpleVacancyWorkChain driver
│   │   └── ranking.py          # cation/anion split, formation-energy ranking
│   ├── cli/                    # click entry points
│   │   ├── __init__.py
│   │   ├── app.py              # main `ss-screen` group
│   │   ├── condense_cmd.py     # ss-screen condense
│   │   ├── pair_cmd.py         # ss-screen pair-screen
│   │   └── defects_cmd.py      # future ss-screen rank-defects
│   ├── gui/                    # optional PySide6 desktop workbench
│   │   ├── __init__.py
│   │   ├── app.py              # GUI shell and command pages
│   │   ├── launcher.py         # `ss-screen-gui` entry point
│   │   └── metadata.py         # workflow presentation metadata
│   └── _schema.py              # dataclass schemas for result CSVs
├── tests/
│   ├── test_envmatch.py
│   ├── test_pairing.py
│   ├── test_grouping.py
│   ├── test_condense.py
│   └── data/                   # tiny fixtures (real robocrys JSONs)
├── docs/
│   ├── PROJECT_PLAN.md         # this file
│   ├── review_pair_screening.md   # technical review #1
│   ├── review_gap_contract.md     # technical review #2
│   └── review_defects.md          # technical review #3
└── examples/
    └── (ported notebooks / scripts)
```

## 4. Dependency strategy

**Core** (pair-screening works standalone):
`pymatgen`, `pandas`, `numpy`, `monty`, `click`, `tqdm`. The core CLI consumes
pre-built data artifacts and pre-condensed structure JSONs without requiring
heavy workflow dependencies.

**Extras**:
- `mp`: official Materials Project live API backend (`mp-api` 0.46.x). The offline MP
  backend uses a separately installed/local `mp_offline` package and explicit
  SQLite snapshot; Stage 10 records the snapshot SHA-256 and scope warning.
- `wbm`: WBM extxyz loading (`ase`).
- `condense`: robocrys condensation (`robocrys`, compatible `matminer` /
  `setuptools` pins).
- `sqs`: optimized SQS generation (`ase`, `icet`).
- `gui`: optional PySide6 desktop workbench. It remains a control layer over the
  real Click CLI and must not replace scientific command implementations.
- `mlp`: MACE relaxation (`mace-torch`, a validated Torch build, `ase`) with
  NumPy/ASE/matscipy compatibility pins matching the local MACE-MPA-0 runtime.
- `phonon`: Phonopy 4.x finite displacements, SeeK-path high-symmetry paths,
  HDF5 force constants, and matplotlib band/DOS figures. Install with `mlp` for
  direct MACE energy/force evaluation.

High-fidelity band-gap execution is intentionally not a package extra. Users
calculate with VASP, ABACUS, AiiDA, or another platform and return the versioned
task/result contract. Any future defect execution extra will be designed and
validated independently rather than reintroducing a band-calculation runtime.

Install: `pip install ss-screen` (core) or install targeted extras such as
`pip install "ss-screen[mp,condense,sqs,mlp]"`. For Ubuntu development with the
CLI, common workflow extras, and GUI, use `pip install -r requirements.txt`.

## 5. Migration milestones (long-running roadmap)

The work is sequenced so each milestone is independently useful and testable.

### Milestone 0 — Scaffolding (small)
- `pyproject.toml`, package skeleton, `pre-commit`, ruff/black config.
- `git init`, `.gitignore` (exclude the multi-GB datasets & AiiDA `.aiida` files).
- README stub. **No** research data committed (only tiny test fixtures).

### Milestone 1 — Structure grouping core (Part 1, the scientific heart)  ← FIRST DELIVERABLE
- Port `envmatch.py` into `src/ssscreen/pair/envmatch.py`; fix `__getitem__` typo;
  add docstrings & type hints; **keep the `re` sanitization of `site['element']`**
  (the ternary inline copy drops it — see `docs/algorithm_structure_grouping.md` §6).
- Extract `group_by_composition_template(df, nelems)` from the binary/ternary
  notebooks into `pair/grouping.py` (de-duplicates the divergent copies).
- Move valence / element-exclusion / size filters into `pair/filters.py`.
- Centralize all thresholds & element lists in `config.py`.
- Unit tests with tiny real robocrys fixtures (sample a few `mp-condense/condensed/*.json`).
- CLI: `ss-screen group --df-mp ... --condensed-dirs ... --output groups.json`
  (outputs `StructureGroup`s only — **no pair enumeration here**).
- Spec reference: `docs/algorithm_structure_grouping.md`.

### Milestone 1b — Gap backfill + pair enumeration (Part 2, logical layer)
- Extract `gaps_valid(gaps, thresholds)` and `enumerate_pairs(...)` from
  `pairing_mbj_*.ipynb` into `pair/pairing.py` with the magic numbers becoming
  `Thresholds` dataclass params.
- Gap-source **must be a configurable input** (mBJ / VASP-HSE06 / ABACUS-HSE06), no hardcoded CSV name.
- Add coverage-rate monitoring + optional PBE fallback (current code silently drops
  members without a high-precision gap — see `docs/algorithm_gap_backfill_pairing.md` §4.3).
- `direct` stays an info column, not a hard filter (user-confirmed).
- CLI: `ss-screen pair --groups ... --gaps ... --output pairs.csv`.
- Spec reference: `docs/algorithm_gap_backfill_pairing.md`.

### Milestone 2 — Data layer
- Port `datacollect.py` → `data/mp.py`, `data/wbm.py`.
- The MP loader uses explicit API/offline backends, excludes deprecated records,
  projects only Stage 1 fields from `mp_offline`, and writes a JSON provenance
  sidecar containing query bounds, database SHA-256/build metadata, and package
  versions. **Implemented.**
- Port `mp-condense/condense.py` + `condense_one.py` → `data/condense.py`;
  CLI: `ss-screen condense` (single file) and a batch mode.
- Port the entry-to-summary matcher from `convert_to_extxyz.py` into a tested
  `match_entries_to_summary(entries, df, tol)` helper in `data/io.py`.
- Externalize MP API key to `MP_API_KEY` env var.

### Milestone 3 — External high-fidelity band-gap contract
- Keep VASP, ABACUS, AiiDA, and other expensive execution outside the package.
- Export deterministic task IDs, structure hashes, JSON/CIF/POSCAR structures,
  a result template, and a method-metadata template.
- Collect batch VASP results from deterministic `task_id/vasprun.xml[.gz]`
  directories, preserving success, not-converged, failed, and missing states.
- Validate returned task/material/method/structure/settings identity, numerical
  values, status, duplicates, and coverage before pair generation.
- Preserve legacy seven-column result ingestion when strict task tables are not
  available. **Implemented.**

MLP phase stability remains independently implemented as Stage 10 under
`stability/competing.py`; its same-energy-reference rules are not changed by
the external band-gap decision. Competing structures can be discovered from
either the live MP API or an explicit `mp_offline` summary snapshot; the latter
does not claim online thermo-type filtering. **Implemented.**

Stage 11 is independently implemented as the top-level `ss-screen recommend`
command under `stability/recommendation.py`. It joins the final pair table,
normalized high-fidelity gap results, mixing enthalpy, phonon summary, and
competing-phase hull results per `pair_index + structure_id`. It preserves
missing and incompatible evidence, checks the shared MLP model hash, assigns
L2--L6 evidence levels, and classifies candidates as `promising`, `uncertain`,
or `low-priority` without an opaque aggregate score. Optional defect evidence
can raise the level to L6; missing defects are only required when explicitly
configured. **Implemented.**

### Milestone 4 — Defect ranking (future execution design)
- Elemental-reference builder; `SimpleVacancyWorkChain` driver;
  cation/anion-aware ranking; CSV schema.
- CLI: `ss-screen rank-defects`.

### Milestone 5 — Documentation & technical reviews
- Three technical review docs (pair-screening / external gap contract / defects) — see
  `docs/review_*.md` — covering algorithm derivation, parameter choices,
  references to source notebooks, and limitations.
- User-guide docs; example notebook ports.
- A CPU-only Stage 1--11 artifact-chain fixture under `tests/data/e2e/` runs the
  real lightweight CLI stages and deterministic substitutes for external or
  expensive engines. It verifies reproducible cross-stage schemas without
  network, credentials, GPU, MLP/phonon execution, DFT, or AiiDA. **Implemented.**

## 6. Conventions
- Python ≥3.10, `src/` layout.
- Type hints everywhere; `ruff` + `black`; tests via `pytest`.
- All file paths configurable (CLI args / config file), no hardcoded relative paths.
- No secrets in repo; MP key via env var.
- Numerical thresholds are named parameters, never inline literals.
- Original notebooks remain unchanged in `/home/bonan/work/HC/<orig>/`.
  Curated notebook and source-code snapshots may also be tracked under
  `references/` with provenance and secret/license checks; large datasets and
  calculation artifacts remain external. The package code is the canonical,
  tested implementation.

## 7. Web platform extension

The approved Web direction is a multi-user research operations platform built
around the existing scientific core. Its development baseline is
[`docs/web_platform_development_guide.md`](web_platform_development_guide.md).

The fixed dependency direction is `ssscreen_web -> ssscreen`: the Web API,
database, queue, authentication, and UI may call the tested Python package, but
`src/ssscreen/` must remain independent of FastAPI, PostgreSQL, Redis/Celery,
and frontend dependencies. PostgreSQL stores control-plane metadata; immutable
scientific artifacts remain in a configurable repository-external NFS or object
store with checksums and provenance.

Development is staged as follows:

1. Freeze and version the current scientific baseline and restore green CI.
2. Add the Project/Run/Task/Attempt/Artifact/Event control layer.
3. Deliver a Stage 1--5 Web MVP, including external gap task download, result
   upload, validation, retries, and candidate inspection.
4. Add Stage 6--11 CPU/GPU workers without weakening model/energy provenance.
5. Add production OIDC, operations, and optional Slurm/AiiDA adapters.

The Phase 1 control-plane vertical slice is implemented under `web/`: an independent
FastAPI/SQLAlchemy/Alembic/Celery backend, PostgreSQL schema, external filesystem
ArtifactStore, SSE, generated OpenAPI client, React workbench, Compose baseline, and
deterministic demo task. Phase 2 now has its first scientific vertical slice: the
`stage-1-mp-offline-v1` Dataset StageRunner calls the core MP offline loader on a
server-configured read-only snapshot. `stage-1-wbm-upload-v1` streams user files into an
external quarantine, rechecks integrity, applies the strict core WBM schema, and publishes
raw inputs, normalized data and sanitized provenance. Both register auditable Datasets
through the CPU queue. Stage 1a freezes a selected Dataset Artifact identity and calls the
core composition screen to publish candidate CSV/provenance without creating a second Dataset;
the Run workbench exposes frozen parameters and a bounded, authorized preview while preserving
the immutable CSV as the authoritative output. Stage 2 now freezes both the normalized Dataset and
composition Artifact identities, runs core Robocrys condensation in checkpointed batches, records
per-material failures, resumes failed Attempts from complete JSON checkpoints, and publishes an
archive/index/failure/manifest/provenance contract with live progress in the Run workbench.
The demo JSON is not a scientific result. Online-MP inputs, Stage 3--11 Web StageRunners, production
OIDC, GPU/HPC adapters, and production operations remain future work.
