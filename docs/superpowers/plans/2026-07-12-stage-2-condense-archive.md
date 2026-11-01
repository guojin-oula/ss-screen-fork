# Stage 2 Condense Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ss-screen condense` into a reusable Stage 2 archive generator with per-material JSON files plus manifest/index metadata.

**Architecture:** Keep `{material_id}.json` files as the canonical concurrent worker artifact. Add JSONL/CSV sidecars for searchable metadata and validation, without replacing the file-per-material layout.

**Tech Stack:** Python 3.10, click, pandas, monty, pymatgen, optional robocrys, pytest, ruff.

## Global Constraints

- Only modify files inside `/home/bonan/work/HC/ss-screen`.
- Treat `../mp-condense` as read-only reference data.
- Do not require robocrys in default CI; tests must mock the condensation boundary.
- Preserve skip-existing behavior by default and write material JSON atomically.
- Keep individual JSON files as the primary archive format for concurrent readers/writers.

---

### Task 1: Archive Metadata Helpers

**Files:**
- Modify: `src/ssscreen/data/condense.py`
- Test: `tests/test_condense_archive.py`

**Interfaces:**
- Produces: `condense_materials(materials, output_dir, ...) -> CondenseSummary`
- Produces: `write_index(records, index_path) -> None`
- Produces: `validate_archive(condensed_dir, index_path=None) -> pd.DataFrame`

- [ ] Write failing tests for manifest/index generation and validation.
- [ ] Implement material-level condensation with atomic JSON writes.
- [ ] Implement JSONL manifest and CSV index sidecars.
- [ ] Implement archive validation over existing per-material JSON files.
- [ ] Run `python -m pytest tests/test_condense_archive.py -q`.

### Task 2: CLI Surface

**Files:**
- Modify: `src/ssscreen/cli/app.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `condense_paths(...)`
- Consumes: `condense_dataframe(...)`
- Consumes: `build_archive_index(...)`
- Consumes: `validate_archive(...)`

- [ ] Add tests for `ss-screen condense --df ... --manifest ... --index ...`.
- [ ] Add tests for `ss-screen condense-index`.
- [ ] Add tests for `ss-screen condense-validate`.
- [ ] Implement CLI options and commands.
- [ ] Run `python -m pytest tests/test_cli.py -q`.

### Task 3: Docs And Verification

**Files:**
- Modify: `README.md`
- Modify: `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`
- Modify: `docs/PROJECT_LOG.md`

- [ ] Document Stage 2 archive commands and storage rationale.
- [ ] Mark Stage 2 started/completed for this slice.
- [ ] Run `ruff check .`, `ruff format --check .`, `python -m pytest -q`, and `git diff --check`.
