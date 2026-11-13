## 1. Evidence and sources

- [ ] 1.1 Re-grep the nine files for stale status words and judge each hit against D2 (stale status vs code semantics vs history); record the final list in the commit message.
- [ ] 1.2 Write `docs/architecture_status_sources.toml` (component, status, evidence file, phrase) from the table in design D1; for any row whose phrase cannot be found, leave that status unchanged and note it for the worker report.
- [ ] 1.3 Write `tests/test_architecture_status.py` (design D4) first and see it fail on the current files.

## 2. Text and figure edits

- [ ] 2.1 Edit `docs/work_log_architecture.svg` and `.md` (classes, labels, `<desc>`, lines, legend, as-of line); keep the figure validation in `scripts/build_work_log.py` unchanged.
- [ ] 2.2 Edit the four `.md` twins (logical, physical, activity, sequence): labels, sentences, status key, as-of date and commit, with the limits (5 of 60 traces unreadable, student interpretation open) stated and cited.
- [ ] 2.3 Write the throwaway edit script in the session scratchpad with the explicit cell table and count assertions (design D3), and apply it to the four `.drawio.svg` files; check the diff touches only the named cells and rects.
- [ ] 2.4 Adjust the status vocabulary in `tests/test_architecture_diagrams.py`, `tests/test_run_flow_diagrams.py`, `tests/test_work_log.py` (three labels plus `EXTERNAL`) without dropping any other assertion.

## 3. Verify and rebuild

- [ ] 3.1 `.venv/bin/pytest -q` offline: the new test passes, existing diagram and work-log tests pass, counts recorded.
- [ ] 3.2 `openspec validate refresh-architecture-status --strict`; `scripts/build_work_log.py --check`.
- [ ] 3.3 Rebuild the work log and grep `report/index.html` for the stale phrases; none may remain outside the allowlist.
- [ ] 3.4 Add a dated entry to `docs/progress.md` (new entry only; no history rewritten) naming commands run and results.
- [ ] 3.5 Visual check of the rebuilt opening figure and the four diagrams in a browser (coordinator, since the implementer has no browser session; state explicitly if not done).
- [ ] 3.6 Commit; `git status` clean.
