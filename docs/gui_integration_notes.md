# SS-Screen GUI Integration Notes

## Goal

The desktop GUI should preserve the workflow thinking from the standalone review
build while keeping the existing CLI as the authoritative scientific runtime.
The two public entry points should coexist:

```text
ss-screen      # real Click CLI and scientific pipeline
ss-screen-gui  # optional PySide6 desktop workbench
```

## Design Kept From The Review Build

- A project-oriented workbench with a left project tree, central parameter pages,
  right-side properties, and a bottom log/file/message area.
- The workflow is organized by the same staged material-screening flow as the
  CLI: data sources, composition screening, structure condensation, structure
  matching, gap handoff, pairing, SQS, relaxation, thermodynamics, phonons,
  phase diagram, and recommendation.
- GUI pages collect user-facing inputs and convert them back into CLI arguments.
- Long-running work is executed through `python -m ssscreen.cli.app ...` so the
  CLI and GUI share validation, defaults, output schemas, and exit codes.
- API keys, when entered in the GUI, should be injected only into the child
  process environment and not written to commands, project files, or logs.

## Integration Boundary

The GUI must not replace or simplify `src/ssscreen/cli/app.py`. Any preview-only
or mock command surface should remain outside the production package. The CLI is
the contract used by tests, documentation, automation, and future Web workers.

The formal package exposes the GUI as an optional extra:

```text
pip install -e ".[gui]"
ss-screen-gui
```

For a fuller Ubuntu development environment, use the repository
`requirements.txt`.

## Desktop Result And Project Integration

- Stage 08 opens the relaxed/SQS structure browser and renders the selected
  structure with the bundled MatterViz 0.7.0 WebGL frontend.
- Stage 10 presents phonon status, minimum frequency, band/DOS figures, and the
  linked structure in one page.
- Stage 11 presents the competing-phase table, a ternary composition/hull map,
  and the selected competing structure.
- CPU is the default MACE device in the desktop presets. Users may still enter
  an explicit CUDA device when the target machine benefits from GPU execution.
- CLI option rows display a Chinese label together with the authoritative
  command-line flag so domain users can understand the parameter without losing
  reproducibility.
- `.ssproject` is a ZIP64 project container with a versioned `project.json`, an
  SHA-256 manifest, and artifacts from Stage 01 through Stage 12. API keys are
  explicitly excluded. Opening a project validates paths and checksums before
  extracting it to the application project cache.
- The SSH panel is intentionally a read-only validation probe in this iteration.
  It checks authentication, remote Python/`ss-screen`, and an optional remote
  project directory; it does not submit, stop, poll, or download remote jobs.

The MatterViz control sidebar is disabled because MatterViz 0.7.0 currently
triggers a `svelte-widgets` multi-select initialization error in that optional
panel. Core WebGL rendering, atom visibility, replication, mouse rotation,
zoom, and pan remain available.

## Near-Term Follow-Up

- Add a small import/launcher smoke test once a GUI-capable CI environment is
  available, or keep it guarded so headless Linux does not need a display server.
- Review each specialized GUI page against the restored real Click command
  options and remove any parameter that is only valid in the standalone demo.
- Promote the SSH probe into an explicit remote-job protocol only after a server
  test account is available. That protocol still needs upload/download rules,
  remote process identity, durable status files, reconnect behavior, and safe
  cancellation semantics.
