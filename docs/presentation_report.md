# Four-page printable report

The report is one self-contained HTML file, `report/presentation_report.html`, built from committed sources and the shared presentation evidence. It has four A4 pages in the structure of the talk: page 1 the title, the motivation slot and the problem statement; page 2 the approach (pipeline overview and trust-boundary diagrams, scoring integrity, reproducibility, the budget ledger, the experiment design); page 3 the results and statistics; page 4 the limits, the lessons learned, the conclusions slot and the references and evidence. The prompt comparison is a worked example with its limits; the report makes no claim of a measured gain.

## Build and check

```sh
.venv/bin/python scripts/build_report.py build                      # write report/presentation_report.html
.venv/bin/python scripts/build_report.py check                      # offline checks, writes nothing
.venv/bin/python scripts/build_report.py build --require-user-text  # release build: fails while a slot, the date or a used screenshot is unfilled
.venv/bin/python scripts/build_report.py measure --pdf report/presentation_report.pdf   # needs Chrome or Chromium
```

`report/` is Git-ignored, and `report/index.html` (the work log) is neither read nor changed. The build uses only the standard library and loads `scripts/build_work_log.py` by path for its SVG validators; it reads no credential, no bundle and no ledger and makes no network call.

## Sources

| File | Role |
| --- | --- |
| `presentation/report/template.html` | Hand-written four-page skeleton and factual prose. Prose contains no numbers. |
| `presentation/report/report.css` | Screen sheets and print rules. |
| `presentation/user_text.toml` | The user's own words (`motivation`, `takeaways`), `report` keys. Created by the evidence change; the report only reads it. |
| `presentation/manifest.json`, `presentation/evidence/summary.json` | Figures, captions, alt text, logo, title and every number. |

Template directives (the closed set, an unknown id, key or directive fails the build): `{{val:PATH|format}}` reads a number from `summary.json` (formats `int`, `id`, `chf`, `chf4`, `ratio`, `pct`, `ratiopct`, `ms`; `ratio` and `pct` read `count`, `of` and `rate` from the same object and print one decimal), `{{fig:ID}}` and `{{shot:ID}}` place a manifest figure, diagram or screenshot, `{{table:NAME}}` renders one of four summary tables (`per-task`, `resources`, `ci-runs`, `changes`), `{{ref:ID}}` is the figure or table number, `{{logo}}`, `{{title:FIELD}}`, `{{user:SLOT}}`, `{{limits}}`, `{{evidence_table}}`, `{{link:index|demo}}`, `{{nav}}` and `{{footer:N}}`. Figures and tables are numbered by order of appearance; captions and alt text are the manifest's, unchanged.

To change what page 3 shows, edit the `{{fig:...}}` list in the template: charts must be compact variants from the manifest (rendered at 88 mm, at least 7.5 pt of text), and anything not charted can be a `{{table:...}}`.

## Your text, the date and pending items

Nothing here is drafted for you. Write the `report` keys of `[motivation]` and `[takeaways]` in `presentation/user_text.toml` (at most 500 characters each so the box keeps the page at four) and set the title date in the manifest source. Until then the report shows bordered placeholder boxes, and a screenshot that is pending, or whose file is absent, shows a placeholder naming what it will show and its owner. The release build fails while any of these remains. Avoid the words improvement and breakthrough in your own text: the check rejects them outside quotations, and "no measured gain" says the same thing.

## Exactly four pages: how it is enforced and checked

Each page is a 296 mm box (one millimetre under the sheet, so it never spills a blank fifth page), `@page { size: A4; margin: 0 }`, a forced break after each page, and `overflow: hidden`. Because overflow is hidden, a too-long page loses content instead of adding a page, so a page count of four is necessary but never sufficient.

- `check` (offline, no browser; runs anywhere): exactly four page sections, no script, handler or external reference, `lang` and `<title>`, a heading on every page, contiguous figure numbers, resolved references, the print block restricted to rules that do not change geometry or type (the screen measurement therefore stands for the printed layout), every font size in pt and at least 7.5 pt, text colours from the `--text` tokens with contrast of at least 4.5:1, compact charts rendered wide enough for 7.5 pt (viewBox arithmetic), the digit lint (no typed number in the template prose; whole-token allowlist `DIGIT_ALLOWLIST` in the script), the framing lint (the words improvement and breakthrough only inside verbatim quotations of the evidence and the manifest, user slots included), the user-text length limits, and a static page-height estimate (exact figure heights, fixed box heights, table rows, prose by characters) against 94 percent of the page body.
- `measure` (local, needs Chrome or Chromium, `--browser` or `$REPORT_BROWSER`): loads a throwaway copy with a measuring script injected (the report itself has no script), compares each page body's content height with its box (clipped content fails, more than 94 percent warns), prints to PDF and counts pages from the page tree (an unreadable page count is its own failure). No browser is exit status 3 with "SKIPPED", never a pass. It prints browser version, per-page fill and the page count for pasting into `docs/progress.md`. Pagination depends on the viewer's font stack (the page uses the system font on purpose), so it is recorded evidence for one browser, not a guarantee for every viewer.
- The static estimate is a guard, calibrated against `measure`. Until that has happened `BUDGETS["calibrated_against"]` starts with `UNMEASURED` and `check` says so; an empty value fails.

Print it yourself: open the file in the browser, print, destination "Save as PDF", paper A4, margins None, background graphics on, headers and footers off. Expected: four pages, no navigation bar. The navigation (sticky page links and previous/next links) exists on screen only.

## Known limits

- Only figures that print at 7.5 pt or more are placed: the compact charts (88 mm) and the pipeline-overview and trust-boundary diagrams (128 mm). The dense draw.io diagrams (`docs/*.drawio.svg`) print at 1 to 3 pt at any width a page allows, so the report lists them by path only; their text twins hold the same content. `check` fails if a figure, a draw.io export included, would print below 7.5 pt.
- The static estimate and the 94 percent headroom are not a substitute for `measure` and a look at the print preview.
- `measure` starts the browser in its own process group with a 60 s hard timeout; on a timeout it kills the group and reports that nothing was measured.
