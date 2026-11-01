# Tasks

## 1. Review of the proposal and authoring spike

- [ ] 1.1 Request an independent Fable review of proposal.md, design.md, the delta spec, and this task list against the code before any diagram work; verify every finding is fixed in the artifacts or declined with a reason recorded in `docs/progress.md`, and `openspec validate add-run-flow-diagrams --strict` still passes.
- [ ] 1.2 Draw a small activity-style and sequence-style test diagram (swimlane, rhombus decision, initial node, final node as ellipse in ellipse, `umlLifeline`, `umlFrame` fragment, dashed boundary rectangle, labelled edges) under the authoring rules (`html=0`, no `whiteSpace`, no images or gradients or links), export with `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f svg --embed-diagram --svg-theme light --embed-svg-fonts false`, and list the elements and attributes of the result; verify by running `sanitize_drawio_svg` on the export (or recording the shape change, the reviewed allowlist addition, or the link-plus-twin fallback needed). Do not commit the spike files.

## 2. Draw and verify against the code

- [ ] 2.1 Re-derive the flow by walking `experiment_cli.main`, `experiment.check_preconditions`, `experiment.run_variant`, `run_recording.run_recorded`, `trial.run_trial`, `openrouter_client.OpenRouterClient.complete`, `ledger.Ledger.reserve`, `run_checks.run_checks`, `evaluate.grade_trial`, `sandbox.execute_check`, `bundle.BundleWriter`, and `mlflow_tracking.bundle_recorder`; write the node, decision, and ending list with one function reference each into `docs/run_flow_activity.md` first; verify that every ending in design decision 3 is confirmed or corrected from the code and that no sixth ending exists (or add it).
- [ ] 2.2 Draw `docs/run_flow_activity.drawio.svg` (swimlanes host CLI, OpenRouter EXTERNAL PHASE 2, sandbox container TRUST BOUNDARY, storage and MLflow, plus the after-the-run lane; start node, precondition gates, per-variant frame, schedule loop, agent loop with limits, grading loop, bundle then MLflow with the outage marker, five final nodes, checkpoint as a continuing action); verify box-by-box against the twin's function references and against the logical diagram's box names.
- [ ] 2.3 Complete `docs/run_flow_activity.md` as the text twin (every node, decision, arrow, lane, ending with exit status, manifest status, marker status; the three differences from the briefing in design decision 2; lane statuses; "no live run has happened"; verified-against commit); verify by reading it without the image and checking every diagram label appears in it.
- [ ] 2.4 Draw `docs/run_flow_sequence.drawio.svg` and write `docs/run_flow_sequence.md` (participants, message order, `loop` and `alt` fragments, trust-boundary frame, note that MLflow recording is once per run); verify each message against the function it names and that the order of reserve, send, response, settle, request logging, grading, and `write_trial` matches the source.
- [ ] 2.5 Render both SVGs to PNG with the draw.io CLI and view them; verify legibility, no overlapping labels, no crossing of the trust boundary except the launcher, and that a draw.io CLI re-export of each file still passes the sanitizer; record the draw.io version and the evidence in `docs/progress.md`.

## 3. Tests and work-log integration

- [ ] 3.1 Add `tests/test_run_flow_diagrams.py` per design decision 6 (embedded XML and rendered labels, names and functions exist, five final nodes with exit and status constants, limits equal the source, order claims against the source, lane and participant names shared with the logical twin, EXTERNAL and PHASE 2 tags, boundary arrows, no invented evidence); verify it passes and fails on a deliberately wrong function name, a removed ending, a changed limit, and a swapped reserve/send order in a temporary copy of the source.
- [ ] 3.2 Register both diagrams in `docs/work_log.toml` after the existing two, rebuild, and run `.venv/bin/python scripts/build_work_log.py --check`; verify the report shows both figures with their twins after the accepted diagrams and has no script, image, or external reference, and that the sanitizer and `tests/test_work_log_diagrams.py` are unmodified and pass.
- [ ] 3.3 Add the work-log build test for the new entries to `tests/test_run_flow_diagrams.py`; verify it asserts order, `role="img"`, title, description, twin, and provenance rows.

## 4. Documentation, review, and acceptance

- [ ] 4.1 Update `README.md` (pointer, one line on what each new diagram shows, regeneration commands for the two new files) and `docs/progress.md` (evidence, spike result, differences from the briefing, no-live-run statement); verify the links resolve through the work-log check and that `git diff --stat` shows the accepted diagrams and twins unchanged.
- [ ] 4.2 Run `.venv/bin/pytest -q`, `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`, and `openspec validate add-run-flow-diagrams --strict`; verify all pass and record the counts.
- [ ] 4.3 Request an independent Fable review of the finished diagrams, twins, tests, and any sanitizer change; verify findings are addressed or explicitly declined in `docs/progress.md`.
- [ ] 4.4 Ask the user to open both new `.drawio.svg` files in draw.io desktop and a browser, save once with compression off if they edit, re-run `tests/test_run_flow_diagrams.py` and `build_work_log.py --check`, and confirm the diagrams are acceptable and that the three differences from the briefing (variants as separate runs, MLflow once per run, summary and comparison as separate commands) are right (user judgment; not checkable by an agent; leave unchecked until the user confirms).

## Workflow follow-up

- Archive the change after review and user acceptance.
- Optionally share the diagram test helpers between the two test modules once the accepted change's tests may be edited.
