# CLI Long-Term Screening Roadmap

## Objective

Build `ss-screen` into a staged command-line screening pipeline that can reproduce notebook-like screening results while keeping expensive electronic-structure calculations outside the CLI. The CLI should own data preparation, composition screening, structure-description archive generation, structure matching, candidate export for external high-level band-gap calculations, band-gap result ingestion, final pair generation, and preliminary machine-learning-potential stability triage.

This plan is based on the current package mission and read-only boundary in `AGENTS.md:6`, `AGENTS.md:34`, and `AGENTS.md:58`; the existing package layout and CLI roadmap in `docs/PROJECT_PLAN.md:60`, `docs/PROJECT_PLAN.md:70`, `docs/PROJECT_PLAN.md:93`, and `docs/PROJECT_PLAN.md:129`; the current CLI implementation in `src/ssscreen/cli/app.py:1`, `src/ssscreen/cli/app.py:81`, `src/ssscreen/cli/app.py:116`, and `src/ssscreen/cli/app.py:228`; the composition/structure algorithm split in `docs/algorithm_structure_grouping.md:50`, `docs/algorithm_structure_grouping.md:59`, and `docs/algorithm_structure_grouping.md:76`; and the explicit high-level band-gap handoff and feedback loop in `docs/algorithm_gap_backfill_pairing.md:31`, `docs/algorithm_gap_backfill_pairing.md:41`, `docs/algorithm_gap_backfill_pairing.md:102`, and `docs/algorithm_gap_backfill_pairing.md:152`.

The key design decision is that the CLI does not run high-level band-gap calculations. Instead, it exports candidate structures and metadata, then later ingests externally computed band-gap tables. This preserves the ability to compare PBE, mBJ, VASP-HSE06, ABACUS-HSE06, and future methods without coupling the core screening CLI to AiiDA or one DFT stack, consistent with `docs/algorithm_gap_backfill_pairing.md:58`, `docs/algorithm_gap_backfill_pairing.md:69`, and `docs/algorithm_gap_backfill_pairing.md:249`.

## Implementation Plan

- [x] **Stage 0 — Stabilize the CLI platform before expanding the science workflow.** Confirm the canonical command names are `valence-filter`, `condense`, `group`, and `pair`, matching `src/ssscreen/cli/app.py:5` through `src/ssscreen/cli/app.py:8`. Split `src/ssscreen/cli/app.py` into smaller command modules only when the file becomes hard to navigate, but keep one top-level `ss-screen` entry point. Add a minimal CI path that runs core CLI tests without optional scientific backends.

  Status on 2026-07-12: completed the first CI/dependency cleanup slice. The repository now has a core GitHub Actions workflow, development tools live in the `uv` dependency group instead of a package extra, and the configuration is guarded by regression tests so default CI does not pull optional DFT dependencies.

- [x] **Stage 1 — Build dataset and composition-screening commands.** Add CLI commands that create the DataFrame inputs currently assumed by `ss-screen group`: one MP-oriented loader and one WBM-oriented loader, following the planned `data/mp.py` and `data/wbm.py` modules in `docs/PROJECT_PLAN.md:70` through `docs/PROJECT_PLAN.md:75`. This stage should produce a normalized dataset table with material ID, composition, reduced composition, element count, PBE/database band gap, hull energy where available, primitive structure, and source metadata. The command should externalize MP credentials through `MP_API_KEY`, honoring `AGENTS.md:60` through `AGENTS.md:63`, and should provide a composition-only pre-screen report before any structure matching.

  Status on 2026-07-12: started. Added `src/ssscreen/data/mp.py` and `ss-screen dataset mp` as an offline-first loader using `mp_offline` by default, so the pipeline can run in network-isolated environments. A live `--backend api` mode is still available and uses `MPRester()` without an explicit API key, allowing standard pymatgen/mp-api config such as `~/.pmgrc.yaml` to provide credentials. The normalized MP table includes composition, reduced composition, element count, database band gap, hull energy, structure, primitive structure, and source metadata. WBM loading remains to be implemented before Stage 1 is complete.

  Status on 2026-07-16: completed the first WBM loader as `ss-screen dataset wbm --xyz ...`. It reads WBM extxyz structures generated from the reference data flow, preserves available `WBM_*` metadata, and writes the same normalized screening schema as the MP loader.

- [x] **Stage 1a — Separate composition screening from structure matching.** Add a dedicated composition-screening command or mode that groups candidates by composition template before requiring condensed structure descriptions. This command should expose the composition-template logic described in `docs/algorithm_structure_grouping.md:59` through `docs/algorithm_structure_grouping.md:74`, including binary and ternary X-site enumeration, minimum number of different X elements, element-count selection, PBE band-gap thresholds, hull-energy thresholds, optional valence filtering, and exclusion lists. Its output should be a machine-readable composition-candidate table that can be inspected independently from robocrys.

  Status on 2026-07-12: completed the first command surface. `ss-screen composition-screen` writes a CSV candidate table plus an optional JSON summary from normalized pickle DataFrames, without requiring condensed robocrys descriptions.

- [x] **Stage 2 — Generate structure-description JSON archives.** Extend `ss-screen condense` from single-file/directory operation into a robust archive-generation stage. It should read structure sources from Stage 1 outputs or file directories, generate `{material_id}.json` robocrys condensed descriptions, and optionally produce an archive manifest that records source path, material ID, formula, success/failure state, error reason, and checksum. This stage should preserve the robocrys fields required by `docs/algorithm_structure_grouping.md:110` through `docs/algorithm_structure_grouping.md:123`, and should explicitly track failures and missing descriptions as required by `docs/algorithm_structure_grouping.md:145` through `docs/algorithm_structure_grouping.md:151`.

  Status on 2026-07-12: completed the first archive-generation slice. `ss-screen condense` now supports `--df` inputs from Stage 1 normalized DataFrames, writes per-material JSON files atomically, skips existing files by default, and can emit JSONL manifest plus CSV index sidecars. The individual-file archive remains intentional for concurrent workers; metadata sidecars make large directories searchable without changing the primary storage layout.

  Status on 2026-07-16: `condense_paths` now records input load failures in manifest/index sidecars instead of silently dropping unreadable files.

- [x] **Stage 2a — Make structure-description archives reusable and cacheable.** Add archive-management commands for validating, indexing, merging, and summarizing condensed JSON directories. The goal is to make the condensed descriptions a reusable artifact, not a hidden temporary directory. This directly supports the data-flow shown in `docs/algorithm_structure_grouping.md:23` through `docs/algorithm_structure_grouping.md:45`, where `condensed/*.json` is the precomputed input to structure matching.

  Status on 2026-07-12: completed the first reusable archive command surface with `ss-screen condense-index` and `ss-screen condense-validate`. Future extensions can add merge/summarize commands or optional Parquet indexes if the core dependency policy changes.

- [x] **Stage 3 — Structure matching and group generation.** Refine `ss-screen group` into the explicit structure-matching stage: consume the composition-screened candidates plus condensed JSON archive(s), run envmatch, enforce X-element diversity, and write `StructureGroup` JSON. This stage should preserve the two-layer order required by `docs/algorithm_structure_grouping.md:50` through `docs/algorithm_structure_grouping.md:104`; write output fields matching `docs/algorithm_structure_grouping.md:155` through `docs/algorithm_structure_grouping.md:174`; and report missing condensed descriptions, ambiguous X-site inference, group counts, member counts, and filter attrition.

  Status on 2026-07-13: completed the first explicit staged command surface as `ss-screen structure-match`. It consumes the Stage 1a composition-candidate CSV plus one or more Stage 2 condensed JSON archive directories, runs envmatch, enforces X-element diversity, writes `StructureGroup` JSON, and can emit a JSON summary with candidate/template counts, missing descriptions, raw group counts, final group counts, and grouped member counts. The older `ss-screen group` command remains available as a legacy all-in-one path.

  Status on 2026-07-16: invalid or malformed condensed descriptions are now reported in the summary and skipped rather than crashing the whole structure-matching run.

- [x] **Stage 3a — Export external high-level band-gap calculation inputs.** Add a command that takes structure groups and the original structure table, extracts the union of group member material IDs, applies the atom-count and cost-control gates, and writes candidate structures plus metadata for external band-gap calculations. This corresponds to the notebook bridge described in `docs/algorithm_structure_grouping.md:201` through `docs/algorithm_structure_grouping.md:213` and the Stage 2 input described in `docs/algorithm_gap_backfill_pairing.md:52` through `docs/algorithm_gap_backfill_pairing.md:56`. The output should include enough metadata to compare multiple theory levels later: method label, source group ID, material ID, formula, composition, structure, atom count, and initial PBE/database gap.

  Status on 2026-07-13: completed the first export command as `ss-screen gap-export`. It writes a unique material-level candidate CSV and can optionally dump per-material structure JSON files for external workflows. The core CLI still does not launch DFT.

  Status on 2026-07-16: `gap-export` now writes the same primitive/calculation structure used for atom-count gating, and the CLI applies a default `--max-natoms 30` cost-control gate.

  Status on 2026-07-31: the external contract now assigns schema-versioned deterministic task IDs and structure hashes, exports JSON/CIF/POSCAR structures, and can write result and method-metadata templates. No DFT launcher or AiiDA runtime is part of the package.

- [x] **Stage 4 — Treat band-gap calculation as an external contract.** Define and document a stable external gap-result schema rather than implementing DFT launchers in the core CLI. The schema should accept at minimum material ID, formula, method name, direct/indirect flag, transition label when available, band gap, calculation status, and optional provenance fields. This keeps high-level theory outside the CLI while supporting multiple gap sources, matching the method-configurability documented in `docs/algorithm_gap_backfill_pairing.md:31` through `docs/algorithm_gap_backfill_pairing.md:37` and the observed method differences in `docs/algorithm_gap_backfill_pairing.md:58` through `docs/algorithm_gap_backfill_pairing.md:74`.

  Status on 2026-07-13: completed the first schema contract with `ss-screen gap-validate`. Required columns are `material_id`, `formula`, `method`, `band_gap`, `is_direct`, `transition`, and `status`; extra provenance columns are preserved by pandas for downstream use.

  Status on 2026-07-16: gap-result validation accepts CSV and JSON records and tolerates blank band gaps on failed/skipped rows so coverage reporting can proceed.

  Status on 2026-07-31: strict validation can cross-check returned rows against exported tasks and JSON method metadata, normalize nullable directness, reject unknown/mismatched/duplicate/invalid rows, and write normalized, rejected, and audit-report artifacts. Legacy seven-column records remain supported.

- [x] **Stage 5 — Ingest external band gaps and generate final composition pairs.** Extend `ss-screen pair` into a complete feedback stage: ingest one or more external gap CSV/JSON files, compute coverage statistics, attach gap results to group members without overwriting the original PBE `band_gaps`, and generate final candidate endmember pairs. This must preserve the `gaps_mbj` feedback contract in `docs/algorithm_gap_backfill_pairing.md:102` through `docs/algorithm_gap_backfill_pairing.md:127`, report the coverage problem described in `docs/algorithm_gap_backfill_pairing.md:129` through `docs/algorithm_gap_backfill_pairing.md:138`, and keep `direct` as an information column by default while allowing optional direct-gap filters later, as discussed in `docs/algorithm_gap_backfill_pairing.md:203` through `docs/algorithm_gap_backfill_pairing.md:216`.

  Status on 2026-07-13: completed the first feedback loop as `ss-screen pair --gap-results ...`. The command accepts one or more validated external gap-result CSVs, requires `--method` when multiple theory labels are present, filters to successful rows, reports material coverage/missing IDs in an optional JSON summary, and writes final pair CSVs without mutating the original PBE/database `band_gaps` in the group artifact. The legacy `--gaps` notebook CSV path remains available.

- [x] **Stage 5a — Support multiple theory levels and comparison reports.** Add CLI support for multiple gap sources in one run, allowing the user to compare candidate lists from PBE fallback, mBJ, VASP-HSE06, ABACUS-HSE06, or future methods. The command should generate method-specific pair outputs and a comparison report showing common pairs, method-only pairs, gap shifts, direct/indirect changes, and coverage differences. This is important because current notebook results used different high-level methods for binary and ternary cases, as recorded in `docs/algorithm_gap_backfill_pairing.md:249` through `docs/algorithm_gap_backfill_pairing.md:260`.

  Status on 2026-07-16: completed the first comparison command as `ss-screen gap-compare`. It reads one or more external gap-result CSV/JSON files, enumerates method-specific final pair CSVs using the same thresholds as `ss-screen pair`, and writes a JSON comparison report with method list, pair counts, coverage summaries, common pairs, all pairs, method-only pair IDs, gap-shift summaries, and direct/indirect changes.

- [x] **Stage 6 — Generate alloy/SQS structures for preliminary stability screening.** Add an optional stability command group that starts from final candidate pairs and generates representative alloy structures, including SQS structures for selected compositions. This stage should be a separate optional workflow because it moves beyond pair screening into alloy realization. It should record parent group, endmember IDs, target composition, generated structure path, supercell size, species mapping, random seed or enumeration metadata, and any limitations of the SQS generation.

  Status on 2026-07-13: completed the first artifact generator as `ss-screen stability sqs-generate`. It consumes final pair CSVs plus the normalized dataset pickle, infers single-site endmember substitutions, writes alloy structure JSON files for requested target fractions/supercells, and emits a JSONL manifest with pair IDs, endpoint IDs, composition, substitution mapping, target fraction, supercell, seed, structure path, status, generator, and limitations. The command supports a lightweight `random` backend and an `icet` backend using `generate_sqs_from_supercells` for optimized SQS generation while preserving the same manifest schema.

- [x] **Stage 7 — Relax candidate disordered phases with machine-learning potentials.** Add an optional MLP relaxation stage that consumes generated alloy structures, relaxes them with a configured machine-learning potential, and stores relaxed structures, energies, forces/stresses when available, and relaxation status. The command should be backend-pluggable so that the CLI can support MACE first, then other potentials later. This aligns with the planned `workflow/relax.py` and MACE-related direction in `docs/PROJECT_PLAN.md:82` through `docs/PROJECT_PLAN.md:87` without forcing the core screening CLI to depend on heavy DFT stacks.

  Status on 2026-07-30: implemented `ss-screen stability relax` with a backend protocol and an ASE-based MACE backend. It loads one configured checkpoint per process, supports full-cell or positions-only FIRE relaxation, optionally de-duplicates and relaxes both endmembers, and writes relaxed structures plus resumable JSON/JSONL records with energy, full forces, Cartesian stress, actual steps, convergence, hashes, runtime, and structural quality control. Non-converged and failed tasks remain explicit and are never marked usable for thermodynamics.

- [x] **Stage 8 — Estimate mixing enthalpies for disordered phases.** Add a command that combines relaxed alloy energies with relaxed endmember reference energies to estimate mixing enthalpies over selected compositions. It should output per-composition mixing enthalpy, reference energies used, uncertainty/provenance notes, and warnings when endmembers or alloy structures were not relaxed by the same MLP backend. This stage should be clearly labeled preliminary because MLP energetics are a screening signal, not a final thermodynamic conclusion.

  Status on 2026-07-30: completed `ss-screen stability mixing-enthalpy`. It preserves one output row per SQS, derives the realized alloy fraction from generated-structure metadata where possible, requires the SQS and both endmembers to share the same model/version/hash, dtype, and full relaxation settings, and records missing, unusable, ambiguous, or incompatible references as explicit failure statuses. The CSV reports eV/atom and meV/atom values plus provenance and warnings; the JSON summary reports aggregate status and coverage counts. These potential-energy differences are explicitly treated as preliminary 0 K screening signals.

- [x] **Stage 9 — Add phonon/dynamic-stability screening.** Add an optional phonon workflow that takes relaxed candidate structures, builds displaced structures or interfaces with an external phonon tool, evaluates phonon dispersion or imaginary-mode indicators, and records dynamic-stability summaries. The command should be designed as an adapter around external phonon calculators rather than hard-coding one engine, mirroring the overall design choice that expensive or backend-specific calculations remain swappable.

  Status on 2026-07-31: implemented resumable `phonon-export`, `phonon-forces`, `phonon-collect`, and end-to-end `phonon-run`. Phonopy 4.x generates finite displacements and force constants; the initial force backend is MACE and records energy, full forces, stress, hashes, and task fingerprints. Collection requires complete compatible forces, subtracts the reference-supercell force by default, writes HDF5/YAML/CSV/NPZ results and PNG/PDF band-DOS plots, and classifies significant imaginary modes on a configured gamma-centered mesh. No-imaginary-mode output remains a harmonic MLIP screening result rather than a finite-temperature stability claim.

- [x] **Stage 10 — Interface with Materials Project phase diagrams and competing phases.** Add a command that queries or consumes Materials Project phase-diagram data for the candidate chemical system, identifies competing phases, obtains or reconstructs their structures, relaxes them with the same MLP backend, and compares candidate alloy energies against the relaxed competing-phase set. This stage should maintain the project rule that MP credentials are externalized, and it should report exactly which phase-diagram entries were fetched, skipped, substituted, or failed.

  Status on 2026-07-31: implemented `competing-export`, `competing-relax`, `convex-hull`, and end-to-end `phase-diagram`. Online commands securely prompt for an API key on every invocation and restore the process environment afterward. MP supplies only versioned structures and selection provenance; candidate and competing entries are all relaxed with one compatible MLP energy reference. Missing, skipped, unconverged, or incompatible phases are explicit and make the default hull incomplete, with no fallback to MP DFT energies. Outputs include candidate margins relative to the competing-only hull, decomposition fractions, augmented-hull entries, strict status/QC summaries, and resumable manifests/results.

  Status on 2026-08-01: Stage 10 now also supports an explicit `mp_offline` SQLite snapshot. It enumerates every non-empty subsystem, queries indexed summary fields, preserves the database SHA-256 and snapshot scope through the final hull output, and never prompts for an API key. Offline summaries do not support online thermo-type filtering, so completeness is explicitly limited to the selected snapshot and automatic API-to-offline fallback remains forbidden.

- [x] **Stage 11 — Produce a recommendation report for further study.** Add a final decision-support command that combines pair-screening results, high-level gap evidence, gap-source coverage, direct/indirect flags, SQS/MLP relaxation results, mixing enthalpy, phonon indicators, and competing-phase comparisons into a ranked recommendation. The output should not claim final discovery; it should classify systems as promising, uncertain, or low-priority for further DFT/experimental study, with explicit reasons and missing-data flags.

  Status on 2026-08-03: implemented the top-level `ss-screen recommend` command. It joins Stage 5 and Stage 8--10 artifacts per pair/SQS structure, validates normalized endpoint gaps and the shared MLP model hash, preserves missing or incompatible records, and writes an auditable CSV, Markdown report, and optional JSON summary. Classification uses explicit configurable triage thresholds and L2--L6 evidence levels; deterministic ordering replaces an opaque aggregate score. Optional defect evidence is accepted through a small input contract and becomes mandatory only with `--require-defects`.

- [x] **Stage 12 — Documentation, examples, and reproducibility fixtures.** Write the Chinese user guide around the staged CLI pipeline, keep README as a concise English entry point, and add small fixtures for every stage so CI can exercise the pipeline without full datasets. The docs should include a stage-by-stage artifact table, explaining which artifacts are produced by the CLI and which are produced by external high-level theory or MLP/phonon backends.

  Status on 2026-08-03: completed the first reproducibility baseline. The Chinese Markdown/Word guide and concise README document the staged artifact map, while `tests/data/e2e/` and `tests/test_e2e_pipeline.py` exercise the Stage 1--11 artifact chain twice in independent temporary directories. Real lightweight CLI stages perform composition screening, environment matching, gap export/validation, pairing, random SQS generation, mixing enthalpy, and recommendation. Deterministic test records replace external high-fidelity gaps and expensive Stage 7/9/10 engines, so default CI requires no network, API key, GPU, model checkpoint, Phonopy run, DFT code, or AiiDA profile. Per-stage tests continue to own the scientific engine contracts.

## Verification Criteria

- The CLI has a documented staged command map from composition screening through final pair generation and optional MLP stability triage.
- Each stage has a declared input artifact, output artifact, schema owner, and minimal fixture test.
- The core screening path can be tested without AiiDA, DFT execution, phonon execution, or MLP dependencies.
- The external band-gap handoff is represented by a stable candidate-export artifact and a stable gap-result ingestion schema.
- The final pair-generation stage can reproduce notebook-like outputs when given equivalent group JSON and external gap tables.
- The optional stability stages are isolated from the core screening path and can be skipped in default CI.
- The Chinese user guide can explain the full workflow without relying on hidden notebooks or hard-coded paths.

## Potential Risks and Mitigations

1. **The CLI grows into too many loosely connected commands.**
   Mitigation: Organize commands by stage and shared artifact schemas. Keep each command responsible for one transformation, and add a top-level workflow summary command only after the individual stages are stable.

2. **External band-gap calculations break reproducibility because the CLI does not run them.**
   Mitigation: Define a strict gap-result schema, require method labels and provenance fields, and generate coverage reports before pair enumeration.

3. **Structure-description archives become stale or inconsistent with source structures.**
   Mitigation: Add archive manifests with checksums, source IDs, structure formulas, and generation timestamps; validate archives before structure matching.

4. **MLP stability signals are overinterpreted as final thermodynamic proof.**
   Mitigation: Label these outputs as preliminary screening; always include backend, model version, relaxation status, reference set, and missing-data warnings.

5. **Materials Project phase-diagram integration introduces network and credential instability.**
   Mitigation: Support both live MP queries and offline phase-diagram inputs; keep `MP_API_KEY` external; make live MP access optional and excluded from default CI.

6. **Optional dependencies make installation fragile.**
   Mitigation: Keep core screening dependencies minimal, isolate `condense`, MLP, phonon, and MP tools into extras, and keep high-fidelity band-gap execution external.

## Alternative Approaches

1. Keep the CLI small and only support composition, structure matching, and final pair generation. This is simpler and easier to stabilize, but it leaves stability triage and recommendation logic scattered in notebooks or ad hoc scripts.

2. Integrate AiiDA high-level band-gap calculations directly into the CLI. This was explicitly rejected: it would couple the package to profiles, licensed codes, schedulers, pseudopotentials, and one operational stack while weakening method portability.

3. Build one monolithic workflow command first. This may be convenient for demos, but it hides intermediate artifacts and makes it harder to diagnose why candidates are lost. The recommended path is staged commands first, then a wrapper workflow once artifacts and schemas are stable.
