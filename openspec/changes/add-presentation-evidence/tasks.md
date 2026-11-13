# Tasks

Planned work only; nothing here is implemented. Tasks marked (coordinator) or (user) stay unchecked in the implementation phase until that person acts.

## 1. Evidence summary

- [x] 1.1 Add `scripts/presentation_evidence.py collect`: read the baseline and revised bundles through `comparison.compare_runs` and `bundle`, build the `provenance`, `comparison`, `efficiency`, `stories`, and `smoke` sections as in design decision 2, refuse incomplete or non-headline pairs, write canonical JSON to `presentation/evidence/summary.json`, never write into the bundles directory, never import or open the ledger.
- [x] 1.2 Add the explicit `(file, quote, field, extract)` table for document-derived values (CI runs and counts, MLflow run IDs, ledger quotes, all seven limits and the non-claim), with values computed from the quote by `extract`, and the headline-number cross-check entries against `docs/prompt_comparison.md` and the engineering snapshot (collected test counts, archived changes, specs).
- [x] 1.3 Add `check` (offline structure, arithmetic, quote-to-value binding, headline cross-check against the document, charts and manifest equality), `check --bundles` (recompute `comparison`, `efficiency`, `stories`, `smoke` and `runs`; report, not compare, `generated_by` and `commit`) and `check --staleness` (read-only, non-fatal engineering staleness note). Import `codegen_eval` lazily and redirect `CODEGEN_EVAL_LEDGER` to a temporary non-existent path first, as in design decision 3.
- [x] 1.4 Run `collect` once from this worktree with `--bundles <absolute path of the primary checkout's run_bundles>` (read-only; the worker never changes directory into the primary checkout and provenance records only relative paths), review the summary against `docs/prompt_comparison.md`, and record the commands and result in `docs/progress.md`.

## 2. Charts and manifest

- [x] 2.1 Add `scripts/render_charts.py` (summary only, standard library, deterministic) producing the thirteen charts of design decision 4, with title, desc, opaque background, count-beside-rate labels, hatch-segment fills, the limits-bearing captions, `viewBox 0 0 960 540`, every `font-size` at least 20, and only the work-log element set; add `--check`.
- [x] 2.2 After 3.1 (the logo digest must exist; an asset may otherwise be `pending`), add `presentation_evidence.py manifest` generating `presentation/manifest.json` per design decision 6 (figures, diagrams, screenshots with `pending` status, assets, recording, title with null date and placeholder).
- [ ] 2.3 (coordinator) Render the charts, open each SVG in the Orca browser in light mode and in print preview, and record what was checked (no claim of slide-size legibility; that belongs to changes 2 and 3).

## 3. Assets

- [x] 3.1 Download the ZHAW logo once from the given URL, commit `presentation/assets/zhaw_rgb.jpg` and `zhaw_rgb.jpg.source.txt` (URL, date, SHA-256), and register it in the manifest.
- [x] 3.2 (user) Confirm the logo may be used and committed.
- [ ] 3.3 (coordinator) Capture the nine screenshots listed in design decision 7 into `presentation/screenshots/` (MLflow on port 5001, not while sandbox tests run; viewport-only 1440x900); review every PNG for local paths, hostnames and the `bundle/` artifact tree before marking it present; update the manifest status to present.

## 4. Recording

- [x] 4.1 Add `scripts/record_demo.py` (`record`, `build-player`, `check`) and the hand-written `presentation/recording/player.html` per design decision 8, with the step list, scrubbing, synthetic timing, and static transcript fallback.
- [ ] 4.2 (recorded and committed; the recorder ran with Podman, the player script was exercised under Node with a stubbed DOM; opening `report/demo.html` in a browser, with and without scripting, is left to the coordinator) Run the recorder in a fresh worktree with an empty `run_bundles/` (Podman running, credential-free environment), commit `presentation/recording/demo.cast`, build `report/demo.html`, and verify by opening it and with scripting disabled.
- [ ] 4.3 (user) Review the transcript and approve it for keeping; until then the manifest marks the recording pending.

## 5. Tests, documentation, wiring

- [x] 5.1 Add offline tests and fixtures under `tests/` as listed in design decision 10; run `.venv/bin/pytest -q` and, once, `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` (foreground) and record the counts.
- [x] 5.2 Write `docs/presentation_evidence.md` (regeneration commands, interface, Git boundaries, screenshot list) and add a README section and extend the `offline` row of the README CI table with the two new checks; register the document in `docs/work_log.toml`; run `.venv/bin/python scripts/build_work_log.py --check`.
- [x] 5.3 Add the offline `presentation_evidence.py check` and `render_charts.py --check` steps to the CI `offline` job in `.github/workflows/ci.yml` (no `PYTHONPATH=src` needed).
- [ ] 5.3a (coordinator) Push, watch the Actions run, and record its run ID and result in `docs/ci_evidence.md`.
- [x] 5.4 Run `check` without bundles and `check --bundles <absolute path of the primary checkout's run_bundles>` from this worktree (read-only); record both in `docs/progress.md` as observed results only, leaving interpretation and reflections to the user.
- [x] 5.5 Run `openspec validate add-presentation-evidence --strict`.
