# CLI tutorial design

## Purpose

Add a concise, interface-first tutorial for `ss-screen`. It must let a
materials researcher run the screening pipeline and let a GUI developer wrap
each CLI stage as a file-in/file-out job without reproducing package internals.

## Audience

- Researchers who need a complete, reproducible screening workflow.
- Software developers building a GUI or another orchestration layer around the
  command-line interface.

## Deliverable

Create `docs/CLI_TUTORIAL.md` and add it to the README documentation list. No
CLI code, notebooks, bundled research data, or GUI code is in scope.

## Tutorial structure

1. **Orientation and setup**
   - State the scientific screening boundary: the CLI groups candidates and
     enumerates pair endmembers; high-level gap calculations remain external.
   - Explain core versus optional extras and path conventions.
2. **Full staged workflow**
   - Show the recommended artifact pipeline: normalized dataset (`.df`) →
     composition candidates (CSV) → condensed archive (JSON files plus
     manifest/index) → structure groups (JSON) → external-gap candidates (CSV
     and optional structures) → validated gap results (CSV/JSON) → pairs (CSV)
     → optional SQS manifest (JSONL).
   - Include the binary historical reproduction with the legacy `--gaps`
     contract; clearly label its source inputs as read-only reference data.
3. **Command contracts**
   - One compact entry for every public command group and command:
     `dataset mp`, `dataset wbm`, `valence-filter`, `composition-screen`,
     `condense`, `condense-index`, `condense-validate`, `structure-match`,
     `gap-export`, `gap-validate`, `pair`, `gap-compare`,
     `stability sqs-generate`, and legacy `group`.
   - For each, list required input files, written files, important columns or
     JSON fields, optional extras, and contract-relevant failures.
4. **GUI integration contract**
   - Model each command as a background job with explicit paths, captured
     stdout/stderr, exit status, and structured output files.
   - Treat output files as authoritative only after exit code zero; surface
     per-row failures from condensation manifests and gap-validation errors.
   - Do not expose or store MP credentials in GUI project files; use the normal
     environment/configuration mechanism for the selected backend.
5. **Reproducibility and limits**
   - Preserve source datasets, condensed archive, gap method, threshold options,
     and summaries alongside final pairs.
   - Explain that directness is an informational output field by default, not a
     default hard filter; distinguish screening candidates from verified alloys.

## Accuracy requirements

- Derive all command names/options and formats from `src/ssscreen/cli/app.py`
  and the supporting data/pair modules, not from historical notebooks alone.
- Use illustrative placeholder paths only; do not imply the package ships the
  multi-GB research datasets.
- State output formats exactly: `.df` is a pickled pandas DataFrame; group
  artifacts are JSON; final pairs are CSV; SQS job queues are JSONL.
- Prefer command output summaries and manifests for GUI progress/result display.

## Verification

- Run `ss-screen --help` and each command's `--help` where feasible from the
  existing virtual environment, checking that documented names/options exist.
- Review the rendered Markdown source for broken links, inconsistent artifact
  names, TODO markers, and unsupported claims.
