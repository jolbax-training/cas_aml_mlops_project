# Tasks

Planned work only; nothing here is implemented. Tasks marked (coordinator) or (user) stay unchecked in the implementation phase until that person acts. Real-data tasks need `add-presentation-evidence` merged (manifest, `summary.json`, charts, logo); fixture-based tasks do not.

## 1. Builder and sources

- [ ] 1.1 Add `scripts/build_report.py` with `build`, `check`, `measure`: manifest and summary loading, the closed directive set of design decision 2 (`val`, `fig`, `shot`, `ref`, `logo`, `title`, `user`, `limits`, `evidence_table`), HTML escaping, inlined SVG through `scripts/build_work_log.py` (loaded by path) with id prefixing, data-URI images, deterministic output, writing only `report/presentation_report.html`.
- [ ] 1.2 Add `presentation/report/template.html` (four pages, prose from repo documents only, digits only through directives, figure list as in design decision 3), `presentation/report/report.css` (screen sheets, A4 print rules, 296 mm page boxes, `screen-only`, slot box sizes, placeholder styles), and `presentation/report/user_text.toml` (empty slots with the authorship header).
- [ ] 1.3 Implement figure numbering by order of appearance, `{{ref:}}` resolution, pending-screenshot and null-date placeholders, per-chart source-key footnotes, and the evidence section with visible run IDs, digests and document paths.
- [ ] 1.4 Implement user-slot handling: visible placeholders, escaped rendering, length limit, `--require-user-text` release build listing every unfilled slot, date and used screenshot.
- [ ] 1.5 Resolve open questions 1 to 4 of `design.md` with the coordinator before the real build (chart size floor, protocol facts, user-text file, work-log link) and record the answers in `design.md`.

## 2. Checks

- [ ] 2.1 Implement `check`: four page sections, print rules present, no script, handler or external reference, id uniqueness, contiguous figure numbers, resolved references and directives, per-page content budgets, slot length limits, the digits lint and the "improvement/breakthrough" lint, navigation hidden in print, placeholder report.
- [ ] 2.2 Implement `measure`: browser discovery with distinct skipped exit status, per-page used versus available height through a throwaway injected measuring copy (never the shipped file), 94% headroom warning, PDF printing with a standard-library page counter, `--pdf PATH` to keep the PDF, result table.
- [ ] 2.3 Calibrate the static per-page budgets against the first real `measure` result and record the numbers in `docs/presentation_report.md`.

## 3. Tests

- [ ] 3.1 Add `tests/fixtures/presentation_report/` (tiny summary and manifest, two charts, a stub diagram, 1x1 images, a template covering every directive) and `tests/test_presentation_report.py` covering the nine groups of design decision 9, including the two lints, determinism, PDF page counter on hand-made PDFs, canned measurement parsing and the static no-ledger/no-bundle inspection.
- [ ] 3.2 Run the full offline test suite and `openspec validate add-presentation-report --strict`.

## 4. Real build and evidence

- [ ] 4.1 After the evidence change is merged, build the real report, run `check`, and review the HTML at print width for legibility of each figure and diagram; adjust the figure selection (a template edit) if a page does not fit.
- [ ] 4.2 Run `build_report.py measure` on the laptop and record browser version, per-page fill and the four-page result in `docs/progress.md`.
- [ ] 4.3 (coordinator) Open the report in the Orca browser, in print preview, check navigation disappears, and compare with the measurement; capture `report-local-architecture.png` and `report-local-results.png` for the deck if still pending.
- [ ] 4.4 (user) Write the motivation and the interpretation/takeaways in `presentation/report/user_text.toml`, set the date in the manifest source, and approve the figure selection.
- [ ] 4.5 (user) Run the release build (`build --require-user-text`), print to PDF per `docs/presentation_report.md`, and confirm four pages.

## 5. Documentation and wiring

- [ ] 5.1 Add `docs/presentation_report.md` (build, release build, print recipe, `measure`, placeholders, how to edit the user text and the figure list, font-stack caveat).
- [ ] 5.2 Small additive edits: `README.md` (commands), `docs/progress.md` (measurement and placeholder status), `docs/work_log.toml` (register the document), `.github/workflows/ci.yml` (`build_report.py check` in the offline job); list them for the coordinator's merge with the deck and evidence changes.
