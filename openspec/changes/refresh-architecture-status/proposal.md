## Why

The architecture and run-flow documentation still shows the state before the paid phase. Boxes and sentences read `PARTIAL: NO LIVE RUN YET`, `PENDING`, "no live call yet", "the comparison has not run", "no live spend has happened". The paid phase is complete and documented: live OpenRouter smokes and calibration (`docs/smoke_evidence.md`), the baseline and revised comparison runs and their MLflow records (`docs/comparison_evidence.md`, `docs/prompt_comparison.md`), reviewed comparison summaries, and required CI checks (`docs/ci_evidence.md`). The figures at the top of the work log and the four draw.io diagrams therefore contradict the report next to them. The user decided on 2026-11-13 to fix this.

## What Changes

- Inventory every stale status label and stale sentence in `docs/work_log_architecture.svg` and `.md`, `docs/architecture_logical.md` and `.drawio.svg`, `docs/architecture_physical.md` and `.drawio.svg`, `docs/run_flow_activity.md` and `.drawio.svg`, `docs/run_flow_sequence.md` and `.drawio.svg` (design.md lists them).
- Change each stale status only where a committed source supports it, recorded in a new `docs/architecture_status_sources.toml` (component, status, evidence file, evidence phrase). Anything still open stays open and is stated as open.
- Edit each `.drawio.svg` by one scripted edit that changes the embedded draw.io model and the rendered SVG together. No re-layout and no new shapes. draw.io desktop is not required.
- Keep dated history as history: progress entries, archived changes, and "as of" statements about what was true then are not rewritten as current status.
- Add an offline test that fails if a current-status figure or page claims a stale status, or a status has no cited source. It runs in the existing offline CI job through pytest.
- Update the existing tests that pin the old three-label wording, refresh the "as of" date and commit in each twin, and rebuild the work log.
- Not in scope: redrawing layouts, new diagrams (the presentation change adds slide diagrams under `presentation/`), `src/` code, and other documents.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `architecture-diagrams`: "Honest status" is modified (statuses follow committed evidence, not the pre-run state) and a requirement is added for the evidence-backed status check.

## Impact

- Files: the nine docs named above, `docs/architecture_status_sources.toml` (new), `tests/test_architecture_status.py` (new), and the status assertions in `tests/test_architecture_diagrams.py`, `tests/test_run_flow_diagrams.py` and `tests/test_work_log.py`. The generated `report/` is rebuilt and is Git-ignored.
- No change to `src/`, CI configuration, dependencies, or the work-log sanitizer.
- Completion evidence: `openspec validate --strict`, `pytest -q` offline green, the work-log `--check`, and a rebuilt report whose first figure shows no stale label.
