## 1. Evidence and sources

- [ ] 1.1 Re-grep (case-insensitive) the nine files, `docs/demo.md`, `README.md` and the "Current status" section of `docs/progress.md` for the stale phrases of design D4 and judge each hit against D2 (stale status, code semantics, history); record the final list in the commit message.
- [ ] 1.2 Write `docs/architecture_status_sources.toml` (component, status, evidence file, phrase, plus the completed-run sentence per twin) from design D1; the MLflow entry uses the "60 of 60 traces read back after `--retrace`" phrase of `docs/progress.md`; a row whose phrase cannot be found keeps its status and goes in the worker report.
- [ ] 1.3 Write `tests/test_architecture_status.py` (design D4) first and see it fail on the current files.

## 2. Text and figure edits

- [ ] 2.1 Edit `docs/work_log_architecture.svg` and `.md` (classes, labels, `<desc>`, lines, legend, as-of line); keep the figure validation in `scripts/build_work_log.py` unchanged.
- [ ] 2.2 Edit the four `.md` twins (logical, physical, activity, sequence): labels, sentences, status key, the activity line 5 sentence about the unset revised prompt, as-of date and commit; state the limits of design D1 (30-trial pilot, student interpretation open) and say nothing about unreadable traces.
- [ ] 2.3 Write the throwaway edit script in the session scratchpad with the per-cell table of design D3, locating rendered nodes by `data-cell-id` and asserting counts; apply it to the four `.drawio.svg` files and check the diff touches only the named cells (OpenRouter cells keep their dash and tags).
- [ ] 2.4 Update the assertions that pin the stale sentences (`tests/test_architecture_diagrams.py:160-161`, `tests/test_run_flow_diagrams.py:257` and `:548`) to the inverse assertion, and the `STATUSES`/three-label vocabulary in `test_architecture_diagrams.py`, `test_run_flow_diagrams.py` and `test_work_log.py:329-331` to include `EXTERNAL`, without dropping any other assertion.
- [ ] 2.5 Minimal edits to `docs/demo.md:86` and `README.md` lines 5, 48, 124, 193.
- [ ] 2.6 Append the dated supersession note after `docs/comparison_evidence.md:14` (design D7); the original sentence stays byte-identical.
- [ ] 2.7 Bring the "Current status" section of `docs/progress.md` to the evidenced state (design D8), then add one new dated entry for this change at the top of the entries; no older entry or `docs/project_spec.md` is edited.

## 3. Verify, rebuild, commit

- [ ] 3.1 `.venv/bin/pytest -q` offline: the new test and the existing diagram and work-log tests pass; record the counts.
- [ ] 3.2 `.venv/bin/python scripts/presentation_evidence.py check` passes (design D7); if it fails, regenerate `summary.json` with its own script, never by hand.
- [ ] 3.3 `openspec validate refresh-architecture-status --strict`; `scripts/build_work_log.py --check`.
- [ ] 3.4 Rebuild the work log and grep the opening figure and the four diagram sections of `report/index.html` (not the whole page) for the stale phrases of design D4; none may remain outside the allowlist.
- [ ] 3.5 Commit (Sonnet co-author line); `git status` clean; leave push, merge and archive to the coordinator.
- [ ] 3.6 Browser visual check of the rebuilt opening figure and the four diagrams (coordinator, Orca browser, on the committed rebuild); left unticked for the coordinator.
