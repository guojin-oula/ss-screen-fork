# Upstream reference curation design

**Status:** Approved for implementation planning
**Approved:** 2026-07-21
**Scope:** Historical notebooks, source code, and source documentation from the
read-only upstream directories declared in `AGENTS.md`

## 1. Purpose

Curate the research workspace's reusable routines, code, executed notebook
results, and historical knowledge into tracked artifacts inside `ss-screen`.
The archive must be useful to researchers reconstructing past decisions and to
developers migrating the remaining routines into package APIs or a GUI.

The archive is provenance, not executable product code. Implementations under
`src/ssscreen/` remain canonical and tested; curated artifacts retain historical
behavior, including stale parameters and known defects.

## 2. Approved scope

Include:

- primary Jupyter notebooks with code, Markdown, execution state, and outputs;
- source-distinct notebook checkpoint revisions when they preserve unique code,
  parameters, analysis, or results;
- Python source scripts;
- source documentation such as the WBM README;
- the manually authored ABACUS submission script as site-specific historical
  source;
- provenance, knowledge summaries, aliases, exclusions, transformations, and
  known-defect annotations.

Exclude:

- full datasets, including WBM `summary.txt` and compressed WBM steps;
- `.aiida` archives/directories and process dumps;
- condensed-structure and input-structure archives;
- generated calculation directories, band-plot export directories, relaxed
  structure directories, scheduler output, and generated AiiDA submission files;
- tarballs, compressed results, dependency environments, caches, and bytecode;
- result/provenance sidecars outside notebooks, such as `struct-pks.txt`, under
  the currently approved notebook/source-only boundary;
- secrets in any form.

The user confirmed authority to curate these notebook/source artifacts in this
repository. No upstream license files were found, so the manifest must record
license status as user-authorized/otherwise unspecified rather than inventing a
license for the historical content.

## 3. Repository layout

```text
references/
├── README.md
├── manifest.json
├── pair-screening/
│   ├── README.md
│   ├── notebooks/
│   ├── source/
│   └── revisions/
├── mp-condense/
├── wbm-dataset/
├── screen-mbj/
├── screen-promising/
├── screen-antiperovskite/
├── prototypes/
│   ├── rocksalt/
│   ├── zincblend/
│   └── chalcopyrite/
├── simple-defects/
└── old-screen-202411/
```

Each family README explains:

- the scientific purpose and chronology;
- the important notebooks/scripts and result types;
- inputs that remain external;
- known defects, stale names, and site-specific configuration;
- related package modules, tests, and technical documentation;
- whether the capability is migrated, partial, missing, or superseded.

Primary files use their original filename. Source-distinct autosave/checkpoint
versions go under the family's `revisions/` directory with an explicit
`checkpoint-` or revision suffix; hidden `.ipynb_checkpoints/` directories are
not recreated.

## 4. Fidelity and duplicate policy

Notebook code, Markdown, execution counts, metadata, and outputs are preserved
byte-for-byte whenever no transformation is required. Scientific figures,
tables, status streams, error outputs, and widget metadata remain inline.

Deduplication is conservative:

- byte-identical files are stored once;
- every original path still receives a manifest record;
- duplicate records point to the stored artifact through `alias_of`;
- files with identical cells but different notebook metadata remain distinct;
- source-distinct checkpoints remain distinct even when the primary is a later
  superset, because launch parameters and analysis history may differ.

This policy preserves all raw information while avoiding copies that add no new
bytes. The expected curated payload is approximately 56 MB, with the largest
individual notebook approximately 17 MB.

## 5. Secret redaction

The only contextual credential findings are positional Materials Project
credentials in:

- `screen-antiperovskite/mpset-test.ipynb`;
- `screen-antiperovskite/satbility-mp.ipynb`;
- their checkpoint-derived revisions/aliases.

For every affected stored notebook:

1. retain all non-secret code, Markdown, metadata, and outputs;
2. replace the literal credential argument with environment/config-based access
   using `MP_API_KEY` (or no explicit argument when the API supports standard
   configuration discovery);
3. do not print, log, copy, hash into user-facing text, or otherwise reproduce
   the credential value;
4. record `transformation: credential-redaction` in the manifest;
5. record the original whole-file SHA-256 and curated whole-file SHA-256;
6. run a contextual secret scan across every curated file before staging.

The upstream originals remain unchanged. Credential rotation/scrubbing of the
external source is an upstream operational issue, not part of this repository
copy.

## 6. Manifest contract

`references/manifest.json` is the machine-readable source of truth. It has a
top-level schema version, snapshot date, repository policy, source-root summary,
and one record per eligible or explicitly excluded path.

Each record contains:

- `source_path`: path relative to `/home/bonan/work/HC`;
- `artifact_kind`: notebook, Python source, shell source, source documentation,
  alias, or excluded artifact;
- `family` and `scientific_roles`;
- `status`: stored, alias, redacted, or excluded;
- `curated_path` when stored;
- `alias_of` when byte-identical content is stored elsewhere;
- `source_sha256` and, when transformed, `curated_sha256`;
- `source_size_bytes` and `curated_size_bytes`;
- `snapshot_date`;
- `source_git_head` and `source_git_dirty` where Git metadata exists;
- `outputs_preserved` for notebooks;
- `transformations`;
- `known_defects` and `portability_notes`;
- `external_dependencies` for data/calculation artifacts not copied;
- `license_status` and `redistribution_basis`.

The manifest includes excluded paths at the meaningful directory/file boundary,
not one record for every file in a multi-thousand-file dataset. This proves the
exclusion was deliberate without bloating the index.

## 7. Knowledge index

The top-level and family READMEs preserve the capability map discovered during
the audit:

- MP/WBM loading, valence screening, composition/environment grouping, gap
  backfill, and canonical binary/ternary pair generation;
- robocrys condensation and archive bundling;
- VASP PBE/HSE06/mBJ and ABACUS-HSE06 launch, retry, monitoring, k-path, band
  analysis, plotting, and CSV export;
- rocksalt, zincblende, chalcopyrite, and antiperovskite prototype construction,
  SQS, MACE relaxation, band comparison, and hull analysis;
- elemental references, manual and workchain vacancy calculations, SOC and
  supercell convergence, chemical potentials, MCT SQS/vacancy sampling, and
  cation-vacancy ranking;
- the superseded `old-screen-202411` threshold/directness policy.

Each entry links historical artifacts to the current package implementation or
to the completeness-review finding that marks it partial/missing. This allows a
future GUI to expose the stable command/file contracts while developers trace
unmigrated routines back to their evidence.

## 8. Known historical defects

Historical defects are retained and annotated, not silently repaired, except
for mandatory secret redaction. At minimum the archive records:

- `envmatch.StructureGroup.__getitem___` typo;
- stale/inlined ternary envmatch logic and `Compositions` schema spelling;
- `screen-promising/pbe-example.py` syntax/name errors and misleading HSE label;
- duplicate/misnamed PBE/HSE checkpoint content;
- site-specific codes, queues, resources, node IDs, and group paths;
- hard-coded thresholds and paths;
- stale notebook labels/cells and superseded directness policies;
- upstream checkpoint variants with materially different launcher concurrency
  or calculation selections.

Annotations live in READMEs/manifest records. The notebook/source snapshot is
not rewritten to make it look canonical.

## 9. Curation workflow

Implementation uses a deterministic curation script under `scripts/` rather
than ad hoc copies. It must:

1. inventory approved upstream roots without following or modifying them;
2. prune excluded data/generated directories;
3. parse every notebook as JSON;
4. compute raw hashes and byte-identical alias groups;
5. apply narrowly targeted credential redactions;
6. copy stored artifacts into the approved layout;
7. generate manifest and family indexes from reviewed metadata;
8. validate hashes, aliases, notebook JSON, exclusions, sizes, and secrets;
9. fail closed if a new credential indicator, unclassified candidate, or
   unexpected large file appears.

The script is idempotent: rerunning against unchanged sources produces the same
curated content and manifest apart from an explicitly controlled snapshot date.
It never executes notebooks, imports upstream code, launches AiiDA/DFT, or
touches GPU/MPI resources.

## 10. Validation and acceptance

Acceptance requires:

- every eligible source path classified as stored, alias, redacted, or excluded;
- all stored notebooks parse as valid notebook JSON;
- notebook outputs and execution state preserved except documented redactions;
- every stored unmodified artifact matches its source SHA-256;
- every alias points to byte-identical stored content;
- all transformed artifacts contain original and curated hashes plus a precise
  transformation record;
- no contextual credential finding in curated artifacts;
- no dataset/archive/calculation-output path copied;
- no curated file exceeds the reviewed size ceiling unexpectedly;
- family READMEs cover every source family and link to current package coverage;
- `git diff --check` succeeds;
- existing package tests remain unchanged/passing in proportion to the fact that
  no runtime package behavior is modified.

The final handoff reports exact stored/alias/redacted/excluded counts, total
bytes, largest artifacts, secret-scan result, and any unresolved provenance or
license caveats. No files are staged or committed unless the user explicitly
requests it.
