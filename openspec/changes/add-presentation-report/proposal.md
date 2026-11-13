# Proposal

## Why

The project is complete and the user must hand in a 4-page, printable HTML report for classmates and examiners, in English, alongside the 15-minute talk (`add-presentation-deck`). The report follows the deck's structure with more detail: motivation, problem statement, approach (architecture, sandbox and scoring integrity, reproducibility, budget ledger), results and statistics, limits, lessons and conclusions. Its numbers and figures come from the shared evidence of `add-presentation-evidence`, never from retyped values, and "exactly four printed pages" is a hard requirement that a normal HTML page does not enforce by itself.

The framing is fixed by the user: "a trustworthy, reproducible, budget-safe evaluation pipeline for a coding agent". The prompt comparison (27/30 to 29/30 successful task trials) is the worked example with its honest limits, not a measured improvement or breakthrough. Motivation, interpretation and takeaways are the user's own words, so the report only provides clearly visible slots for them.

## What Changes

- Add a hand-written report template, stylesheet and user-text source under `presentation/report/` (committed sources), and a build script `scripts/build_report.py` that writes one self-contained, JavaScript-free `report/presentation_report.html` (Git-ignored; the work log `report/index.html` is untouched).
- Four A4 `<section class="page">` elements of fixed size with print CSS (`@page` A4, no margins, forced page breaks), so the printed result is four pages by construction; overflow is detected by a browser measurement (`build_report.py measure`: per-page content height against page height, plus printed-PDF page count) and by static offline checks that run in CI.
- Page 1 motivation slot and problem statement; page 2 approach (architecture and run-flow diagrams, sandbox and scoring integrity, reproducibility, budget ledger); page 3 results and statistics (the four chart sets: outcome comparison, failure labels with the two trace stories, efficiency and cost, engineering statistics); page 4 limits, lessons learned, conclusions slot, and the references/evidence section (run IDs, bundle digests, repo document links).
- Numbers only through template references into `summary.json`; figures, diagrams, captions, alt text, logo and screenshots by manifest id; one `Figure N` numbering assigned by the builder in order of appearance, with in-text references resolved from the same numbering.
- Pending screenshots and an unset date render as visible, deliberate placeholders; user slots render as visible placeholder boxes until `presentation/report/user_text.toml` is filled; a release flag fails the build while any placeholder remains.
- Screen-only navigation (sticky page links) that is removed in print.
- Add `docs/presentation_report.md` (build, print, check), offline tests with fixtures, one CI step, and small additive edits to shared files (listed in `design.md`).

No evaluator, agent, grading, ledger or tracking behaviour changes; nothing under `src/` changes; no model call, credential or ledger read.

## Capabilities

### New Capabilities

- `presentation-report`: the four-page printable HTML report: structure, evidence-bound content, user slots, pending handling, figure numbering, screen navigation, print enforcement, overflow detection, and the offline checks.

### Modified Capabilities

None. `presentation-evidence` (change `add-presentation-evidence`), `architecture-diagrams`, `local-work-log` and `project-delivery` are consumed, not changed.

## Impact

New: `presentation/report/{template.html,report.css,user_text.toml}`, `scripts/build_report.py`, `tests/test_presentation_report.py` with `tests/fixtures/presentation_report/`, `docs/presentation_report.md`. Generated and Git-ignored: `report/presentation_report.html` (and an optional `report/presentation_report.pdf`). Small edits to `README.md`, `docs/progress.md`, `docs/work_log.toml`, `.github/workflows/ci.yml` (one offline step). No new runtime or third-party dependency (standard library, plus the already-present `scripts/build_work_log.py` sanitizer loaded by path).

## Dependencies and milestone

Blocked by `add-presentation-evidence` being merged (manifest, `summary.json`, charts, logo). Tests use fixtures, so the code can be written before, but the real build and the printed-page measurement happen after that merge. Independent of `add-presentation-deck` except for the shared files and the optional shared user-text file (open question in `design.md`). Delivery polish: the `project-delivery` cut order applies; this never reduces benchmark, trials, denominators, probes, CI or MLflow records.

## Completion evidence

Offline tests and `build_report.py check` pass in CI without bundles or a browser. On the user's laptop, `build_report.py measure` reports four printed pages and every page within its box (recorded in `docs/progress.md` with the browser version); the coordinator opens the page in the Orca browser and in print preview. User slots, the date and the screenshots stay visibly unfilled until the user and the coordinator supply them; that is not a failure of this change, and a release build (`--require-user-text`) is the user's last step.
