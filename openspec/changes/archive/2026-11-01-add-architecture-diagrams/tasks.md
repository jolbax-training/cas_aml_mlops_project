# Tasks

## 1. Authoring spike and diagram toolchain

- [x] 1.1 Draw a small test diagram in the draw.io XML under the authoring rules (`html=0`, no wrap, no images/gradients/links), export it with `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f svg --embed-diagram --svg-theme light --embed-svg-fonts false`, with the documented flags (`--svg-theme light --embed-svg-fonts false`), and confirm the element and attribute set observed in the review spike (design decision 3) against the sanitizer allowlist; verify by listing them, and also re-export the saved file with the draw.io CLI and check its elements the same way (a GUI save in draw.io desktop is left to task 4.4; or record the needed reviewed widening, or the link-plus-twin fallback).
- [x] 1.2 Record the regeneration and verification commands in the README diagram section (edit in draw.io, save as `.drawio.svg`, run the consistency test and `build_work_log.py --check`); verify by running the documented commands as written.

## 2. Draw and verify against the code

- [x] 2.1 Draw `docs/architecture_logical.drawio.svg` with real module names, the three status labels, CI as a gate, and only flows that exist in code; verify by tracing each box and arrow to a function, import, or script in `src/codegen_eval/` and `scripts/` and listing the evidence in `docs/progress.md`.
- [x] 2.2 Draw `docs/architecture_physical.drawio.svg` (phase-1 local system, phase-2 elements on their own layer with dashed outline and `PHASE 2`/`EXTERNAL` tags, trust zones, no candidate-container arrows out); verify each placement and flag against `sandbox.py`, `scripts/mlflow_service.sh`, `ledger.py`, `openrouter_client.py`, `.github/workflows/ci.yml`, and `scripts/ci_pull_pinned_image.sh`.
- [x] 2.3 Write `docs/architecture_logical.md` and `docs/architecture_physical.md` as complete text twins (components, arrows, boundaries, phases, statuses, "no live run has happened", verified-against commit); verify by reading them without the image and checking each diagram label appears in a twin.
- [x] 2.4 Add `tests/test_architecture_diagrams.py` per design decision 6 (embedded XML decodes, labels equal rendered text, module names and coverage, status words, flags and "reads bundles" claims against source, no invented results); verify the test passes and fails on a deliberately wrong module name and a stale label.
- [x] 2.5 Render both SVGs with the draw.io CLI (PNG export) and view them; verify legibility, no overlapping labels, and that a draw.io CLI re-export of each file still passes the sanitizer; record browser or CLI evidence and the draw.io version in `docs/progress.md`.

## 3. Work-log integration

- [x] 3.0 Tell the owner of `add-local-html-work-log` (via the coordinator) that this change adds code to `scripts/build_work_log.py`; verify the notice is sent. Done 2026-11-01: the coordinator owns that change and acknowledged the additive edits to `scripts/build_work_log.py` and the tests (new tests are in `tests/test_work_log_diagrams.py`; `tests/test_work_log.py` is untouched).
- [x] 3.1 Add `sanitize_drawio_svg`, the `[[diagram]]` source-list tables, validation, rendering after the navigation, and provenance rows to `scripts/build_work_log.py`, leaving `validate_svg` and `SVG_TAGS` unchanged; verify with the existing `tests/test_work_log.py` still passing unmodified for the old figure.
- [x] 3.2 Add the work-log tests from design decision 6 (accepted build, no `content` attribute in output, output validation, parametrized unsafe-construct rejections, old-figure regression, config key errors); verify they pass and each rejection test fails when its check is removed.
- [x] 3.3 Register both diagrams in `docs/work_log.toml`, rebuild, and run `build_work_log.py --check`; verify the report shows both figures with twins, the old opening figure still comes first, and the page has no script, image, or external reference.
- [x] 3.4 Add the pointer sentence for the new diagrams to `docs/work_log_architecture.md` and the README (touches files owned by `add-local-html-work-log`; keep to docs-only edits) and add the old-figure/logical-diagram module and status consistency test; verify with the test.

## 4. Documentation and review

- [x] 4.1 Update `docs/progress.md` and the README (pointer, regeneration, what each diagram shows, status honesty) and the `README` plan list; verify links resolve with the work-log check.
- [x] 4.2 Run `.venv/bin/pytest -q` and the Podman group `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`, plus `openspec validate add-architecture-diagrams --strict`; verify all pass and record counts.
- [x] 4.3 Request an independent Fable review of the finished diagrams, twins, sanitizer, and tests; verify findings are addressed or explicitly declined in `docs/progress.md`. Done 2026-11-01: Fable implementation review (0 blocker, 2 major, 11 minor) plus seven coordinator layout findings from the rendered PNGs; all fixed except finding 9, declined with reason; the coordinator re-viewed the v2 renders.
- [x] 4.4 Ask the user to open each `.drawio.svg` in draw.io desktop and a browser, save it once (compression off), re-run `tests/test_architecture_diagrams.py` and `build_work_log.py --check`, and confirm the diagrams are acceptable (user judgment; not checkable by an agent). Done 2026-11-01: the user opened both diagrams in draw.io desktop and confirmed they are acceptable; the files were left byte-identical (no GUI re-save written), and both diagram test modules and `build_work_log.py --check` passed afterwards.

## Workflow follow-up

- Archive the change after review and user acceptance of the diagrams.
- Decide with the owner of `add-local-html-work-log` whether the opening figure should later be replaced by the logical diagram.
