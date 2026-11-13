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
  user_text.toml    committed; the user's slots: motivation, takeaways (empty strings initially)
  deck.css          committed; layout, font floor, print rules
  deck.js           committed; navigation only (~50 lines)
scripts/build_deck.py    build | --check | --strict
report/deck.html         generated, Git-ignored; single file
report/deck_notes.html   generated, Git-ignored; one slide of notes per printed page
```

Why separate files and TOML: the user edits only `user_text.toml`; TOML is already used (`docs/work_log.toml`, parsed with `tomllib`), needs no dependency, and keeps prose out of Python. Why a `report/` output: same ignored directory as the work log, so relative links to `report/index.html` and `report/demo.html` resolve, and no `.gitignore` edit is needed. The script writes only these two files, through a temporary file and rename, so a failed build keeps the previous output and never touches `report/index.html`.

Alternatives rejected: a Markdown deck (needs a converter and gives weak layout control); committing the generated HTML (violates the spec's exclusion; drift risk); one HTML file per slide (breaks navigation and print).

### 2. One file, inlined assets

`deck.html` inlines CSS, JS, each used SVG (checked against the manifest's element set and no `<script>`, as `build_work_log.py` does), and the ZHAW logo and present screenshots as base64 data URIs, so it works when moved or opened from `file://`. SVGs are inlined (not `<img>`) only when they keep `role="img"` plus title and desc; otherwise they are wrapped in an `<img>` data URI with the manifest alt. Decision: use `<img>` with data URI and manifest alt for every figure, because alt text then comes from one place (the manifest) for SVG, PNG and JPG alike, and `<img>` keeps chart CSS from leaking. The drawio SVGs from `docs/` are handled the same way, after the XML, no-script and no-external-reference checks.

### 3. Slide model and the approved outline

`slides.toml` holds the 13 slides with the exact titles and minutes of the outline. The build asserts: 13 slides, ids equal the expected ordered list in the script (so reordering fails), minutes sum to 15.0 using integer tenths to avoid float error. Content per slide (figure ids are manifest ids; exact ids are confirmed against the merged manifest in the first task):

| # | Slide | Min | Content |
| --- | --- | --- | --- |
| 1 | Title | 0.5 | logo `zhaw-logo`, manifest headline, author, course, date placeholder (null stays visible) |
| 2 | Motivation | 1 | USER SLOT `motivation` |
| 3 | Problem statement | 1.5 | four problems: unsafe candidate code, flaky or hidden cost, irreproducible results, small-sample claims |
| 4 | Approach overview | 1.5 | diagram `architecture-logical` (agent loop, hidden grading, sandbox, bundles, MLflow, CI) |
| 5 | Scoring integrity | 1.5 | trust boundary bullets from `docs/threat_model.md`; diagram `architecture-physical`; what the isolation probes cover |
| 6 | Reproducibility | 1.5 | bundles, digests, replay, completeness check; screenshot `mlflow-trace-lists02-baseline` (pending handled) |
| 7 | Budget-safe paid calls | 1 | ledger, reserve-before-send, CHF 15 ceiling, total spent CHF 0.0068 (quoted via summary `ledger_quotes`); figure `cost-charged-reserved` |
| 8 | Experiment design | 1 | 10 tasks x 3 trials, one model, one prompt sentence changed, all else frozen (counts from summary) |
| 9 | Results | 1.5 | figures `outcome-overview`, `outcome-by-category`; the summary's non-claim as a caption line |
| 10 | What the traces say | 1.5 | figures `story-lists-02`, `story-strings-01`; why it is not proof |
| 11 | Limits and lessons | 1 | small n, benchmark-informed tuning, one model; MLflow big-int bug, smoke forcing (from `docs/progress.md`, `docs/smoke_evidence.md`) |
| 12 | Takeaways | 1 | USER SLOT `takeaways` |
| 13 | Questions | 0.5 | links: report, recorded demo player, repository |

Engineering statistics (tests, CI, archived changes) stay out of the deck, as approved; the three `engineering-*` figures are not used.

### 4. Numbers by reference

Slide text may contain `{{summary:<dotted.path>}}` (and `{{fmt:...}}` for a fixed format such as `27/30`). The builder resolves each against `summary.json`, failing on a missing path. A lint rejects a bare digit run of two or more digits or any `CHF`/`/30` pattern in slide and notes text outside a reference, except an allow-list of structural constants stated in the source (13 slides, 15 minutes, "10 tasks x 3 trials" is resolved from the summary instead). Where the summary is the evidence-change's `ledger_quotes`, the slide shows the quoted string, not a recomputed value. Key paths depend on the evidence change's final summary schema; confirming them is task 1.2.

### 5. User slots, date and pending evidence

Slots 2 and 12 render `user_text.toml` text (escaped, paragraphs split on blank lines). Empty text renders a dashed, high-contrast box reading "YOUR TEXT HERE: slot `motivation`, edit `presentation/deck/user_text.toml`". The title date renders the manifest `date_placeholder` while `date` is null; neither the build nor the tests choose a date. `--check` lists unfilled slots and pending screenshots as notices, exit 0; `--strict` (used by the user before the talk, not by CI) fails on any of them. Pending screenshots render a labelled box with id and caption, never a blank gap or a broken image.

### 6. Navigation (the only JavaScript)

About 50 lines of inline vanilla JS, no library: ArrowRight/Space/PageDown next, ArrowLeft/PageUp previous, Home, End, `N` toggles notes, `F` requests fullscreen, `#n` hash for the current slide so reload and links keep position, a live counter `n / 13` in an `aria-live="polite"` element. Justification: keyboard navigation cannot be done in CSS alone with reliable Home/End/Space semantics; scripting is progressive enhancement: with JS off, slides are stacked vertically and fully readable (the same stacked layout is what print uses). No timers, no network, no storage. A test parses the script to ensure it has no `fetch`, `XMLHttpRequest`, `import`, `eval`, `localStorage` or URL.

### 7. Layout and legibility

Each slide is a 16:9 box (`aspect-ratio: 16/9`, sized with `min(100vw, 177.78vh)` and centred on black, so fullscreen letterboxes). Font sizes use `clamp` scaled to slide width with design values at a 1920 px slide: title 72 px, heading 56, body 36 (floor 28), caption 24, counter and footer 20 (floor); no smaller text anywhere. A test scans `deck.css` for `font-size` and fails below the floor (when expressed in the slide-width unit it is converted from the 1920 px base). Few words per slide: at most six bullets and about 25 words per bullet-slide, checked by a lint that warns (non-fatal) above limits. Charts use the whole slide width (manifest says charts need 1280 px and font units of at least 20, giving at least 26 px effective at 1920). Dark text on white slide backgrounds for projector contrast; high contrast placeholders. Contrast pairs are defined as tokens in `deck.css` and a test computes their ratios (at least 7:1 body, 4.5:1 other).

### 8. Print / PDF and notes

`@page { size: 1920px 1080px; margin: 0 }` with `print-color-adjust: exact`; each slide `break-after: page`, chrome and notes hidden, so Print to PDF gives 13 pages. Speaker notes: kept in `notes.toml`, which is the committed source, and exposed two ways: an `N`-toggled panel in `deck.html` (hidden by default and in print, so the audience view and PDF never leak notes), and `report/deck_notes.html`, printable, one slide's title, minutes, running time and notes per page, for paper. Rejected: a separate presenter window (needs `window.open` and cross-window messaging, more JS, fragile from `file://`). Notes are factual: statements with source file references and summary references; the build lints for first-person opinion markers is not attempted, rather notes may hold no `{{user}}` text and the review checks them against evidence.

### 9. Accessibility

`<html lang="en">`, a title, one `<h1>` on the title slide and `<h2>` per slide, `<main>` and per-slide `<section aria-label="Slide n of 13: title">`, figures as `<figure>` with `<figcaption>` (manifest caption) and `<img alt>` (manifest alt); the build fails on empty alt. Colour is never the only carrier (charts already hatch; placeholders use dashed border plus text). No animation or transition. Focus ring is visible; the notes panel is reachable by keyboard.

### 10. Links

Slide 13 links to the report (`report/report.html` per the sibling change; the file name is an open question), the recorded demo player (`report/demo.html` from the manifest `recording.built_player`) and the repository (URL from `README.md`). Links are relative or plain anchors, never fetched. If the target is not built, the link is rendered as text with "(not built)", so nothing dead is presented, and the build reports it. `report/index.html` (work log) is linked from the deck footer on slide 13 only; it is never modified.

### 11. Tests (offline, deterministic, fixtures)

`tests/test_build_deck.py` loads the script by path (as the work-log tests do) and uses `tests/fixtures/deck/` with a miniature manifest, summary, tiny SVG and PNG, and slide sources. Tests: outline order, 13 slides and minutes sum 15.0 (failing on tampering); unknown figure id, empty alt, unresolved number reference, literal number lint; slots empty versus filled, escaping, `--strict`; pending screenshot placeholder and `present` with missing file failing; null date placeholder; navigation script present and free of network, storage and eval; font-size and contrast checks on the real `deck.css`; print CSS rules (page size, break, hidden notes); notes absent from the audience view's visible text and present on the notes page; forbidden words scan; output scan (no external URL load, `/Users/`, key-like strings); byte-identical double build; failed build leaves previous output; `report/index.html` untouched. Rendering to PDF and legibility are not claimed by tests (see task 3).

### 12. CI and shared files

Additive edits listed for the coordinator to merge with the sibling change: `README.md` (a short "Presentation deck" subsection with the build command), `docs/progress.md` (evidence entry), `docs/work_log.toml` (register the new spec/docs if the work log lists them), `.github/workflows/ci.yml` offline job (add `.venv/bin/python scripts/build_deck.py --check`; the deck check needs the committed manifest, summary and fixtures only, no bundles). If `add-presentation-evidence` is not yet merged, the real-manifest checks are skipped in tests only through fixtures, not through a skip marker.

## Risks / Trade-offs

- Manifest or summary key names differ from assumptions → task 1.1 and 1.2 confirm against the merged evidence change first; mismatches go to the coordinator, never patched around.
- A data-URI deck can be several MB (logo, PNG screenshots) → fine for `file://`; the build reports the size and warns above 16 MB.
- Slide legibility cannot be proven by tests → coordinator rehearsal review in the Orca browser at 1920x1080 and a PDF page-count check (task 3.2).
- Pending screenshots at talk time → `--strict` before the talk catches them.
- Hand-written JS → small, library-free, content-checked by tests.
- The logo is ZHAW's mark → user decision recorded in the evidence change.

## Open Questions

For the coordinator, none blocking the specs:
1. Exact manifest ids for the four `docs/` diagrams and the screenshot used on slide 6; the summary key paths for the ledger quote (CHF 0.0068, CHF 15 ceiling) and experiment-design counts.
2. File name of the report page (`report/report.html` assumed) for the slide-13 link.
3. Whether the coordinator wants the Orca browser rehearsal (task 3.2) to produce the PDF.
