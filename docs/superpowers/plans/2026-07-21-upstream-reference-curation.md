# Upstream Reference Curation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, tested curation tool and use it to create a provenance-rich `references/` archive of upstream notebooks, source code, executed results, and historical revisions.

**Architecture:** A standard-library-only script inventories explicitly approved read-only source roots, classifies candidates/exclusions, deduplicates byte-identical files, redacts only known credential-bearing notebook cells, copies preserved artifacts into a family-oriented layout, and writes a machine-readable manifest plus human indexes. Synthetic tests exercise the transformations; a real dry-run/curation/validation pass proves the complete archive without executing notebooks or upstream code.

**Tech Stack:** Python 3.10+ standard library (`argparse`, `dataclasses`, `hashlib`, `json`, `pathlib`, `re`, `shutil`), pytest, Markdown, JSON.

## Global Constraints

- Never modify anything outside `/home/bonan/work/HC/ss-screen/`; upstream roots are read-only.
- Preserve notebook code, Markdown, execution state, metadata, and outputs except mandatory credential redaction.
- Do not copy datasets, `.aiida`, archives, generated calculation directories, scheduler output, dependency environments, caches, or secrets.
- Store source-distinct checkpoints as visible revisions and byte-identical duplicates as manifest aliases.
- Record original path/hash/size, curated path/hash/size, snapshot date, Git provenance where available, transformations, roles, exclusions, known defects, and license basis.
- Do not execute notebooks, import upstream code, run AiiDA/DFT, or use GPU/MPI.
- Do not stage or commit unless the user explicitly requests it.

---

### Task 1: Tested inventory, layout, and credential-redaction engine

**Files:**
- Create: `scripts/curate_upstream_references.py`
- Create: `tests/test_reference_curation.py`

**Interfaces:**
- Produces: `Candidate`, `Family`, `sha256_path(path)`, `discover_candidates(workspace_root)`, `destination_for(candidate)`, `redact_notebook(candidate, raw)`, and `curate(workspace_root, repo_root, snapshot_date, write)`.
- Consumes: synthetic source trees created by pytest `tmp_path`; no project runtime dependencies.

- [x] **Step 1: Write failing tests for classification and destinations**

```python
def test_discovery_classifies_primary_checkpoint_and_excluded_paths(tmp_path):
    workspace = make_workspace(tmp_path)
    candidates, exclusions = module.discover_candidates(workspace)
    by_path = {item.source_path: item for item in candidates}
    assert by_path["pair-screening/screening.ipynb"].kind == "notebook"
    assert by_path["pair-screening/.ipynb_checkpoints/screening-checkpoint.ipynb"].is_revision
    assert "wbm-dataset/summary.txt" in {item.source_path for item in exclusions}
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_reference_curation.py -q`
Expected: FAIL because `scripts/curate_upstream_references.py` does not exist.

- [x] **Step 3: Implement explicit source-family configuration and discovery**

```python
@dataclass(frozen=True)
class Family:
    source_name: str
    destination: str
    roles: tuple[str, ...]

@dataclass(frozen=True)
class Candidate:
    path: Path
    source_path: str
    family: Family
    kind: str
    is_revision: bool

def discover_candidates(workspace_root: Path) -> tuple[list[Candidate], list[Excluded]]:
    """Return all approved notebook/source candidates and reviewed exclusions."""
```

Use an allowlist for `.ipynb`/`.py`, `wbm-dataset/README.txt`, and
`zincblend/614426-abacus/submit.sh`. Prune `.git`, caches, generated structure,
band, relaxation, calculation, and `.aiida` directories. Record specific
excluded sidecars and aggregate generated/data directories.

- [x] **Step 4: Write failing tests for output preservation and redaction**

```python
def test_redaction_preserves_notebook_outputs(tmp_path):
    test_credential = "credential-" + "value"
    raw = notebook_bytes(f'with MPRester("{test_credential}") as mpr:\n    pass', outputs=[RESULT])
    curated, transforms = module.redact_notebook(candidate("screen-antiperovskite/mpset-test.ipynb"), raw)
    before = json.loads(raw)
    after = json.loads(curated)
    assert after["cells"][0]["outputs"] == before["cells"][0]["outputs"]
    assert test_credential not in curated.decode()
    assert "MPRester()" in curated.decode()
    assert transforms == ["credential-redaction"]
```

- [x] **Step 5: Run the focused redaction test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_reference_curation.py::test_redaction_preserves_notebook_outputs -q`
Expected: FAIL because redaction is not implemented.

- [x] **Step 6: Implement fail-closed targeted notebook redaction**

Parse notebook JSON, scan contextual patterns, and permit credential literals
only in the four reviewed antiperovskite primary/checkpoint paths. Replace the
literal positional `MPRester(...)` argument with `MPRester()`. Assert output,
execution-count, and non-source-cell equality before returning serialized JSON.
Raise `CurationError` for any contextual credential in an unapproved file or an
approved file with zero/multiple unexpected matches.

- [x] **Step 7: Run Task 1 tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_reference_curation.py -q`
Expected: PASS for discovery, destination mapping, output preservation,
redaction, and fail-closed credential cases.

### Task 2: Manifest, aliases, indexes, and archive validation

**Files:**
- Modify: `scripts/curate_upstream_references.py`
- Modify: `tests/test_reference_curation.py`

**Interfaces:**
- Produces: `references/manifest.json`, `references/README.md`, family READMEs,
  stored artifacts, aliases, redacted records, excluded summaries, and
  `validate_archive(references_root, manifest)`.
- Consumes: Task 1 discovery/redaction APIs.

- [x] **Step 1: Write failing tests for byte aliases and distinct revisions**

```python
def test_curate_aliases_exact_bytes_but_keeps_distinct_revision(tmp_path):
    result = module.curate(workspace, repo, "2026-07-21", write=True)
    records = {row["source_path"]: row for row in result["artifacts"]}
    assert records[duplicate]["status"] == "alias"
    assert records[duplicate]["alias_of"] == primary
    assert records[distinct_checkpoint]["status"] == "stored"
    assert "/revisions/" in records[distinct_checkpoint]["curated_path"]
```

- [x] **Step 2: Write failing tests for manifest and validation contracts**

```python
def test_manifest_records_hashes_transformations_exclusions_and_roles(tmp_path):
    manifest = module.curate(workspace, repo, "2026-07-21", write=True)
    redacted = record(manifest, "screen-antiperovskite/mpset-test.ipynb")
    assert redacted["source_sha256"] != redacted["curated_sha256"]
    assert redacted["outputs_preserved"] is True
    assert "credential-redaction" in redacted["transformations"]
    assert record(manifest, "wbm-dataset/summary.txt")["status"] == "excluded"
    module.validate_archive(repo / "references", manifest)
```

- [x] **Step 3: Run new tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_reference_curation.py -q`
Expected: FAIL because writing, aliasing, indexes, and validation are incomplete.

- [x] **Step 4: Implement deterministic copy, alias, and manifest generation**

Canonicalize exact-byte groups by preferring primary files, then stable source
path order. Copy unmodified files with `shutil.copyfile`; write transformed
notebooks with deterministic JSON formatting. Emit schema version `1`, snapshot
date, source roots, policy summary, counts, total sizes, Git state, and complete
records using the field contract in the design spec.

- [x] **Step 5: Implement top-level and family knowledge indexes**

Define reviewed family metadata in the script and generate READMEs containing
scientific purpose, important artifacts/results, external inputs, current
package coverage, known defects, and portability warnings. Ensure all manifest
stored paths are linked from either the family README or manifest inventory.

- [x] **Step 6: Implement archive validation and CLI**

```python
def validate_archive(root: Path, manifest: dict[str, object]) -> None:
    """Raise CurationError if hashes, aliases, notebooks, exclusions, or secrets violate policy."""

def main(argv: Sequence[str] | None = None) -> int:
    # --workspace-root, --repo-root, --snapshot-date, --dry-run, --validate-only
```

Validation reparses notebooks, verifies unmodified/curated hashes, checks alias
targets, reruns contextual secret scanning, rejects unmanifested files, and
rejects prohibited extensions/directory names.

- [x] **Step 7: Run Task 2 tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_reference_curation.py -q`
Expected: all curation tests pass.

### Task 3: Curate and verify the real upstream archive

**Files:**
- Create: `references/**` (generated by the curation script)
- Modify: `README.md`

**Interfaces:**
- Produces the reviewed ~56 MB historical archive and links it from project docs.
- Consumes the real read-only roots under `/home/bonan/work/HC`.

- [x] **Step 1: Run a real dry-run inventory**

Run:

```bash
.venv/bin/python scripts/curate_upstream_references.py \
  --workspace-root /home/bonan/work/HC \
  --repo-root /home/bonan/work/HC/ss-screen \
  --snapshot-date 2026-07-21 \
  --dry-run
```

Expected: zero credential-policy errors; summary reports classified stored,
alias, redacted, and excluded records with no writes under `references/`.

- [x] **Step 2: Generate the real archive**

Run the same command without `--dry-run`. Expected: `references/manifest.json`,
top-level/family READMEs, primary notebooks/source, and distinct revisions are
created; upstream mtimes/hashes remain unchanged.

- [x] **Step 3: Validate the generated archive independently**

Run:

```bash
.venv/bin/python scripts/curate_upstream_references.py \
  --repo-root /home/bonan/work/HC/ss-screen \
  --validate-only
```

Expected: archive validation passes, no contextual secrets are found, all
aliases/hashes resolve, all notebooks parse, and no prohibited artifact exists.

- [x] **Step 4: Link the archive from the project README**

Add `references/README.md` and `references/manifest.json` to the Documentation
section, clearly labeling them historical/non-canonical and noting that large
datasets/calculation artifacts remain external.

### Task 4: Final verification and project handoff

**Files:**
- Modify: `docs/PROJECT_LOG.md`
- Modify: `.planning/2026-07-20-upstream-reference-curation-design/task_plan.md`
- Modify: `.planning/2026-07-20-upstream-reference-curation-design/progress.md`

**Interfaces:**
- Produces completion evidence and an accurate next-step handoff.
- Consumes all earlier tasks.

- [x] **Step 1: Run focused and full tests**

Run: `.venv/bin/python -m pytest tests/test_reference_curation.py -q`
Expected: focused curation tests pass.

Run: `.venv/bin/python -m pytest -q`
Expected: full suite passes.

- [x] **Step 2: Run static and repository validation**

Run: `.venv/bin/ruff check scripts/curate_upstream_references.py tests/test_reference_curation.py`
Expected: `All checks passed!`.

Run: `.venv/bin/python scripts/curate_upstream_references.py --repo-root /home/bonan/work/HC/ss-screen --validate-only`
Expected: archive validation passes.

Run: `git diff --check`
Expected: exit 0.

- [x] **Step 3: Record exact results**

Append a newest-first `docs/PROJECT_LOG.md` entry with stored/alias/redacted/
excluded counts, byte totals, largest artifacts, validation/test evidence,
known upstream credential issue, and immediate next migration step.

- [x] **Step 4: Review the working tree without staging**

Run: `git status --short` and `git diff --stat`. Confirm no upstream path was
modified and no excluded large-data artifact appears. Do not commit.
