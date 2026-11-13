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
- [x] 2.3 (coordinator) Render the charts, open each SVG in the Orca browser in light mode and in print preview, and record what was checked (no claim of slide-size legibility; that belongs to changes 2 and 3). Done by the coordinator 2026-11-13: all charts rendered in headless Chrome 157 and inspected during the round-3 and round-4 reviews and by the coordinator (pipeline, trust boundary, outcome, per-category, per-task); in print they were checked through the report PDF (Chrome print, 4 pages, no clipping).

## 3. Assets

- [x] 3.1 Download the ZHAW logo once from the given URL, commit `presentation/assets/zhaw_rgb.jpg` and `zhaw_rgb.jpg.source.txt` (URL, date, SHA-256), and register it in the manifest.
- [x] 3.2 (user) Confirm the logo may be used and committed.
- [x] 3.3 (coordinator) Capture the nine screenshots listed in design decision 7 into `presentation/screenshots/` (MLflow on port 5001, not while sandbox tests run; viewport-only 1440x900); review every PNG for local paths, hostnames and the `bundle/` artifact tree before marking it present; update the manifest status to present. Done by the coordinator: seven MLflow shots in a3385ac and two report-local shots in b320dd0, each reviewed for local paths, hostnames and bundle trees; one mis-rendered compare-table shot was discarded.

## 4. Recording

- [x] 4.1 Add `scripts/record_demo.py` (`record`, `build-player`, `check`) and the hand-written `presentation/recording/player.html` per design decision 8, with the step list, scrubbing, synthetic timing, and static transcript fallback.
- [x] 4.2 (recorded and committed; the recorder ran with Podman, the player script was exercised under Node with a stubbed DOM; opening `report/demo.html` in a browser, with and without scripting, is left to the coordinator) Run the recorder in a fresh worktree with an empty `run_bundles/` (Podman running, credential-free environment), commit `presentation/recording/demo.cast`, build `report/demo.html`, and verify by opening it and with scripting disabled. Done by the coordinator 2026-11-13 on 3238a31: report/demo.html plays to 51.4 s with scripting in headless Chrome; without scripting the page keeps the full plain-text transcript (4,311 characters) and a noscript notice, with no external references.
- [ ] 4.3 (user) Review the transcript and approve it by adding `presentation/recording/review.txt`; until then the manifest marks the committed recording `unreviewed` (`pending` only when no cast exists).

## 5. Tests, documentation, wiring

- [x] 5.1 Add offline tests and fixtures under `tests/` as listed in design decision 10; run `.venv/bin/pytest -q` and, once, `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` (foreground) and record the counts.
- [x] 5.2 Write `docs/presentation_evidence.md` (regeneration commands, interface, Git boundaries, screenshot list) and add a README section and extend the `offline` row of the README CI table with the two new checks; register the document in `docs/work_log.toml`; run `.venv/bin/python scripts/build_work_log.py --check`.
- [x] 5.3 Add the offline `presentation_evidence.py check` and `render_charts.py --check` steps to the CI `offline` job in `.github/workflows/ci.yml` (no `PYTHONPATH=src` needed).
- [x] 5.3a (coordinator) Push, watch the Actions run, and record its run ID and result in `docs/ci_evidence.md`. (Evidenced by run 43461309299 on `main` at `e00236d`, recorded in `docs/ci_evidence.md`; it ran the three presentation CI steps.)
- [x] 5.4 Run `check` without bundles and `check --bundles <absolute path of the primary checkout's run_bundles>` from this worktree (read-only); record both in `docs/progress.md` as observed results only, leaving interpretation and reflections to the user.
- [x] 5.5 Run `openspec validate add-presentation-evidence --strict`.

## 6. Round 2 additions (decisions D1-D3)

- [x] 6.1 Add compact half-width variants (decision 11): viewBox 480x270, fonts at least 17 units, ten charts, manifest fields `variant` and `full_size`; extend the font-size, extent, determinism and link tests.
- [x] 6.2 Add the `protocol` section (decision 12) from the quote table, with tamper tests and the `check` cross-verification.
- [x] 6.3 Add `presentation/user_text.toml` with empty marked slots, list it in the manifest, and test that tools never write it (decision 13).
- [x] 6.4 Require non-empty `alt` on every manifest entry including assets and improve the logo's alt text.
- [x] 6.5 Record in `docs/presentation_evidence.md` and `docs/progress.md` the additions and that `schema_version` stays 1 because they are additive (decision 14); rerun the full checks and tests.

## 7. Round 3 (review of the deck's charts, user decision on diagrams)

- [x] 7.1 Fix the footnote overlap in `outcome-by-category` (full-size and compact) through the generator, and harden the overlap test (ascent, descent, strokes, clearance) with the old chart as a failing fixture.
- [x] 7.2 Add the pipeline-overview and trust-boundary diagrams (decision 15) to `scripts/render_charts.py`, register them in the manifest (`diagram-pipeline-overview`, `diagram-trust-boundary`), and test the box-to-source mapping, the element set, font size, determinism and the absence of status labels.
- [x] 7.3 Regenerate the charts, summary and manifest through the scripts, record the results in `docs/progress.md` and `docs/presentation_evidence.md`, and rerun the checks and tests.

## 8. Round 4 (final CI state)

- [x] 8.1 Record the latest run on main in `docs/ci_evidence.md` ("Latest run on main") and add its quote-table entry with an explicit `latest` marker (decision 16).
- [x] 8.2 Store `engineering.ci.latest`, make the engineering charts and the report's test figure and CI sentence use it, require exactly one latest marker, fail the offline check on a mismatch, and test it.
- [x] 8.3 Regenerate the summary (bundles read-only), charts and manifest at the new commit's tree through the scripts; rerun the deck and report checks (the report's static page estimates are unchanged).

Left for others: 2.3 (coordinator: charts and diagrams opened in a browser and in print preview), 4.2 (coordinator: open `report/demo.html` in a browser with and without scripting) and 4.3 (the user: approve the recording transcript by adding `presentation/recording/review.txt`); 3.3 (screenshots) is the coordinator's and is ticked only when all nine files exist.

## 9. Round 5 (the user can set the date)

- [x] 9.1 Add the empty `[title] date` key to `presentation/user_text.toml`, record `title.date_source` in the manifest, validate a filled value in the checker, and extend the never-writes test (decision 17).
- [x] 9.2 Make the deck and the report builders read the date from the user-text file (minimal edits to their date lines and tests): placeholder while empty, strict and release builds fail while empty, validated and escaped when filled.
- [x] 9.3 State in `docs/presentation_evidence.md`, `docs/presentation_deck.md` and `docs/presentation_report.md` exactly where the user writes the date; rerun the checks and tests.
