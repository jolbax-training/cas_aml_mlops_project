# Design

## Context

See proposal.md. Inputs are fixed by the user: the approved 13-slide outline, the accepted decisions in the shared context, and the consumer interface of `add-presentation-evidence` (read-only here): `presentation/manifest.json` (schema_version 1) with figures, diagrams, screenshots (`present|pending`), assets and recording, plus `presentation/evidence/summary.json`. The precedent for an offline builder is `scripts/build_work_log.py` (explicit sources, `--check`, atomic write, tests that load the script by path). `docs/project_spec.md` says to commit editable sources and keep generated HTML out of Git; `/report/` is already ignored.

## Goals / Non-Goals

**Goals:** a talk deck that is trustworthy by construction (numbers by reference), legible, printable, and where the user's words are visibly theirs.

**Non-Goals:** the report (`add-presentation-report`), new evidence, charts or screenshots, a live demo, a presentation framework, a presenter window synchronised across screens, writing the user's motivation or takeaways.

## Decisions

### 1. Sources, build and output paths

```
presentation/deck/
  slides.toml       committed; per slide: id, title, minutes, layout, blocks (text with {{ref}}, figure ids, links)
  notes.toml        committed; factual speaker notes per slide id
  deck.css          committed; layout, font floor, print rules
  deck.js           committed; navigation only (~50 lines)
scripts/build_deck.py    build | --check | --strict
report/deck.html         generated, Git-ignored; single file
report/deck_notes.html   generated, Git-ignored; one slide of notes per printed page
```

Why separate files and TOML: the user's words are not in these files at all: slots 2 and 12 read the shared `presentation/user_text.toml` (created by `add-presentation-evidence`, empty slots `motivation` and `takeaways`, each with a `deck` short key and a `report` long key; the deck reads only the `deck` keys and never creates or edits the file); TOML is already used (`docs/work_log.toml`, parsed with `tomllib`), needs no dependency, and keeps prose out of Python. Why a `report/` output: same ignored directory as the work log, so relative links to `report/index.html` and `report/demo.html` resolve, and no `.gitignore` edit is needed. The script writes only these two files, through a temporary file and rename, so a failed build keeps the previous output and never touches `report/index.html`.

Alternatives rejected: a Markdown deck (needs a converter and gives weak layout control); committing the generated HTML (violates the spec's exclusion; drift risk); one HTML file per slide (breaks navigation and print).

### 2. One file, inlined assets

`deck.html` inlines CSS and JS, and embeds every figure, the ZHAW logo and present screenshots as base64 data URIs, so it works when moved or opened from `file://`. SVGs are first checked by loading `scripts/build_work_log.py` by path (as its tests do) and calling its chart validator and `sanitize_drawio_svg`, so one element/attribute allowlist and DOCTYPE handling serves the work log, the report and the deck (no second copy). Decision: use `<img>` with a data URI and the manifest alt for every figure, because alt text then comes from one place (the manifest) for SVG, PNG and JPG alike, and `<img>` keeps chart CSS from leaking. The drawio SVGs from `docs/` are handled the same way after that sanitising. The logo's alt text and caption come from the manifest `assets` entry (`alt`, added by `add-presentation-evidence`); the build fails on an empty one, so the deck types no alt text anywhere.

### 3. Slide model and the approved outline

`slides.toml` holds the 13 slides with the exact titles and minutes of the outline. The build asserts: 13 slides, ids equal the expected ordered list in the script (so reordering fails), minutes sum to 15.0 using integer tenths to avoid float error. Content per slide (figure ids are manifest ids that bind to the merged `add-presentation-evidence` implementation; the build and its tests fail on an unknown id):

| # | Slide | Min | Content |
| --- | --- | --- | --- |
| 1 | Title | 0.5 | logo `zhaw-logo`, manifest headline, author, course, date placeholder (null stays visible) |
| 2 | Motivation | 1 | USER SLOT `motivation` |
| 3 | Problem statement | 1.5 | four problems: unsafe candidate code, flaky or hidden cost, irreproducible results, small-sample claims |
| 4 | Approach overview | 1.5 | diagram `architecture-logical` (agent loop, hidden grading, sandbox, bundles, MLflow, CI) |
| 5 | Scoring integrity | 1.5 | Podman sandbox, trust boundary, hidden final grading (checks and expected answers stay on the trusted host), what the isolation probes cover (probe categories from the summary); diagram `architecture-physical` |
| 6 | Reproducibility | 1.5 | bundles, digests, replay, completeness check; screenshot `mlflow-trace-lists02-baseline` (pending handled) |
| 7 | Budget-safe paid calls | 1 | ledger, reserve-before-send, CHF 15 ceiling, total spent CHF 0.0068 (summary protocol facts, rounded by the documented `chf4` format of decision 4 with the full quoted value in the footnote); figure `cost-charged-reserved` |
| 8 | Experiment design | 1 | 10 tasks x 3 trials, one model, one prompt sentence changed, all else frozen (tasks, trials per task and planned trials from the summary protocol facts) |
| 9 | Results | 1.5 | figures `outcome-overview`, `outcome-by-category` side by side (layout `pair`); the summary's non-claim as a caption line |
| 10 | What the traces say | 1.5 | figures `story-lists-02`, `story-strings-01` side by side (layout `pair`); why it is not proof |
| 11 | Limits and lessons | 1 | small n, benchmark-informed tuning, one model; MLflow big-int bug, smoke forcing (from `docs/progress.md`, `docs/smoke_evidence.md`) |
| 12 | Takeaways | 1 | USER SLOT `takeaways` |
| 13 | Questions | 0.5 | links: report, recorded demo player, repository |

Engineering statistics (tests, CI, archived changes) stay out of the deck, as approved; the three `engineering-*` figures are not used.

### 4. Numbers by reference

Slide text may contain `{{summary:<dotted.path>}}` (the value as stored) and `{{fmt:<format>:<dotted.path>}}`, where `<format>` is one of a closed set defined in the script: `int`, `ratio` (`27/30` from a count and its denominator path pair), `pct1` (one decimal), `chf4` (the numeric value rounded half-even to four decimals, so `0.0068475273497` shows as `0.0068`). A value shown through `chf4` carries a footnote with the full quoted value from the summary, so the rounding is visible and documented, never silent. Experiment-design and protocol facts (tasks, trials per task, planned trials, CHF 15 ceiling, CHF 10 checkpoint, ledger total quote, probe categories) are read from the summary's protocol section (decision D2 of the shared decisions); the deck keeps no quote table of its own. Key paths depend on the evidence change's merged summary schema; the build fails on a missing path.

Literal-number lint: a "bare" number is a digit run not adjacent to a letter or underscore (so `lists_02`, `strings_01-t2`, `int64` and `16:9` are not hits) in slide and notes text outside a reference. Bare numbers of two or more digits and any `CHF` or `/<digits>` pattern are rejected, except entries of an allow-list kept in `slides.toml` with a reason per entry (for example the slide count 13 and the minutes 15).

### 5. User slots, date and pending evidence

Slots 2 and 12 render the `deck` key of the `motivation` and `takeaways` slots of the shared `presentation/user_text.toml` (escaped, paragraphs split on blank lines). Empty text renders a dashed, high-contrast box reading "YOUR TEXT HERE: slot `motivation`, edit `presentation/user_text.toml` key `deck`". A missing file or missing key fails the build (the evidence change creates it). The title date renders the manifest `date_placeholder` while `date` is null; neither the build nor the tests choose a date. `--check` lists unfilled slots and pending screenshots as notices, exit 0; `--strict` (used by the user before the talk, not by CI) fails on any of them. Pending screenshots render a labelled box with id and caption, never a blank gap or a broken image.

### 6. Navigation (the only JavaScript)

About 50 lines of inline vanilla JS, no library: ArrowRight/Space/PageDown next, ArrowLeft/PageUp previous, Home, End, `N` toggles notes, `F` requests fullscreen, `#n` hash for the current slide so reload and links keep position, a live counter `n / 13` in an `aria-live="polite"` element. Justification: keyboard navigation cannot be done in CSS alone with reliable Home/End/Space semantics; scripting is progressive enhancement: the script adds a class (`js-deck`) to `<html>`, and every rule that hides, stacks or positions slides as a one-at-a-time deck is scoped under `html.js-deck`; without it, slides are stacked vertically and fully readable (the same stacked layout is what print uses). A test fails if any `deck.css` rule hides a slide outside that scope. No timers, no network, no storage. A test parses the script to ensure it has no `fetch`, `XMLHttpRequest`, `import`, `eval`, `localStorage` or URL.

### 7. Layout and legibility

Each slide is a 16:9 box (`aspect-ratio: 16/9`, sized with `min(100vw, 177.78vh)` and centred on black, so fullscreen letterboxes). Font sizes use `clamp` scaled to slide width with design values at a 1920 px slide: title 72 px, heading 56, body 36 (floor 28), caption 24, counter and footer 20 (floor); no smaller text anywhere. A test scans `deck.css` for `font-size` and fails below the floor (when expressed in the slide-width unit it is converted from the 1920 px base). Few words per slide: at most six bullets and about 25 words per bullet-slide, checked by a lint that warns (non-fatal) above limits. Layout per slide is `single` (one figure across the 1840 px content width) or `pair` (two figures side by side, each about 920 px). Effective chart text size is `min_font_units * render_width_px / 960` from the manifest (`min_font_units` 20): 38 px for `single`, 19 px for `pair`. Chart text floor is 18 px effective at a 1920 px slide (about one sixtieth of the slide height), below the 20 px floor for slide text because charts are drawn images with direct labels; the builder computes the value for each placed figure and fails below 18 px. Slides 9 and 10 use `pair`. If the merged charts reduce `min_font_units`, the builder fails and the fallback is `single` with the second chart moved to the notes page and the report; the 13-slide outline allows no sub-slides. Dark text on white slide backgrounds for projector contrast; high contrast placeholders. Contrast pairs are defined as tokens in `deck.css` and a test computes their ratios (at least 7:1 body, 4.5:1 other).

### 8. Print / PDF and notes

`@page { size: 1920px 1080px; margin: 0 }` with `print-color-adjust: exact`; `break-before: page` on slides 2 to 13 (no trailing blank page), chrome and notes hidden, so Print to PDF gives 13 pages. The PDF target is the Chromium-based Orca browser; other engines (Safari ignores `@page size`) may letterbox differently, and the print claim is not made for them. Speaker notes: kept in `notes.toml`, which is the committed source, and exposed two ways: an `N`-toggled panel in `deck.html` whose header shows the slide's minutes and the running total (hidden by default and in print, so the audience view and PDF never leak notes), and `report/deck_notes.html`, printable, one slide's title, minutes, running time and notes per page, for paper. Rejected: a separate presenter window (needs `window.open` and cross-window messaging, more JS, fragile from `file://`). Notes are factual: statements with source file references and summary references. No tooling can detect opinion, so the reviewer checks notes against the evidence; notes never read from `user_text.toml`.

### 9. Accessibility

`<html lang="en">`, a title, one `<h1>` on the title slide and `<h2>` per slide, `<main>` and per-slide `<section aria-label="Slide n of 13: title">`, figures as `<figure>` with `<figcaption>` (manifest caption) and `<img alt>` (manifest alt); the build fails on empty alt. Colour is never the only carrier (charts already hatch; placeholders use dashed border plus text). No animation or transition. Focus ring is visible; the notes panel is reachable by keyboard.

### 10. Links

Slide 13 links to the report at `report/presentation_report.html` (generated by `add-presentation-report`; decision D4) through one constant `REPORT_PAGE` in `scripts/build_deck.py`, to the recorded demo player (`report/demo.html` from the manifest `recording.built_player`) and to the repository (URL from `README.md`). Links are relative paths or plain anchors, never fetched. The report, player and work-log (`report/index.html`) links are printed as paths and are non-fatal when the target does not exist at build time: the link is rendered as text with "(not built)" and `--check` and the build print which links would fall back. Because the output then depends on the presence of those targets, the determinism claim is "identical sources and identical presence of the link targets", and the documented build order is player, report, work log, then deck (README subsection, task 2.3). The deck never modifies `report/index.html`.

### 11. Tests (offline, deterministic, fixtures)

`tests/test_build_deck.py` loads the script by path (as the work-log tests do) and uses `tests/fixtures/deck/` with a miniature manifest, summary, tiny SVG and PNG, and slide sources. Tests: outline order, 13 slides and minutes sum 15.0 (failing on tampering); unknown figure id, empty alt, unresolved number reference, literal number lint; slots empty versus filled, escaping, `--strict`; pending screenshot placeholder and `present` with missing file failing; null date placeholder; navigation script present and free of network, storage and eval; font-size and contrast checks on the real `deck.css`; print CSS rules (page size, break, hidden notes); notes absent from the audience view's visible text and present on the notes page; forbidden words scan over the source texts (`slides.toml`, `notes.toml`) and the manifest captions used, treating text resolved from the summary's `limits[].quote` entries and its non-claim field as allowed (they contain the words by quoting the document that denies the claim), while the user's own `deck` text is scanned only for a non-fatal warning; output scan (no external URL load, `/Users/`, key-like strings); byte-identical double build; failed build leaves previous output; `report/index.html` untouched. Rendering to PDF and legibility are not claimed by tests (see task 3). Further tests: the chart effective-font computation per layout, the `js-deck` scoping of slide-hiding rules, `chf4` rounding with its footnote, lint hits and allow-list misses, and the shared `user_text.toml` read.

### 12. CI and shared files

Additive edits listed for the coordinator to merge with the sibling change: `README.md` (a short "Presentation deck" subsection with the build command and the build order; also the `offline` row of the CI table at README.md:162, which the evidence change edits too), `docs/progress.md` (evidence entry), `docs/work_log.toml` (register the new spec/docs if the work log lists them), `.github/workflows/ci.yml` offline job and its header comment at line 3 that lists the offline checks (add `.venv/bin/python scripts/build_deck.py --check`; the deck check needs the committed manifest, summary and fixtures only, no bundles). If `add-presentation-evidence` is not yet merged, the real-manifest checks are skipped in tests only through fixtures, not through a skip marker.

### 13. Bound ids and summary keys (task 1.1, from the merged evidence change)

| Slide | Manifest ids | Summary keys |
| --- | --- | --- |
| 1 | `zhaw-logo` (asset, with `alt`), `title.*` | none |
| 2, 12 | none | `presentation/user_text.toml`: `motivation.deck`, `takeaways.deck` |
| 4 | `diagram-architecture-logical` | none |
| 5 | `diagram-architecture-physical` | `protocol.probes_passed`, `protocol.probe_categories` |
| 6 | `shot-mlflow-trace-lists02-baseline` (pending until captured) | `provenance.runs.baseline.completeness.{recorded,planned}` |
| 7 | `cost-charged-reserved` | `protocol.checkpoint_chf`, `protocol.ceiling_chf`, `protocol.ledger_total_chf` (via `chf4`) |
| 8 | none | `protocol.tasks`, `protocol.trials_per_task`, `protocol.planned_trials_per_variant` |
| 9 | `outcome-overview`, `outcome-by-category` | `comparison.{baseline,revised}.primary`, `limits.non_claim` |
| 10 | `story-lists-02`, `story-strings-01` | `comparison.delta.{gained_tasks,regressed_tasks}` |
| 11 | none | `comparison.delta.primary_successes`, `protocol.planned_trials_per_variant`, notes: `limits.items`, `limits.statement` |
| 13 | manifest `recording.built_player` | none |

All ids and keys exist on main; none had to be added to the evidence change. Layouts: `pair` for slides 9 and 10 (19.2 px effective chart text), `split` for 5 to 7 (22.0 px for the cost chart), `single` for 4. The two `docs/` diagrams are dense; their legibility at slide size is a coordinator check (task 3.2).

## Risks / Trade-offs

- Manifest or summary key names differ from assumptions → task 1.1 and 1.2 confirm against the merged evidence change first; mismatches go to the coordinator, never patched around.
- A data-URI deck can be several MB (logo, PNG screenshots) → fine for `file://`; the build reports the size and warns above 16 MB.
- Slide legibility cannot be proven by tests → coordinator rehearsal review in the Orca browser at 1920x1080 and an optional PDF page-count check (task 3.2).
- Pending screenshots at talk time → `--strict` before the talk catches them.
- Hand-written JS → small, library-free, content-checked by tests.
- The logo is ZHAW's mark → user decision recorded in the evidence change.

## Open Questions

None. Resolved by the coordinator: figure, diagram and screenshot ids bind to the merged `add-presentation-evidence` implementation (tests fail on an unknown id); the report page is `report/presentation_report.html`; the PDF during rehearsal is optional.
