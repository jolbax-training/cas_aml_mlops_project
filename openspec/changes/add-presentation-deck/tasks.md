# Tasks

Planned work only; nothing here is implemented. Tasks marked (coordinator) or (user) stay unchecked in the implementation phase until that person acts. Depends on `add-presentation-evidence` being merged.

## 1. Sources and builder

- [x] 1.1 Read the merged `presentation/manifest.json`, `summary.json` and `presentation/user_text.toml`; record the exact figure, diagram, screenshot and asset ids and the summary key paths each slide needs as a short table in design.md (not in `slides.toml`, which task 1.3 alone writes); report any missing id, key or logo `alt` to the coordinator instead of adding it.
- [x] 1.2 Add `scripts/build_deck.py` (`build`, `--check`, `--strict`): load sources, enforce the 13-slide ordered outline and the 15.0-minute sum (integer tenths), resolve `{{summary:...}}` and `{{fmt:<format>:...}}` references (formats `int`, `ratio`, `pct1`, `chf4` with footnote), apply the bare-number lint with its allow-list, compute each figure's effective chart font size per layout (floor 18 px), load `scripts/build_work_log.py` by path for the SVG validators, read the shared `user_text.toml`, place figures by manifest id with manifest caption and alt, fail on unknown id, empty alt, unresolved reference, literal-number lint hit.
- [x] 1.3 Write `presentation/deck/slides.toml` with the approved titles, minutes and factual content for the 13 slides (design decision 3); write `notes.toml` with factual notes and source references per slide, including the seven limits on slide 11; the deck owns no user-text file.
- [x] 1.4 Add `deck.css`: 16:9 letterboxed layout, font floor, contrast tokens, print rules (one slide per landscape page, no chrome, no notes), visible placeholder styles, no animation.
- [x] 1.5 Add `deck.js` navigation only (arrows, Space, PageUp/PageDown, Home, End, N notes, F fullscreen, hash position, `n / 13` counter); readable stacked layout without JavaScript.
- [x] 1.6 Inline assets (images as data URIs with manifest alt; SVG element/script/external-reference checks), pending-screenshot placeholders, links to report, demo player and repository with "(not built)" fallback, atomic write of `report/deck.html` and `report/deck_notes.html`, size report.

## 2. Tests and wiring

- [x] 2.1 Add `tests/test_build_deck.py` (building from the committed sources copied to a scratch root) covering every item of design decision 11, offline, no network, Podman, bundles or ledger.
- [x] 2.2 Add the `build_deck.py --check` step to the CI `offline` job and name it in the workflow header comment; add the README subsection and the `offline` row of the README CI table; add the `docs/progress.md` entry and any `docs/work_log.toml` registration; keep edits small and list them for the merge with `add-presentation-report`.
- [x] 2.3 Run `openspec validate add-presentation-deck --strict`, the full offline test suite, `build_deck.py --check`, and a build; confirm `report/index.html` is unchanged by a build; document and exercise the build order (player, report, work log, deck) and check that `--check` names the links that would fall back.

## 3. Review and rehearsal

- [ ] 3.1 (user) Write the Motivation and Takeaways `deck` texts into the shared `presentation/user_text.toml` and set the date in the manifest source; run `build_deck.py --strict`. The worker never writes these texts.
- [ ] 3.2 (coordinator) Open `report/deck.html` in the Orca browser at 1920x1080: step through all 13 slides with the keyboard, check the counter, N notes and fullscreen, judge legibility of each chart and diagram at slide size, (optional, only if the Orca browser can print; otherwise the user prints and reports the page count) print to PDF, confirm 13 pages and print `deck_notes.html`; record findings in `docs/progress.md`.
- [ ] 3.3 (coordinator) After screenshots exist, rebuild and confirm no pending boxes remain; run one timed rehearsal against the per-slide minutes.
