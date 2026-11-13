# Presentation deck: the 15-minute talk

A self-contained HTML slide deck, built offline from committed sources and the [shared presentation evidence](presentation_evidence.md). It has 13 slides and 15.0 minutes, exactly the outline the user approved; the build fails if a slide is added, dropped, renamed or reordered, or if the minutes stop summing to 15.0. The prompt comparison is shown as a worked example with its limits, never as an improvement.

## Build

```sh
.venv/bin/python scripts/build_deck.py            # writes report/deck.html and report/deck_notes.html (Git-ignored)
.venv/bin/python scripts/build_deck.py --check    # validate everything, write nothing (also runs in CI)
.venv/bin/python scripts/build_deck.py --strict   # --check, and fail on unfilled user slots or pending screenshots
open report/deck.html                             # macOS; works from file://, no server, no network
```

Build order, so the links on the last slide find their targets: the recording player (`report/demo.html`), the report (`report/presentation_report.html`), the work log (`report/index.html`), then the deck. A missing target is shown as text marked "(not built)" and is not an error; the build prints which links fell back.

## Sources

| File | Edit it to |
| --- | --- |
| `presentation/user_text.toml` | write the Motivation (slide 2) and Takeaways (slide 12) in your own words, `deck` key, and the title-slide date under `[title]` (`date = "2026-12-01"` or free text, one line, at most 40 characters) |
| `presentation/deck/slides.toml` | change the factual text of a slide; numbers are `{{summary:path}}` or `{{fmt:int\|pct1\|ratio\|chf4:path}}` references into `presentation/evidence/summary.json` |
| `presentation/deck/notes.toml` | change the factual speaker notes |
| `presentation/deck/deck.css`, `deck.js` | layout, print rules and the navigation script |

The deck never writes `user_text.toml` and drafts none of your words: an empty slot is a dashed yellow box saying what to edit, and the title slide shows `[DATE: fill in]` until you write the date: open `presentation/user_text.toml` and set `date` in the `[title]` table (one line, at most 40 characters). `build_deck.py --strict` fails while the date or a slot is empty. Pending screenshots are boxes labelled `SCREENSHOT PENDING`.

## Using it

Arrow keys, Space and PageUp/PageDown move; Home and End jump; `N` shows the speaker notes of the current slide (with its minutes and the running total); `F` goes fullscreen. The counter shows `n / 13`. Without JavaScript all slides are shown one under the other. Printing to PDF from a Chromium-based browser gives one landscape 16:9 slide per page with no notes; `report/deck_notes.html` prints the notes, one slide per page.

## Rules the build enforces

- Every number is read from `summary.json`; a literal number, CHF amount or ratio in slide or note text fails, except the tokens allowed with a reason in `slides.toml`. The ledger total is shown through `chf4` (four decimals) with the full quoted value in a footnote.
- Figures, diagrams, screenshots and the logo are placed by manifest id with the manifest's caption and alt text; an unknown id or an empty alt fails.
- The words "improvement" and "breakthrough" may not appear in the deck's own text, and evidence captions may use them only to deny the claim.
- Each chart's effective text size (its minimum font units scaled to the width it is shown at, with 1cqw = 19.2 px on a 1920 px slide) must be at least 18 px; a screenshot can be shown as a cropped detail (`[crop.<id>]` in `slides.toml`); slide text is at least 20 px and body text at least 28 px.
- The output loads nothing external and contains no home path or key-like string.

## Not checked by tests

The look and legibility of the slides on a projector (the build computes chart and diagram text sizes but cannot see them), the full `docs/` architecture diagrams (not on the slides; the report and the repository carry them), the look of the slides and the page count when printed are reviewed by hand in a browser.
