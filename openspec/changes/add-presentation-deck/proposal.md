# Proposal

## Why

The user gives a 15-minute talk to classmates and examiners on "a trustworthy, reproducible, budget-safe evaluation pipeline for a coding agent". The project and its evidence are complete, but there is no talk material. A deck built from committed sources and the shared evidence interface keeps every number traceable and keeps the user's own words (motivation, takeaways) the user's.

## What Changes

- Add a self-contained 13-slide HTML deck, built offline by a Python script from committed sources into the Git-ignored `report/deck.html`. Slide order, titles and minutes are exactly the user-approved outline (sum 15.0 minutes, checked by the build).
- Add editable sources under `presentation/deck/`: slide definitions, factual speaker notes, the stylesheet and navigation script. The user's slot texts for slides 2 and 12 come from the shared `presentation/user_text.toml` created by `add-presentation-evidence`; the deck owns no user-text file.
- Add keyboard navigation, a slide counter, a 16:9 fullscreen layout with minimum font sizes, one-slide-per-page print/PDF, speaker notes (toggle on screen and a separate notes print page), accessible figures, and visible placeholders for the user slots, the date and any `pending` screenshot.
- Consume `presentation/manifest.json` and `summary.json` from `add-presentation-evidence`; numbers, captions and alt text are never typed in the deck.
- Small additive edits to shared files (README, `docs/progress.md`, `docs/work_log.toml`, CI offline job), listed in design.md.
- No live demo, no new experiment, no paid call, no change under `src/`, no JavaScript library.

## Capabilities

### New Capabilities
- `presentation-deck`: the offline 15-minute HTML talk, its sources, user slots, timing check, navigation, print layout, speaker notes, accessibility and honest framing of the prompt comparison.

### Modified Capabilities

## Impact

New: `presentation/deck/*`, `scripts/build_deck.py`, `tests/test_build_deck.py`, `tests/fixtures/deck/`. Edited additively: `README.md`, `docs/progress.md`, `docs/work_log.toml`, `.github/workflows/ci.yml`. Depends on `add-presentation-evidence` being merged first (manifest, summary, charts, logo); the sibling `add-presentation-report` shares the manifest. Fits the delivery phase of docs/project_spec.md; completion evidence is a passing build `--check`, offline tests, and a coordinator rehearsal review.
