# Tasks

Planned work only; nothing here is implemented. Tasks marked (coordinator) or (user) stay unchecked in the implementation phase until that person acts. Depends on `add-presentation-evidence` being merged.

## 1. Sources and builder

- [ ] 1.1 Read the merged `presentation/manifest.json` and `summary.json`; record the exact ids and key paths used by each slide in `presentation/deck/slides.toml`; list any missing id or key as an open question instead of adding it.
- [ ] 1.2 Add `scripts/build_deck.py` (`build`, `--check`, `--strict`): load sources, enforce the 13-slide ordered outline and the 15.0-minute sum (integer tenths), resolve `{{summary:...}}` references, place figures by manifest id with manifest caption and alt, fail on unknown id, empty alt, unresolved reference, literal-number lint hit.
- [ ] 1.3 Write `presentation/deck/slides.toml` with the approved titles, minutes and factual content for the 13 slides (design decision 3); write `notes.toml` with factual notes and source references per slide, including the seven limits on slide 11; leave `user_text.toml` slots empty.
- [ ] 1.4 Add `deck.css`: 16:9 letterboxed layout, font floor, contrast tokens, print rules (one slide per landscape page, no chrome, no notes), visible placeholder styles, no animation.
- [ ] 1.5 Add `deck.js` navigation only (arrows, Space, PageUp/PageDown, Home, End, N notes, F fullscreen, hash position, `n / 13` counter); readable stacked layout without JavaScript.
- [ ] 1.6 Inline assets (images as data URIs with manifest alt; SVG element/script/external-reference checks), pending-screenshot placeholders, links to report, demo player and repository with "(not built)" fallback, atomic write of `report/deck.html` and `report/deck_notes.html`, size report.

## 2. Tests and wiring

- [ ] 2.1 Add `tests/test_build_deck.py` and `tests/fixtures/deck/` covering every item of design decision 11, offline, no network, Podman, bundles or ledger.
- [ ] 2.2 Add the `build_deck.py --check` step to the CI `offline` job; add the README subsection; add the `docs/progress.md` entry and any `docs/work_log.toml` registration; keep edits small and list them for the merge with `add-presentation-report`.
- [ ] 2.3 Run `openspec validate add-presentation-deck --strict`, the full offline test suite, `build_deck.py --check`, and a build; confirm `report/index.html` is unchanged by a build.

## 3. Review and rehearsal

- [ ] 3.1 (user) Write the Motivation and Takeaways texts into `presentation/deck/user_text.toml` and set the date in the manifest source; run `build_deck.py --strict`. The worker never writes these texts.
- [ ] 3.2 (coordinator) Open `report/deck.html` in the Orca browser at 1920x1080: step through all 13 slides with the keyboard, check the counter, N notes and fullscreen, judge legibility of each chart and diagram at slide size, print to PDF and confirm 13 pages, print `deck_notes.html`; record findings in `docs/progress.md`.
- [ ] 3.3 (coordinator) After screenshots exist, rebuild and confirm no pending boxes remain; run one timed rehearsal against the per-slide minutes.
