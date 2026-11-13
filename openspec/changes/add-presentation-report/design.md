# Design

## Context

`add-presentation-evidence` (consumed, read-only here) provides `presentation/manifest.json` (schema_version 1), `presentation/evidence/summary.json` (including `protocol` facts, `documents` quote rows and `limits`), thirteen full-size chart SVGs (`viewBox 0 0 960 540`, `min_render_mm: 160`) plus, by decision D1, compact half-width variants with their own manifest ids linked to the full-size chart (`variant: "compact"`, `viewBox 0 0 480 270`, rendered no narrower than 78 mm, minimum font 17 units), four reused `docs/*.drawio.svg` diagrams (ids like `diagram-architecture-logical`, `diagram-run-flow-sequence`), coordinator-owned screenshots (ids like `shot-...`, possibly `pending`), the ZHAW logo with alt text on every manifest asset, the shared user-text file `presentation/user_text.toml` (with a manifest `user_text` status per slot) and a null date with a visible placeholder. Ids and field names below are the ones the evidence change builds today; they are bound at task 4.1 against the merged change, and a name that does not exist fails the build and the tests. This change does not define or alter any of them. `scripts/build_work_log.py` is the precedent: standalone offline script, `--check`, tests load it by path, and it already contains the SVG allowlist validator and draw.io sanitizer. This change turns that material into the four-page report. Accepted user decisions in the shared context are binding: plain HTML/CSS, no JavaScript libraries, nothing vendored, no network at viewing time, works from `file://`, generated HTML in the Git-ignored `report/`, honest framing, user-authored motivation/interpretation/takeaways, no invented numbers.

## Goals / Non-Goals

**Goals:** exactly four printed A4 pages by construction and by measurement; every number from `summary.json`; every figure by manifest id with manifest caption and alt; visible placeholders (user slots, date, pending screenshots); screen navigation that vanishes in print; offline deterministic checks that run in CI.

**Non-Goals:** drafting the user's motivation, interpretation or takeaways; new evidence, charts or experiments; changes to `src/`, the work log, or the evidence change's interface; a JavaScript framework or any dependency; hosting; a CI browser job.

## Decisions

### 1. One file, four fixed sections (alternative rejected: four files)

`report/presentation_report.html` is a single self-contained file: stylesheet, SVGs, logo and screenshots inlined (SVG as markup, JPG/PNG as `data:` URIs), so it can be handed in or moved and still opens from `file://` with no network. Four files (one per page) were rejected: printing needs one PDF, four print jobs would have to be merged by hand, and cross-page figure numbering and navigation would span files. The name `presentation_report.html` keeps `report/index.html` (the work log from `build_work_log.py`) untouched; the builder writes only its own file and never cleans the directory.

Structure:

```html
<nav class="screen-only">Page 1 .. Page 4 (anchor links)</nav>
<main>
  <section class="page" id="page-1">header | content | footer "n / 4"</section> ... id="page-4"
</main>
```

Print CSS:

```css
@page { size: A4; margin: 0 }
.page { box-sizing: border-box; width: 210mm; height: 296mm; padding: 12mm 14mm;
        overflow: hidden; break-after: page; break-inside: avoid; }
.page:last-child { break-after: auto }
.screen-only { display: none !important }  /* inside @media print */
body { -webkit-print-color-adjust: exact; print-color-adjust: exact }
```

The page box is 296 mm, not 297 mm: a box exactly as tall as the sheet can spill a sub-pixel onto a fifth, blank page in Chromium and Firefox, and a one-millimetre margin removes that failure without any visible difference. `overflow: hidden` makes every page a hard box, so a too-long page loses content rather than creating a fifth page. That would hide the problem from a page-count check alone, which is why overflow detection is a separate measurement (decision 4) and why a page count of four is necessary but never sufficient. The `<nav>` sits outside `<main>` (so it cannot push page 1 down on screen) and the document declares `lang="en"` and a `<title>`. On screen the sections render as stacked sheets (max width 210 mm, shadow, centred); on narrow screens the sheet scrolls horizontally rather than reflowing, so the screen layout stays the print layout. That claim is enforced, not assumed: the browser height measurement runs in screen media, so `check` requires the `@media print` block of `report.css` to contain only the `@page` rule, the `.page` break rules, `print-color-adjust` and the `.screen-only` hide rule, nothing that changes box geometry or type size (decision 4).

### 2. Sources, template directives, and what is committed

```
presentation/report/template.html   committed; hand-written four-page skeleton and prose
presentation/report/report.css      committed; screen + print rules
scripts/build_report.py             build | check | measure [--pdf PATH]
tests/test_presentation_report.py, tests/fixtures/presentation_report/
docs/presentation_report.md         build, print and check instructions
report/presentation_report.html     generated, Git-ignored (spec line 175; `/report/` is already ignored)
report/presentation_report.pdf      optional, generated by `measure --pdf`, Git-ignored
```

The template is plain HTML with a small, closed set of directives resolved by the builder (a missing id, key or slot is a build error, never an empty string):

| Directive | Resolves to |
| --- | --- |
| `{{val:PATH}}` with an optional format suffix | a value read from `summary.json` by dotted path (including `protocol.tasks`, `protocol.trials_per_task`, `protocol.planned_trials_per_variant`, `protocol.planned_trials_total`, `protocol.ceiling_chf`, `protocol.checkpoint_chf`, `protocol.ledger_total_chf`, `protocol.probes_passed`, `protocol.probe_categories`). Formats: `int`, `id`, `chf` (the summary's own CHF string, never recomputed), `ratio` and `pct`, which read a numerator and its denominator as a pair of fields of the same summary object (the form `ratio:PATH` names the object) and format with one decimal exactly as the comparison output and `docs/prompt_comparison.md` do (`27/30 (90.0%)`); a test reproduces the documented strings from the fixture. Nothing else. |
| `{{fig:ID}}` | the manifest figure or diagram by id (compact chart ids on page 3), its `Figure N` label and manifest caption. Charts keep their own `role="img"`, `title`, `desc` and `aria-labelledby`, with ids prefixed per figure; diagrams go through `sanitize_drawio_svg(text, id, title, description)` with the manifest caption as title and the manifest alt as description. Both pass `validate_svg` |
| `{{shot:ID}}` | the screenshot as `<img>` with manifest alt and caption when `status` is `present` and the file exists; otherwise a visible dashed box "Screenshot pending (owner: coordinator): <shows>" |
| `{{ref:ID}}` | the text `Figure N` for the same numbering, so a cross-reference cannot drift from the figure |
| `{{logo}}` | the manifest `zhaw-logo` asset inlined as a `data:` URI after its recorded SHA-256 is re-verified, with the manifest asset's `alt` text |
| `{{title:author\|course\|date\|headline}}` | manifest title block; a null date renders the manifest `date_placeholder` in a visible highlighted box |
| `{{user:motivation}}`, `{{user:takeaways}}` | the `report` key of that slot in the shared `presentation/user_text.toml`, HTML-escaped, paragraphs split on blank lines; when empty, a visible placeholder box with a dashed border and text (so it survives printing without background graphics) naming the slot and `presentation/user_text.toml` |
| `{{limits}}` | the seven limits (`limits.items`, short labels) each joined with its verbatim quote row from the summary's `documents` rows, and the non-claim (`limits.non_claim`, `limits.statement`); every verbatim quotation is emitted as `<q class="quoted" data-source="file">` |
| `{{evidence_table}}` | run IDs, full bundle digests printed once each on a wrapping monospace line (the short form is used in prose; nothing is only in a `title` attribute), prompt hashes, MLflow run IDs, completeness, from `summary.provenance.runs` |

Prose in the template is factual description from repo documents (what the sandbox, ledger and bundles do) and contains no digits except through directives; page numbers and `Figure N` are generated. The digits lint runs on the template prose only (not on `report.css`, not on the user's text, not on resolved output) and matches whole tokens against an allowlist kept in `build_report.py` next to the page budgets (for example `A4`, `SHA-256`, `Python`-version tokens), which the coordinator reviews at task 4.1. A second lint covers framing: the words "improvement" and "breakthrough" are forbidden everywhere in the output, the user's slot text included (the failure names the slot, and "no measured gain" is the allowed wording), except inside `<q class="quoted">` elements. The `quoted` marker is emitted only by the `{{limits}}` and quote directives (a quoted limit legitimately ends "rather than a general improvement"), and a test fails if the template contains the marker itself. This is the discipline the evidence change applies to charts, applied to prose.

Why a hand-written template with a closed directive set rather than a Markdown pipeline: layout of four fixed boxes, figure placement and per-page budgets are layout decisions that Markdown cannot express, and the directive set is small enough to test exhaustively. The builder is expected to be about 400 lines of standard-library Python plus `scripts/build_work_log.py` loaded by path for `validate_svg` and `sanitize_drawio_svg` (a dependency on a script, not on `src/`).

Rejected: building from the existing `report/index.html`; two separate sources of numbers; client-side JavaScript to fill values (the page must work printed from a viewer with scripting disabled).

### 3. Content plan per page (structure mirrors the approved deck outline)

| Page | Content | Sources |
| --- | --- | --- |
| 1 | Header with logo, title, author, course, date; motivation USER SLOT; problem statement (unsafe candidate code, flaky or hidden cost, irreproducible results, small-sample claims) with the headline sentence; one-paragraph roadmap | manifest title, `user_text.toml`, factual prose |
| 2 | Approach: architecture figure (`diagram-architecture-logical`) and run-flow figure (`diagram-run-flow-sequence` or the activity diagram, chosen after seeing both at print width; or selected by manifest `role`); scoring integrity (sandbox, trust boundary, hidden checks, what the isolation probes cover, from `docs/threat_model.md`); reproducibility (bundles, digests, grading replay, completeness check, MLflow traces, one screenshot figure when present); budget-safe paid calls (reserve-before-send, ceiling, total spent from `summary.protocol.ledger_total_chf`, ceiling and checkpoint from `summary.protocol`); experiment design (tasks, trials, one prompt sentence changed) | diagrams, `summary.provenance`, `summary.protocol` (tasks, trials, planned trials, ceiling, checkpoint, ledger total, probe categories), prose from reviewed docs without numbers |
| 3 | Results and statistics, one block per chart set (a outcome comparison, b failure labels plus both trace stories, c efficiency and cost, d engineering: tests, CI, archived changes), each figure with manifest caption and a one-sentence reading that only restates the plotted values | charts by id, `summary.comparison/efficiency/stories/engineering` |
| 4 | Limits (all seven, each quoted from its document row) and the non-claim; lessons learned (MLflow big-integer bug, smoke forcing, from `docs/progress.md` and `docs/smoke_evidence.md`); conclusions/takeaways USER SLOT (interpretation); references/evidence section; footer with build provenance (summary commit and script hash) | `summary.limits`, `user_text.toml`, `evidence_table`, repo document links |

The references/evidence section on page 4 gives, as visible text and not only as links (links are dead on paper): the two comparison run IDs and the forced-pass smoke run ID with bundle digests and MLflow run IDs, and the repository paths of the documents the report relies on (`docs/prompt_comparison.md`, `docs/comparison_evidence.md`, `docs/smoke_evidence.md`, `docs/ci_evidence.md`, `docs/threat_model.md`, `docs/demo.md`, `docs/evaluation_design_guide.md`, `docs/progress.md`). On screen each is also a relative link (`../docs/...`, resolved from `report/`, valid in the checkout). The link to the work log (`index.html`) and to the recorded demo player (`demo.html`) are relative sibling links shown on screen with their path printed; a missing sibling is a non-fatal builder note (those files are generated and Git-ignored), never an error, and the link text says which script builds it.

Figure budget (decision D1, compact charts plus tables): page 3 embeds about eight compact half-width charts, by manifest id of the compact variants the evidence change defines (expected names `outcome-overview-compact`, `outcome-by-category-compact`, `failure-labels-compact`, `story-lists-02-compact`, `story-strings-01-compact`, `efficiency-calls-compact`, `cost-charged-reserved-compact`, `engineering-tests-compact`; bound at task 4.1, never redefined here). They cover the four sets: (a) outcome comparison, (b) failure labels with both trace stories, (c) efficiency and cost, (d) engineering statistics. Figures are numbered `Figure 1..N` by appearance: the two diagrams and an optional screenshot on page 2, then the page 3 charts. The remaining figures (`outcome-by-task`, tokens, latency, CI runs, archived changes) appear as compact HTML tables from `summary.json` (for example per-task successes, token totals, latency totals with the evidence caption wording "measured once, different times, no attribution", CI runs with outcomes, archived changes by date). The selection is a list in the template, so changing it is an edit, not code.

Static print-legibility rule (spec "Print legibility"): for each inlined chart, `min_font_units * rendered_width_mm / viewBox_width >= 2.646 mm` (7.5 pt), with the rendered width taken from the figure's CSS class in `report.css`; every `font-size` in `report.css` is at least 7.5 pt (body about 10 pt, captions and source footnotes not below 7.5 pt) and every text colour token has contrast at least 4.5:1 on its background (a few lines of standard-library arithmetic). A compact chart at 78 mm with 17 units gives about 7.8 pt, so two columns fit within the 182 mm text width.

Space arithmetic, stated now so the selection is not a surprise: two columns of about 88 mm give charts about 50 mm tall plus a manifest caption, so four rows of charts take most of a 272 mm page body before tables and headings. The static estimator (decision 4) and the first real measurement decide whether page 3 carries eight charts or six, with the omitted ones turned into tables; the four chart sets stay covered either way, and "about 8" is the target.

### 4. Enforcing and checking exactly four pages

Two layers, because "four sections exist" is trivially true and "no section clips content" is the real risk.

1. **Offline static checks (CI, no browser)**: `build_report.py check` builds in memory and asserts: exactly four `section.page` with ids `page-1..4`; no `<script>`, no event-handler attribute, no external `http(s)`/`//` reference, no `url(` in CSS beyond `data:`; every directive resolved; unique ids after inlining (each inlined SVG has its ids prefixed with its figure id so two draw.io diagrams cannot collide); figure numbers contiguous in document order; every `Figure N` reference resolves; the print CSS contains `@page` A4, `break-after: page` on `.page`, the 296 mm box and the `screen-only` hide rule (a regression test against an accidental edit); a per-page **content budget**: the static estimate sums exact heights (each figure's rendered width times its viewBox aspect, fixed slot boxes, tables from their row counts, header and footer) and estimates prose from characters per line and line height, so it is a real lower bound on used height, and the same 94 percent headroom rule applies offline; budgets ship as explicit constants with a `calibrated_against` note (browser, version, date) and `check` fails with "budgets not calibrated" while that note is empty, so the CI guard can never pass vacuously; the print-legibility rule of decision 3; the print-block restriction (only `@page`, the `.page` break rules, `print-color-adjust` and the `.screen-only` hide rule, so the screen measurement stands for the print layout); `lang`, `<title>` and a heading outline per page; the placeholder/slot report (below); the claims and digits lints of decision 2. Only the browser measurement is evidence of four printed pages; the static guard is a regression net. These are deterministic and run in the existing CI `offline` group, which has no browser.
2. **Browser measurement (local, recorded by hand)**: `build_report.py measure` locates a Chromium-family browser (`--browser PATH`, else `$REPORT_BROWSER`, else known macOS/Linux paths; absent browser exits with a distinct code 3 and the message "SKIPPED: no browser", never a silent pass) and does two things on a throwaway copy of the built page in a temporary directory: (a) loads a copy with a small measuring script injected (the shipped report has no JavaScript) via headless `--dump-dom` with a virtual-time budget; the script writes, per page, `scrollHeight`, `clientHeight` and the lowest bottom edge of any child, and the builder fails if any page has `scrollHeight > clientHeight` (clipped content, because of `overflow: hidden`) and warns if the used height exceeds 94% (headroom for another font stack or browser); (b) prints to PDF (`--print-to-pdf --no-pdf-header-footer`, A4 from `@page`) and counts pages from the PDF page tree using the standard library: it matches `/Type\s*/Page\b` (so `/Pages` does not match) and reads the root `/Pages` `/Count` separately; if the two disagree or neither is found (for example with compressed object streams) it fails with "could not determine page count", distinct from "page count is N, not four", and otherwise fails unless the count is four. It prints a table (page, used mm, available mm, percent) so the result can be pasted into `docs/progress.md` with the browser version. `measure --pdf PATH` keeps the PDF the user can hand in; Git-ignored.

Why no browser job in CI: the page uses the system font stack on purpose (nothing vendored, no web fonts), so pagination can differ across runners; a CI browser check would be flaky evidence or would pin a font we deliberately do not ship. The headroom rule plus the local measurement is the honest evidence; the static budget is the always-on guard. Why not per-page HTML files with page counting per file: it would still need the same overflow measurement, and it multiplies print steps. The headroom rule plus calibration means the CI step is added only after the first real measurement (task order).

Manual print recipe (also in `docs/presentation_report.md`): open the file, print, destination "Save as PDF", paper A4, margins None, background graphics on, headers and footers off; the expected result is four pages with no navigation bar.

### 5. Screen navigation that disappears in print

A `<nav class="screen-only">` with anchors `#page-1..#page-4`, sticky at the top, with the current-page highlight done by `:target` (no JavaScript), plus per-page "previous | next" links in each page footer inside a `screen-only` span. Both are hidden by `@media print`; a test asserts the hide rule and that no navigation text appears in the print-visible DOM of a build by checking the class on every nav element. The footer page counter "n / 4" is generated and stays in print.

### 6. User slots, date, pending items

The shared `presentation/user_text.toml` (created by `add-presentation-evidence`, edited by the user, never by tools) holds the slots `motivation` and `takeaways`, each with a `deck` (short) and a `report` (long) key. This change reads only the `report` keys, creates no user-text file of its own, and may use the manifest's per-slot `empty`/`filled` status for the placeholder report. Empty slots render as unmistakable boxes with a dashed border and text ("YOUR TEXT HERE: why evaluating coding agents matters to you; edit the `report.motivation` key of presentation/user_text.toml"), so they survive printing without background graphics; filled slots render the text in the normal body style with no marker. `build_report.py build --require-user-text` (the release build) fails while any `report` slot, the date, or any screenshot used by the report is unfilled; the default build succeeds and lists them in a "placeholders" summary line, and `check` reports the same counts. A slot box has a reserved minimum and maximum height so an empty and a filled slot occupy the same space; a `report` text longer than the maximum fails `check` with the slot name and the allowed length, so the user's text cannot silently break the four-page guarantee. The framing lint also reads the slot text. Tools never choose a date.

### 7. Figure numbering, captions, provenance

The builder assigns `Figure N` in order of first appearance across diagrams, charts and screenshots; captions and alt text come only from the manifest; the builder never composes a caption. The evidence change's chart captions already state the limits and the single-measurement note for latency and cost; the report must show the caption unchanged. A source footnote under each chart lists the manifest `source_keys` at the footnote size of the stylesheet (not below 7.5 pt, dark text), so each plotted number traces to `summary.json`. Because the manifest has no figure number, numbering is a report concern (the deck may number differently).

### 8. Shared and pre-existing files; edits to list for merge

New files only, plus small additive edits, which the coordinator merges with the deck and evidence changes:

- `README.md`: one row/line for the report build and check commands.
- `docs/progress.md`: a section recording the measurement and placeholders status once run.
- `docs/work_log.toml`: register `docs/presentation_report.md` as a document section.
- `.github/workflows/ci.yml`: one step in the `offline` job: `.venv/bin/python scripts/build_report.py check`.

`scripts/build_work_log.py` is read (loaded by path), not modified; `report/index.html` is not rebuilt or touched.

### 9. Tests (offline, deterministic, no browser)

Fixtures hold a tiny `summary.json` (with `protocol`, `documents` and `limits` keys in the evidence shapes) and `manifest.json` (with compact chart entries, asset alt text and the `user_text` status), a stub shared `user_text.toml` with empty slots, two small SVG charts (full and compact), a stub diagram, a 1x1 PNG and JPG and a template exercising every directive. Tests cover: directive resolution and failure on a missing id, key or slot; number formatting (`pct` and `ratio` reproduce the documented `90.0%` and `27/30` strings from fixture pairs); unknown manifest ids failing the build; HTML escaping of the user text and of summary strings; sanitizer rejection of a script-bearing SVG; id uniqueness after inlining; figure numbering and `{{ref:}}` agreement; pending screenshot rendering; null-date placeholder; empty and filled slots, over-long slot failure, `--require-user-text` failure and success; the digits lint (whole-token allowlist, template prose only) and the claims lint (including a template edit that adds a bare number, a quoted limit ending "improvement" passing, the same word in a user slot failing with the slot named, and a template trying to write the `quoted` marker failing); the print-legibility rule (a chart rendered too narrow, a small stylesheet font size, a low-contrast colour); print-block restriction; "budgets not calibrated" failure; structural checks (four pages, `lang` and `<title>`, print CSS rules, no script, no external reference, logo alt from the manifest, placeholders with a border); navigation hidden in print; deterministic output (two builds identical, no timestamp); a build with no manifest screenshot files present; the page-count helper on hand-made minimal PDFs (three and four pages, and one with a `/Pages` node and no plain page objects expecting the distinct "could not determine" failure); the measure-result parser on canned measurement output (clip detected, headroom warning); and that no script reads the ledger or opens anything outside the repository. The browser path itself is exercised by hand and recorded; the test for it skips cleanly only when no browser is found and says so.

## Risks / Trade-offs

- **Chart density versus legibility.** Resolved by D1 with compact half-width variants and tables; the remaining risk is vertical space on page 3 (see the space arithmetic), handled by the static estimator, the measurement and a template-level selection of six to eight charts.
- Pagination depends on the viewer's font stack → headroom threshold, 296 mm boxes, local measurement recorded with browser version, no claim for other browsers.
- User text length changes layout → fixed slot box and a length limit enforced by `check`.
- `overflow: hidden` can hide content in a viewer with different fonts → the measurement is the detector; documented in `docs/presentation_report.md`.
- Draw.io diagrams sanitized for the work log may lose detail at print width → judged in the implementation phase by the coordinator in print preview, with the text twins in `docs/architecture_*.md` as the accessible fallback (referenced, not duplicated).
- Shared-file edits collide with the other two changes → additive, listed above.

## Migration Plan

Implement on a branch from `main` after `add-presentation-evidence` merges: builder and template with fixtures, static checks, CSS and page budgets, browser measurement, docs and CI wiring, real build and measurement. Rollback is deleting `presentation/report/`, `scripts/build_report.py`, the test, the doc and the four small edits; nothing under `src/` changes and `report/index.html` is unaffected.

## Decisions confirmed by the coordinator (round 2)

- **D1 (user):** compact charts plus tables: compact half-width chart variants from `add-presentation-evidence`, nothing below 7.5 pt printed, about eight key charts covering all four chart sets plus compact numeric tables, exactly four pages.
- **D2:** protocol facts (tasks, trials per task, planned trials, ceiling, checkpoint, ledger total, probe categories) come from `summary.json` (`protocol`); this change keeps no quote table of its own.
- **D3:** one shared `presentation/user_text.toml` created by the evidence change; this change reads its `report` keys (`motivation`, `takeaways`) and creates no user-text file.
- **D4:** the report is `report/presentation_report.html` (generated, Git-ignored); links to `report/index.html` and `report/demo.html` are printed paths plus screen links, a missing target a non-fatal note.

Bound at task 4.1 against the merged evidence change: the manifest ids (`diagram-*`, `shot-*`, compact chart ids), the `limits` and `documents` shapes, the `protocol` keys, the asset alt text and the `user_text` status; a mismatch fails the build and is fixed here, never by redefining the evidence interface.
