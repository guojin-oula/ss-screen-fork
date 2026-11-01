# Upstream migration completeness review

**Date:** 2026-07-19
**Scope:** `ss-screen` versus the read-only upstream sources declared in
`AGENTS.md`
**Review type:** Static source/notebook audit plus non-mutating package and
artifact verification

## Executive verdict

No: the repository has **not** yet included all upstream information, routines,
functionality, or workflows.

The implemented portion is strongest where it matters most for the original
screening algorithm. Materials Project normalization, robocrys condensation,
composition/environment grouping, external gap handoff, gap feedback, pair
enumeration, method comparison, and initial SQS generation are real package
APIs with CLI commands and tests. The current binary path exactly reproduces the
canonical 52-pair result.

However, the full research workflow is still incomplete:

- WBM **consumption** is implemented, but raw WBM entry/summary reconciliation
  and extxyz construction are not.
- The package exports and ingests high-level band-gap artifacts, but none of the
  upstream VASP/ABACUS AiiDA launch, rerun, monitor, band-analysis, or plotting
  workflows are implemented.
- Phase-diagram stability, MACE antiperovskite relaxation, most prototype-study
  routines, MLP relaxation/mixing/phonon stages, and final recommendation logic
  are absent.
- The complete vacancy-defect workflow—elemental references, bulk/supercell
  relaxation, vacancy generation, `SimpleVacancyWorkChain`, chemical
  potentials, and cation-vacancy ranking—is absent.
- Documentation is complete for the grouping/pairing scientific core but not
  for downstream DFT, stability, prototypes, or defects.

The repository should therefore be described as a **well-tested core screening
package with an external calculation contract and an early SQS stage**, not yet
as a complete migration of the whole upstream workspace.

## Review criteria

A capability counts as migrated only when its intended behavior is represented
by one or more of the following inside `ss-screen`:

1. a reusable Python API;
2. a CLI/file contract;
3. tests or a justified smoke-test boundary;
4. documentation sufficient to reproduce or safely replace the notebook flow.

Merely listing an optional dependency, mentioning a future stage, retaining a
read-only notebook, or accepting the final CSV does not count as migrating the
workflow that created that CSV.

Large datasets, `.aiida` archives, tarballs, calculated results, and the
145k-file condensed/structure archives are intentionally not expected to be
copied into the package. Their schemas, provenance assumptions, and reusable
transformation routines are in scope.

## Coverage summary

| Upstream source | Intended capability | Coverage in `ss-screen` | Assessment |
|---|---|---|---|
| `../pair-screening/` | MP/WBM loading, valence filtering, composition templates, envmatch, group artifacts, gap backfill, pair enumeration | `data/mp.py`, `data/wbm.py`, `pair/*`, `data/io.py`, staged CLI, tests, two algorithm docs | **High but not complete** |
| `../mp-condense/` | Single/batch robocrys condensation, resumability, combined archive | Robust single/batch condensation, manifests, indexes, validation; no worker pool or combined-JSON command | **High / partial** |
| `../wbm-dataset/` | Raw five-step entry loading, dirty-row matching, validation, extxyz creation | Loads an already-built extxyz into normalized DataFrame | **Partial** |
| `../screen-mbj/` | PBE, VASP-HSE06, true mBJ, ABACUS-HSE06 launch/monitor/analyze flows | Candidate export, external-result schema, feedback/comparison only | **Calculation contract only** |
| `../screen-promising/` | MP structure acquisition, PBE/HSE band workflows and plots | No launcher or analysis implementation | **Missing** |
| `../screen-antiperovskite/` | ASE prototype enumeration, MACE relaxation, mBJ/HSE launch, MP-compatible hull analysis | No equivalent modules; generic MP loader/SQS do not cover it | **Missing** |
| `../rocksalt/` | Prototype setup, HSE/mBJ/SOC studies, PbSe-Te SQS and HSE analysis | Generic SQS structure generation covers part of `sqs.ipynb` | **Partial** |
| `../zincblend/` | Prototype setup and HSE/mBJ/SOC comparisons | No equivalent workflow | **Missing** |
| `../Chalcopyrite /` | PBE/HSE/mBJ band workflow for chalcopyrite | No equivalent workflow | **Missing** |
| `../simple-defects/` | Elemental references, manual/workchain vacancies, SQS vacancies, chemical potentials, ranking | `dft` dependencies are declared, but no `defects/` code or commands exist | **Missing** |
| `../old-screen-202411/` | Historical grouping/pairing baseline with older thresholds/direct filtering | Newer canonical behavior supersedes most logic; historical direct-filter mode and combined-JSON flow are unavailable | **Superseded / partial** |
| `../hc-mbj-antiperovskite.aiida`, tarballs, large data | Historical process/data archives | Correctly excluded from the package | **Intentionally external** |

## Findings ordered by impact

### 1. The downstream half of the declared scientific mission is absent

`docs/PROJECT_PLAN.md` defines a full pipeline ending in high-fidelity band
verification and vacancy ranking. The source tree has no
`src/ssscreen/workflow/` or `src/ssscreen/defects/` package and no
`launch-bands` or `rank-defects` command. The `dft` extra in `pyproject.toml`
declares libraries but provides no functionality.

Missing upstream behavior includes:

- VASP PBE, HSE06, and mBJ builder configuration;
- optional SOC/non-collinear variants;
- ABACUS HSE06 with PBE cell relaxation;
- `GroupPathX` provenance/group layouts;
- throttled `GroupLauncher` submission;
- failed/excepted work reruns and restart builders;
- pymatgen band-gap/directness extraction and plot/PDF generation;
- elemental-reference and bulk/supercell relaxations;
- vacancy creation and `SimpleVacancyWorkChain` configuration;
- chemical-potential analysis with `CompetingPhasesAnalyzer`;
- cation-vacancy formation-energy ranking and CSV output.

The newer roadmap deliberately keeps expensive band calculations external.
That is a defensible architecture, but the result is **replacement by a file
contract**, not migration of the upstream execution and analysis workflows.
The documentation and status language should make that boundary explicit.

### 2. The real ternary legacy artifact cannot be loaded

The canonical ternary group JSON stores `Compositions` with a capital C, as
documented in `docs/algorithm_gap_backfill_pairing.md`. `load_group_df()` in
`src/ssscreen/data/io.py` only reads `r["compositions"]`.

Fresh reproduction:

```text
ss-screen pair --groups ../pair-screening/ternary-group-df.json ...
KeyError: 'compositions'
```

This is not a scientific algorithm failure. A diagnostic temporary copy with
only `Compositions` renamed to `compositions` produced 299 rows exactly equal
to `../pair-screening/mbj_result_ternary_20250426.csv`. The missing behavior is
legacy field-alias normalization and a real ternary fixture test.

Impact: the package can generate and consume its own lowercase ternary
artifacts, but it cannot directly reproduce the historical ternary workflow
from the declared upstream inputs.

### 3. Raw WBM preparation has not been migrated

`src/ssscreen/data/wbm.py` reads a completed extxyz archive and optionally joins
summary metadata by row position. The upstream `datacollect.py` and
`convert_to_extxyz.py` perform additional load-bearing work:

- load `step_1.json.bz2` through `step_5.json.bz2`;
- attach source-step provenance;
- split at the known clean/dirty boundary;
- uniquely reconcile dirty entries by reduced formula, site count, and volume
  tolerance;
- validate every matched row against the structure;
- transfer WBM energies, formation/hull energies, gaps, volume, site counts,
  step, and index to extxyz metadata;
- write the canonical extxyz archive.

The `PROJECT_PLAN.md` requirement for a tested
`match_entries_to_summary(entries, df, tol)` helper is still unmet. The current
loader is useful only after the upstream converter has already run.

### 4. Optional PBE fallback is promised but absent

The project plan requires coverage monitoring plus optional PBE fallback.
Coverage monitoring exists, but `attach_gaps_and_compress()` always removes
members without an external high-level result. `gap-compare` can compare an
explicitly supplied PBE result file; it does not backfill missing IDs from the
PBE values already stored on `StructureGroup.band_gaps`.

This preserves the notebook's silent-drop behavior with better reporting, but
does not complete the planned mitigation for low high-level-gap coverage.

### 5. Binary and ternary gate policies are not fully reproducible

The package centralizes thresholds, which is an improvement, but uses the broad
binary excluded-element set for every `nelems` value. CLI
`--excluded-elements` options only add elements; they cannot replace or remove
defaults. The upstream ternary screen excluded only U/Th/Po/Tl/Hg and used a
different group-level PBE-gap-diversity rule.

Consequently, one API covers both systems, but users cannot select the exact
canonical ternary gate policy through configuration alone.

### 6. Stability/prototype migration is only at the SQS-input stage

`src/ssscreen/stability/sqs.py` provides a useful generic one-site alloy
generator with random and icet backends, manifests, multiple target fractions,
and tests. It partially replaces the rocksalt and MCT SQS notebooks.

Still missing:

- optimal non-diagonal supercell selection and fixed-size MCT construction;
- SQS correlation/quality metrics;
- inequivalent vacancy-site sampling in SQS structures;
- MACE relaxation and energy/force/stress results;
- mixing enthalpy and endmember consistency checks;
- phonon/dynamic-stability adapters;
- Materials Project competing-phase reconstruction;
- recommendation/ranking reports;
- HSE band calculations on generated SQS structures.

The antiperovskite notebook already contains an ASE Ca3SnO prototype, a 4x4x4
A/B/C substitution grid, symmetry-constrained MACE/FIRE cell relaxation, and
per-composition extxyz output. None is represented in the package.

### 7. Information/documentation coverage is downstream-incomplete

`docs/algorithm_structure_grouping.md` and
`docs/algorithm_gap_backfill_pairing.md` are strong, source-indexed technical
records. Missing planned information includes:

- a DFT workflow review covering method-specific builders and provenance;
- a defect review covering elemental references, chemical-potential assumptions,
  charge/state limitations, and ranking logic;
- prototype-study rationale and reusable structure-building recipes;
- the top-level user guide and complete artifact contract;
- an explicit statement that high-level execution is external rather than
  migrated;
- end-to-end reproducibility fixtures for both binary and ternary paths.

README currently states a small *direct*-gap scientific target while the
implemented/current canonical pair criterion keeps directness as information
only. The algorithm document explains this nuance, but README does not.

### 8. Lower-priority data/serialization gaps

- `combined_condensed.py` has no CLI/API equivalent. Per-file archives plus
  indexes are better for concurrency, but a compatibility bundle/export command
  is absent.
- Upstream condensation used joblib parallelism; the package runs serially and
  exposes no worker count.
- `StructureGroup.to_dict()` drops `group_repr`. This matches the binary artifact
  but loses a field present in the ternary artifact and prevents a normal
  dump/load round trip from retaining the fingerprint used by
  `filter_groups_by_gaps()`.
- `screen-mbj/kpt-example.ipynb` contains k-path label lookup/segment reduction
  helpers with no package equivalent.
- Historical `old-screen-202411` used a hard direct-gap gate and different
  thresholds. It is reasonable to mark this superseded, but exact historical
  reproduction is not exposed as an optional policy.

## Capabilities that are migrated well

The incomplete verdict should not obscure the quality of the implemented core:

- `envmatch` is faithfully ported with oxidation-state element sanitization and
  fixes the upstream `__getitem___` typo.
- Binary/ternary composition templates are unified behind one typed API.
- Valence, element, hull, band-gap, X-diversity, and atom-count gates are named
  and mostly configurable.
- Condensation adds atomic writes, resumability, checksums, manifests, indexes,
  validation, and explicit failures.
- MP loading supports offline and live backends without embedding credentials.
- Structure matching reports missing/invalid descriptions instead of silently
  losing them.
- Gap export/validation/feedback introduces stable external contracts and
  coverage reporting.
- Method comparison reports common/method-only pairs, gap shifts, directness
  changes, and coverage differences.
- Pair enumeration removes the upstream self-pairing defect.
- Binary canonical reproduction is exact, and ternary algorithm reproduction is
  exact after the isolated legacy field-name normalization.

## Security and provenance observations

At least one read-only upstream notebook still embeds a live-looking Materials
Project credential. Its value is intentionally not reproduced here. The
package's live MP path correctly relies on standard `mp-api` configuration /
environment discovery and does not embed that credential.

Recommended operational action outside this review: revoke/rotate the exposed
upstream credential and scrub it from any repository history that may be
shared. The read-only boundary was respected; no upstream file was changed.

## Verification evidence

Run on 2026-07-19 without executing notebooks, AiiDA, DFT, GPU, or MPI jobs:

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | Exit 0; 89 tests completed, with only spglib deprecation warnings |
| `.venv/bin/ruff check src tests` | Exit 0; all checks passed |
| Binary historical CLI reproduction | 52 rows; exact dataframe equality with canonical CSV |
| Ternary historical CLI reproduction | Failed at loader with `KeyError: 'compositions'` |
| Ternary diagnostic with temporary one-key normalization | 299 rows; exact dataframe equality with canonical CSV |
| Black check | Inconclusive: three variants reported 33 files unchanged but hung until timeout (exit 124) |

The passing suite establishes that implemented and tested behavior is stable;
it does not establish upstream completeness. In particular, absent DFT/defect
modules cannot be validated by the current tests.

## Recommended completion order

1. **Repair compatibility and core contract gaps**
   - accept `Compositions` as a legacy alias and add a real ternary reproduction
     fixture;
   - implement optional PBE fallback with provenance per member;
   - allow replacement/per-system exclusion and group-gap policies;
   - decide whether `group_repr` is part of the durable schema.

2. **Complete WBM data provenance**
   - extract/test `match_entries_to_summary` with configurable tolerance;
   - add raw WBM steps-to-extxyz/DataFrame construction and validation;
   - preserve source-step and reconciliation provenance.

3. **Make the external-calculation boundary explicit**
   - either implement backend adapters for VASP/ABACUS/AiiDA launch and analysis,
     or formally declare those workflows out of package scope;
   - if external, document required calculator provenance and add converters from
     AiiDA workgroups to the stable gap-result schema.

4. **Port stability/prototype routines**
   - ASE prototype builders, MACE relaxation adapter, energy/result schemas,
     phase-diagram checks, and SQS quality metrics.

5. **Port defects as an optional DFT layer**
   - elemental references, generic vacancy driver, supercell controls,
     chemical-potential model, cation/anion classification, ranking schema, and
     smoke tests with mocked AiiDA boundaries.

6. **Finish documentation and reproducibility**
   - DFT and defect reviews, user guide/artifact table, binary and ternary
     end-to-end fixtures, and a top-level workflow/orchestration command only
     after individual contracts are stable.

## Completion criterion for a future re-audit

The migration can be called complete only when every non-historical matrix row
above is either:

- implemented with API/CLI, tests, and documentation; or
- explicitly declared out of scope with a documented replacement interface and
  provenance contract.

Under that criterion, the current repository is not complete.
