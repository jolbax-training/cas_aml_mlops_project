# Tasks

## 1. Authoring spike and diagram toolchain

- [ ] 1.1 Draw a small test diagram in the draw.io XML under the authoring rules (`html=0`, no wrap, no images/gradients/links), export it with `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f svg --embed-diagram --uncompressed`, and record the exact element and attribute set the export produces; verify by listing them and confirming they fit the allowlist in design.md (or record the needed reviewed widening, or the link-plus-twin fallback).
- [ ] 1.2 Record the regeneration and verification commands in the README diagram section (edit in draw.io, save as `.drawio.svg`, run the consistency test and `build_work_log.py --check`); verify by running the documented commands as written.

## 2. Draw and verify against the code

- [ ] 2.1 Draw `docs/architecture_logical.drawio.svg` with real module names, the three status labels, CI as a gate, and only flows that exist in code; verify by tracing each box and arrow to a function, import, or script in `src/codegen_eval/` and `scripts/` and listing the evidence in `docs/progress.md`.
- [ ] 2.2 Draw `docs/architecture_physical.drawio.svg` (phase-1 local system, phase-2 elements on their own layer with dashed outline and `PHASE 2`/`EXTERNAL` tags, trust zones, no candidate-container arrows out); verify each placement and flag against `sandbox.py`, `scripts/mlflow_service.sh`, `ledger.py`, `openrouter_client.py`, `.github/workflows/ci.yml`, and `scripts/ci_pull_pinned_image.sh`.
- [ ] 2.3 Write `docs/architecture_logical.md` and `docs/architecture_physical.md` as complete text twins (components, arrows, boundaries, phases, statuses, "no live run has happened", verified-against commit); verify by reading them without the image and checking each diagram label appears in a twin.
- [ ] 2.4 Add `tests/test_architecture_diagrams.py` per design decision 6 (embedded XML decodes, labels equal rendered text, module names and coverage, status words, flags and "reads bundles" claims against source, no invented results); verify the test passes and fails on a deliberately wrong module name and a stale label.
- [ ] 2.5 Render both SVGs with the draw.io CLI (PNG export) and view them; verify legibility, no overlapping labels, and record browser or CLI evidence and the draw.io version in `docs/progress.md`.

## 3. Work-log integration

- [ ] 3.1 Add `sanitize_drawio_svg`, the `[[diagram]]` source-list tables, validation, rendering after the navigation, and provenance rows to `scripts/build_work_log.py`, leaving `validate_svg` and `SVG_TAGS` unchanged; verify with the existing `tests/test_work_log.py` still passing unmodified for the old figure.
- [ ] 3.2 Add the work-log tests from design decision 6 (accepted build, no `content` attribute in output, output validation, parametrized unsafe-construct rejections, old-figure regression, config key errors); verify they pass and each rejection test fails when its check is removed.
- [ ] 3.3 Register both diagrams in `docs/work_log.toml`, rebuild, and run `build_work_log.py --check`; verify the report shows both figures with twins, the old opening figure still comes first, and the page has no script, image, or external reference.
- [ ] 3.4 Add the pointer sentence for the new diagrams to `docs/work_log_architecture.md` and the README (touches files owned by `add-local-html-work-log`; keep to docs-only edits) and add the old-figure/logical-diagram module and status consistency test; verify with the test.

## 4. Documentation and review

- [ ] 4.1 Update `docs/progress.md` and the README (pointer, regeneration, what each diagram shows, status honesty) and the `README` plan list; verify links resolve with the work-log check.
- [ ] 4.2 Run `.venv/bin/pytest -q` and the Podman group `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`, plus `openspec validate add-architecture-diagrams --strict`; verify all pass and record counts.
- [ ] 4.3 Request an independent Fable review of the finished diagrams, twins, sanitizer, and tests; verify findings are addressed or explicitly declined in `docs/progress.md`.
- [ ] 4.4 Ask the user to open each `.drawio.svg` in draw.io and a browser and confirm they are acceptable (user judgment; not checkable by an agent).

## Workflow follow-up

- Archive the change after review and user acceptance of the diagrams.
- Decide with the owner of `add-local-html-work-log` whether the opening figure should later be replaced by the logical diagram.
