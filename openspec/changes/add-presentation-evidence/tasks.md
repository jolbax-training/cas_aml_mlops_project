# Tasks

Planned work only; nothing here is implemented. Tasks marked (coordinator) or (user) stay unchecked in the implementation phase until that person acts.

## 1. Evidence summary

- [ ] 1.1 Add `scripts/presentation_evidence.py collect`: read the baseline and revised bundles through `comparison.compare_runs` and `bundle`, build the `provenance`, `comparison`, `efficiency`, `stories`, and `smoke` sections as in design decision 2, refuse incomplete or non-headline pairs, write canonical JSON to `presentation/evidence/summary.json`, never write into the bundles directory, never import or open the ledger.
- [ ] 1.2 Add the explicit `(file, quote, field)` table for document-derived values (CI runs and counts, MLflow run IDs, ledger quotes, limits and non-claim) and the engineering snapshot (collected test counts, archived changes, specs).
- [ ] 1.3 Add `check` (offline structure, arithmetic, quotes, charts and manifest equality) and `check --bundles` (recompute bundle-derived sections) and `check --refresh` (non-fatal engineering staleness note).
- [ ] 1.4 Run `collect` once on the primary checkout's retained bundles (read-only), review the summary against `docs/prompt_comparison.md`, and record the commands and result in `docs/progress.md`.

## 2. Charts and manifest

- [ ] 2.1 Add `scripts/render_charts.py` (summary only, standard library, deterministic) producing the thirteen charts of design decision 4, with title, desc, opaque background, count-beside-rate labels, pattern fills, and the limits-bearing captions; add `--check`.
- [ ] 2.2 Add `presentation_evidence.py manifest` generating `presentation/manifest.json` per design decision 6 (figures, diagrams, screenshots with `pending` status, assets, recording, title with null date and placeholder).
- [ ] 2.3 Render the charts, open each SVG in a browser in light mode and in print preview, and record what was checked (no claim of slide-size legibility; that belongs to changes 2 and 3).

## 3. Assets

- [ ] 3.1 Download the ZHAW logo once from the given URL, commit `presentation/assets/zhaw_rgb.jpg` and `zhaw_rgb.jpg.source.txt` (URL, date, SHA-256), and register it in the manifest.
- [ ] 3.2 (user) Confirm the logo may be used and committed.
- [ ] 3.3 (coordinator) Capture the nine screenshots listed in design decision 7 into `presentation/screenshots/` (MLflow on port 5001, not while sandbox tests run; avoid the five unreadable traces); update their manifest status to present.

## 4. Recording

- [ ] 4.1 Add `scripts/record_demo.py` (`record`, `build-player`, `check`) and the hand-written `presentation/recording/player.html` per design decision 8, with the step list, scrubbing, synthetic timing, and static transcript fallback.
- [ ] 4.2 Run the recorder on the laptop (Podman running, credential-free environment), commit `presentation/recording/demo.cast`, build `report/demo.html`, and verify by opening it and with scripting disabled.
- [ ] 4.3 (user) Review the transcript and approve it for keeping; until then the manifest marks the recording pending.

## 5. Tests, documentation, wiring

- [ ] 5.1 Add offline tests and fixtures under `tests/` as listed in design decision 10; run `.venv/bin/pytest -q` and, once, `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` (foreground) and record the counts.
- [ ] 5.2 Write `docs/presentation_evidence.md` (regeneration commands, interface, Git boundaries, screenshot list) and add a README section; register the document in `docs/work_log.toml`; run `.venv/bin/python scripts/build_work_log.py --check`.
- [ ] 5.3 Add the offline `presentation_evidence.py check` and `render_charts.py --check` steps to the CI `offline` job in `.github/workflows/ci.yml`. (Pushing and watching Actions is the coordinator's.)
- [ ] 5.4 Run `check` without bundles and, on the primary checkout, `check --bundles run_bundles`; record both in `docs/progress.md` as observed results only, leaving interpretation and reflections to the user.
- [ ] 5.5 Run `openspec validate add-presentation-evidence --strict`.
