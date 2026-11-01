# CLI-First Implementation Plan

## Objective

Make the reusable CLI/package the immediate priority. The Chinese technical report and Chinese user guide remain important deliverables, but they should follow the stabilized command surface rather than drive it. The near-term goal is to turn `ss-screen` into a CI-testable command-line program that can run the existing pair-screening stages and begin producing its own upstream inputs.

## Current CLI Baseline

- Implemented console script: `ss-screen`.
- Implemented commands: `valence-filter`, `group`, `pair`.
- Planned next command: `condense`.
- Known naming mismatch: older planning docs mention `group-screen` and `pair-screen`, while current code and README use `group` and `pair`.
- Known test gap: `ss-screen pair` reproduces the research output in manual/end-to-end verification, but there is no small committed CLI regression fixture for the lockstep gap-compression behavior.

## Implementation Plan

- [x] **Freeze the command naming convention**: keep the current short command names `ss-screen valence-filter`, `ss-screen group`, and `ss-screen pair`; add `ss-screen condense` next. Treat old names like `group-screen` and `pair-screen` as historical names in planning docs unless explicit aliases are later requested.

- [x] **Add CLI regression tests first**: create tests for `ss-screen --help`, existing command help, missing/invalid input behavior where useful, and a tiny `ss-screen pair` run using committed fixtures. This gives CI a stable surface around the current CLI before new commands are added.

- [x] **Add `ss-screen condense` as the next CLI command**: implement a small data-layer API and CLI wrapper that can condense one structure file or a directory of structure files into `{material_id}.json` outputs. It should report counts for written, skipped, and failed items, and it should produce clear errors when the optional `robocrys` dependency is missing.

- [x] **Keep `condense` optional in tests**: unit-test the CLI and data-layer behavior with monkeypatched/mocked condensation so default CI does not require `robocrys`. Only import `robocrys` inside the runtime condensation path.

- [x] **Update README around the CLI-first surface**: document the stable current commands and mark `condense` as the command that builds condensed JSON inputs for `group`. Keep the README English-first and concise.

- [ ] **Update project log after implementation**: record that the working priority changed to CLI-first and list the implemented commands/tests.

## Verification Criteria

- `pytest` includes a CLI test module and covers `ss-screen --help`.
- `ss-screen pair` can be tested on tiny committed fixtures without full datasets, AiiDA, DFT, or `robocrys`.
- `ss-screen condense --help` is available after implementation.
- `condense` tests do not require installing `robocrys`.
- Existing M1 tests continue to pass.

## Potential Risks and Mitigations

1. **Optional `robocrys` dependency destabilizes default CI**
   Mitigation: import it only inside the real condensation function and mock that function in CLI tests.

2. **CLI names drift between docs and code**
   Mitigation: treat current implemented names as canonical and update README/project docs around them.

3. **`condense` input formats become too broad for one step**
   Mitigation: start with common pymatgen-readable structure files plus directory traversal; defer MP/WBM dataset builders to later commands.

## Alternative Approaches

1. Add aliases for old `group-screen` and `pair-screen` names immediately. This helps backward compatibility with old notes but adds surface area before there are external users.

2. Build MP/WBM loaders before `condense`. This would help create `.df` files sooner, but grouping still needs condensed JSON, so `condense` is the better first upstream CLI gap.
