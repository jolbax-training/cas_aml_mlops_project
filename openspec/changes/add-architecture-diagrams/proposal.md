# Proposal

## Why

The project has one compact work-log figure (`docs/work_log_architecture.svg`) but no editable reference that answers two separate questions: *where does each piece run, and across which boundaries does it talk* (physical), and *which components exist and how does data flow between them regardless of placement* (logical). The physical question matters now because the project is about to cross from phase 1 (everything local and offline, as implemented) into phase 2 (live OpenRouter calls with a real API key and budget ledger, plus GitHub Actions CI and the registries the pinned images come from), where the trust boundaries become security-relevant. Drawing both views from the code, with honest status, lets a reader and a reviewer check the isolation claims before the first paid call.

## What Changes

- Add two draw.io-editable diagrams as `*.drawio.svg` files (SVG with the diagram XML embedded, openable and editable in draw.io): `docs/architecture_physical.drawio.svg` and `docs/architecture_logical.drawio.svg`.
- Physical view: one diagram of the phase-1 local system (macOS laptop, uv/Python CLI, Podman with one disposable no-network candidate container per check, the MLflow Podman service with durable storage on `127.0.0.1`, run bundles and spending ledger on disk, generated HTML work log) with the phase-2 elements marked as such (OpenRouter over HTTPS with API key and budget ledger, GitHub and GitHub Actions with offline and podman jobs, image registries). Trust boundaries are drawn explicitly.
- Logical view: components labelled with the real module names under `src/codegen_eval/`, with data-flow arrows from frozen tasks through the bounded agent loop, model client, and ledger, submission, sandboxed execution, grading, run bundle, then MLflow, comparison, and the work log, with CI as a gate.
- Add a Markdown text twin for each diagram (`docs/architecture_physical.md`, `docs/architecture_logical.md`) that carries the same information in prose and lists.
- Register both diagrams in the offline HTML work log through a new, separately validated path that embeds a rebuilt allowlisted SVG plus the text twin, without loosening the existing `validate_svg` checks for `docs/work_log_architecture.svg`.
- Add tests that tie each diagram's module names, statuses, and key edges to the source tree, and that cover the new work-log path including rejection of unsafe draw.io constructs.
- Point to the diagrams from the README and record verification in `docs/progress.md`. No live run has happened; the diagrams carry that status and no results.

## Capabilities

### New Capabilities

- `architecture-diagrams`: Physical and logical architecture diagrams that match the implemented code, mark phase-1 and phase-2 elements and trust boundaries honestly, ship as editable draw.io SVGs with text equivalents, and appear safely in the offline work log.

### Modified Capabilities

None. `local-work-log` is still an in-flight change (`add-local-html-work-log`), not a main spec, so this change adds its own requirements and does not edit that change.

## Impact

- New files under `docs/` (two `.drawio.svg`, two `.md` twins); `docs/work_log.toml` gains diagram entries; `scripts/build_work_log.py` gains a draw.io sanitizing path and keeps `validate_svg` unchanged; `tests/test_work_log.py` and a new diagram-consistency test; README and `docs/progress.md` updates.
- The edits to `scripts/build_work_log.py` and `tests/test_work_log.py` (owned by the in-flight `add-local-html-work-log`) are additive: that change's own tasks and tests must still pass unmodified, and its owner is told before the builder edit starts.
- No change to `src/codegen_eval` behavior, CI workflow, benchmark, or any other OpenSpec change. `docs/work_log_architecture.svg` and `.md` stay as they are (see design).
- Fits the project scope as documentation and verification work that supports the "reproducible MLOps workflow" goal; it does not block any live-run task and needs no paid call, GitHub push, or API key.
