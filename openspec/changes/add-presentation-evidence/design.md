# Design

## Context

The project is complete; the user will give a 15-minute HTML presentation and hand in a 4-page printable HTML report (changes `add-presentation-deck`, `add-presentation-report`). This change produces what both share. Existing material it builds on: `codegen_eval.comparison` (`experiment_cli compare --json` already computes outcomes, per-category, per-task, failure labels, efficiency, tokens, latency, cost), `codegen_eval.trace_inspect` and `codegen_eval.bundle` (trial records), the reviewed documents (`docs/prompt_comparison.md`, `comparison_evidence.md`, `ci_evidence.md`, `smoke_evidence.md`, `demo.md`, `progress.md`), the four `docs/*.drawio.svg` diagrams, and `scripts/build_work_log.py` (the precedent for a standalone, offline, documented script with `--check` and tests loading it by path).

Fixed inputs: comparison runs baseline `20261103T053309Z-280182` and revised `20261103T095324Z-d25905`; forced passing smoke `20261103T050806Z-30949f`. Retained bundles live in the primary checkout's Git-ignored `run_bundles/`, never in a worktree or in CI.

## Goals / Non-Goals

**Goals:** one provenanced evidence summary; deterministic accessible SVG charts; a stable manifest for the deck and the report; a screenshot plan; a reproducible credential-free recording; the logo; offline tests.

**Non-Goals:** slides, report pages, new experiments or paid calls, changes under `src/`, third-party or JavaScript libraries, capturing screenshots (coordinator), writing the user's interpretation or reflections, presenting 27/30 to 29/30 as an improvement.

## Decisions

### 1. Layout and what is committed

```
presentation/
  manifest.json                 committed; the consumer interface (decision 6)
  evidence/summary.json         committed; reviewed summary (decision 2)
  charts/<id>.svg               committed; generated from summary.json
  assets/zhaw_rgb.jpg           committed; with zhaw_rgb.jpg.source.txt
  screenshots/<id>.png          committed once captured by the coordinator
  recording/demo.cast           committed unreviewed; the user's approval is the marker file review.txt
  recording/player.html         committed; hand-written template, no embedded cast
scripts/presentation_evidence.py   collect | check | manifest
scripts/render_charts.py           summary.json -> charts/*.svg
scripts/record_demo.py             record | build-player | check
tests/test_presentation_*.py, tests/fixtures/presentation/
```

Committed versus generated, with reasons:

| Output | Decision | Reason |
| --- | --- | --- |
| `summary.json` | committed | Bundles are Git-ignored and absent in CI and in the deck/report builds; a reviewed summary is exactly what `project_spec.md` allows ("reviewed result summaries"). It holds aggregates and short excerpts only. |
| chart SVGs | committed | Small deterministic text assets that the deck and the report both embed; the spec says to commit assets. Drift is caught by byte comparison against a fresh render in `check`, so committing them cannot hide staleness. |
| `manifest.json` | committed | The interface must be readable without running code. |
| `demo.cast` | committed as `unreviewed`; approved by the user's `review.txt` marker | A text file of tens of KB; it cannot be regenerated without Podman and the repository checkout, and the user reviews the transcript once and approval is recorded by adding `presentation/recording/review.txt` (it contains run IDs and timings that differ per run, so it is not byte-reproducible; the script is). |
| player page with the cast embedded | generated into Git-ignored `report/demo.html` | It is a built HTML page (spec: exclude generated HTML); the hand-written template is what is committed. |
| deck and report HTML | generated into `report/` by changes 2 and 3 | Same rule. |
| raw bundles, MLflow stores, ledger | never committed, never read by these scripts | Spec line 175; the ledger additionally by the user's decision. |

`/report/` is already ignored; no `.gitignore` change is needed. Scripts live in `scripts/`, not `src/`, so the evaluator source hash recorded by future runs is untouched.

### 2. The summary file

`presentation/evidence/summary.json`, canonical JSON (sorted keys, two-space indent, trailing newline), `schema_version: 1`. Top-level sections:

- `provenance`: `generated_by` (script name and its own sha256), `commit` (Git revision it was generated at), `commands` (the exact `experiment_cli compare ... --json` and `trace_inspect verify` invocations, with relative bundle paths), and `runs`: for `baseline`, `revised`, and `smoke_forced_pass`: `run_id`, `bundle` (relative, `run_bundles/<id>`), `bundle_digest` (sha256 of `manifest.json`), `prompt` name and sha256, `mlflow_run_id` (from `comparison_evidence.md`), `completeness` (from `trace_inspect verify`).
- `comparison`: the `compare --json` fields we need, copied unchanged: `primary`, `hidden_checks`, `edge_cases`, `categories`, `per_task`, `failure_labels`, `tasks_passing_at_least_one_trial`, `tasks_passing_every_trial`, `delta` (gained, regressed, unchanged tasks), `caveats`.
- `efficiency`: `model_calls`, `attempts`, `tool_attempts`, `revisions`, `recovery`, `tokens`, `model_latency_ms`, `trial_wall_clock_ms`, `cost` (`reported_usd`, `charged_chf`, `reserved_before_send_chf`), per variant.
- `stories`: `lists_02` (per variant, per trial: success flag, grade labels, `contract_issue` code, model calls, tool attempts, whether a development check failed, all read from the trial records through `codegen_eval.bundle`; the final-message form is derived by a stated rule from recorded fields only: grade label `syntax_error` means prose before the code, `contract_error` with a fence issue means a fenced reply, otherwise a bare function, as `docs/prompt_comparison.md` reads them; no heuristic on the source text) and `strings_01` (same, plus for the failing revised trial the failing check id and its actual value). Excerpts are truncated to a fixed length and contain no prompt text beyond what the documents already show.
- `smoke`: forced-pass smoke run facts (call and tool-attempt counts) from its bundle, cited to `docs/smoke_evidence.md`.
- `engineering`: `tests` (collected counts: offline group and `-m sandbox` group, from `pytest --collect-only -q` at generation, with the commit), `ci` (run IDs, jobs, outcomes and counts, each extracted from a committed document by the quote table: the `podman` counts of `docs/ci_evidence.md`, 63 at `ef1186e` and 64 at `15c9eb9`, and the single `offline` count recorded in `docs/progress.md` (its note on run 41581787430); every count is labelled with its origin, and a CI count with no recorded source is omitted or shown as pending, never typed), `changes_archived` (names and dates, from `openspec/changes/archive/`), `specs` (count from `openspec/specs/`).
- `ledger_quotes`: ledger totals exactly as written in `docs/prompt_comparison.md`, taken by quoting the document, never by reading `~/.codegen_eval/spend_ledger.jsonl`.
- `limits`: all seven limits documented in `docs/prompt_comparison.md` (small n, benchmark-informed tuning, single model and provider, fixed sampling and no repeated runs, provider precision not returned, evaluator revision differs, benchmark reviewed by models only) and the non-claim ("not a measured improvement or breakthrough"), each with a `quote` from that document.

Every leaf group has `source`: either `{"command": ..., "field": ...}` (bundle-derived) or `{"file": ..., "quote": ...}` (document-derived). Values derived from documents (CI run IDs and counts, MLflow run IDs, ledger quotes, limits) come from a small explicit table of `(file, quote, field, extract)` entries, where `extract` names the token of the quote that is the value (a regular expression with one group, written next to the entry). The collector computes the stored value from the quote by `extract`; it is never typed. `check` asserts that the quote occurs verbatim in its file and that applying `extract` to the quote yields exactly the stored value, so a value edited while its quote stays intact fails. If a document is edited, the check fails and a human re-reviews, which is the intended behaviour.

No absolute paths: bundle locations are relative to the bundles directory that `--bundles` names.

### 3. Regeneration and checking

```sh
# on the primary checkout, which has run_bundles/ (bundles dir is a flag, never written to)
PYTHONPATH=src .venv/bin/python scripts/presentation_evidence.py collect --bundles run_bundles
.venv/bin/python scripts/render_charts.py
.venv/bin/python scripts/presentation_evidence.py manifest

# anywhere, including CI (no bundles)
.venv/bin/python scripts/presentation_evidence.py check
.venv/bin/python scripts/render_charts.py --check
# primary checkout only: also recompute bundle-derived sections
PYTHONPATH=src .venv/bin/python scripts/presentation_evidence.py check --bundles run_bundles
```

`collect` calls `comparison.compare_runs` and `bundle` in-process (as `experiment_cli compare --json` does), refuses to run if the two runs are not a headline comparison or are incomplete, and refuses to write into the bundles directory (it opens bundles read-only through the existing loaders). `check` (offline) validates structure against a schema embedded in the script, verifies every quote-table entry as in decision 2 (quote in file, `extract` yields the stored value), verifies internal arithmetic (counts at most denominators, per-task sums equal totals), and verifies the committed charts and manifest equal a fresh render. Because CI has no bundles, the offline `check` also cross-checks the bundle-derived headline numbers against the reviewed lines of `docs/prompt_comparison.md` through the same quote table: successful trials (27/30, 29/30), hidden checks, edge cases, categories, the gained and regressed task, model calls, tool attempts, revisions, tokens, latency totals, and charged and reserved cost. Editing either the summary or the document therefore fails the offline check; `check --bundles` remains the stronger verification on the primary checkout. `check --bundles` recomputes and requires equality for `comparison`, `efficiency`, `stories`, `smoke`, and the `runs` provenance (IDs, digests, prompts, completeness), naming the first differing field; `provenance.generated_by` and `provenance.commit` are reported, not compared, because they change with every script edit or commit. The engineering snapshot is compared against the repository only by `check --staleness`, a read-only report (it never rewrites anything) that notes non-fatally when the snapshot is older than HEAD, because test and archive counts legitimately grow when changes 2 and 3 land.

Import and ledger discipline: `scripts/presentation_evidence.py` imports `codegen_eval` lazily, only inside `collect` and `check --bundles`, so the CI step `.venv/bin/python scripts/presentation_evidence.py check` runs without `PYTHONPATH=src` (the package is not installed). `codegen_eval.comparison` imports `codegen_eval.experiment`, which imports `codegen_eval.ledger`, so that module is loaded as a side effect; the guarantee is therefore behavioural: no script imports the ledger module directly, constructs a `Ledger`, or opens the ledger path, and `collect` and `check --bundles` set `CODEGEN_EVAL_LEDGER` to a non-existent path in a temporary directory before importing `codegen_eval` (the ledger honours that variable), so even an accidental read cannot reach `~/.codegen_eval`.

The offline `check` and `render_charts.py --check` are added to the CI `offline` group's command list (task) so drift fails CI; they need only `summary.json` and documents.

### 4. Chart generator

`scripts/render_charts.py` reads only `summary.json` and writes plain SVG with the standard library (string templates, `xml.sax.saxutils.escape`, fixed `%.1f`/integer formatting, no timestamps or random IDs), so output is byte-identical. No JavaScript, no external font or image reference; font stack `system-ui, sans-serif`. Each SVG has `role="img"`, `aria-labelledby` pointing at `<title>` and `<desc>`, an opaque white background rect (legible on dark slides and in print), a fixed `viewBox="0 0 960 540"` (16:9) for every chart. Intended render widths: slide, full slide width (at least 1280 px); report, single column, at least 160 mm. One variant serves both; there is no half-column use. The minimum font size follows from the narrowest use: 160 mm over 960 units is 0.167 mm per unit, so 20 units is 3.3 mm (9.4 pt); every `font-size` in every chart is therefore at least 20 units, and an offline test parses each chart and fails on any smaller value or a missing `font-size`. Legibility of the finished pages is still confirmed in changes 2 and 3, but the SVG geometry and minimum are fixed here. Element set: only `svg, title, desc, defs, marker, path, g, rect, text, tspan, style`, the set `scripts/build_work_log.py` accepts (so change 3 may inline the charts through that validator); the hatch for the second variant is drawn as diagonal `path` segments computed inside each bar rectangle, not with `pattern`, `clipPath`, `line`, or `image`. The two variants differ by fill pattern (solid versus diagonal hatch segments) as well as hue (a colour-blind-safe blue/orange pair), so greyscale print still separates them. Every bar carries its count and denominator beside the rate (`27/30 (90.0%)`).

Charts (ids are the interface):

| Id | Shows |
| --- | --- |
| `outcome-overview` | successful trials /30, hidden checks /120, edge cases /60, baseline vs revised |
| `outcome-by-category` | five categories, successes /6 |
| `outcome-by-task` | ten tasks, successes /3, gained and regressed marked |
| `failure-labels` | label counts per variant (`syntax_error`, `contract_error`, `wrong_answer`) |
| `story-lists-02` | the six `lists_02` trials: outcome, model calls, tool attempts, failed development check, final-message form (from grade labels and `contract_issue`, per decision 2) |
| `story-strings-01` | the six `strings_01` trials, with the one failing check of `strings_01-t2` |
| `efficiency-calls` | model calls, tool attempts, revisions |
| `efficiency-tokens` | prompt and completion tokens |
| `efficiency-latency` | total and mean per trial; caption: measured once, different times, no attribution |
| `cost-charged-reserved` | charged versus reserved-before-send CHF per variant, drawn on separate scales with explicit values (the two differ by an order of magnitude) |
| `engineering-tests` | collected offline and sandbox tests at the recorded commit, and the CI counts that a committed document records (`podman` per run; `offline` only for the run whose count `docs/progress.md` records), each labelled by origin; no count without a source |
| `engineering-ci` | CI runs recorded in `ci_evidence.md` with outcome (failed runs shown, as history) |
| `engineering-changes` | OpenSpec changes archived, by date |

Each has the full-size form above and, for ten of them, a compact form (decision 11).

Captions never use the words "improvement" or "breakthrough"; `story-lists-02` and `outcome-overview` captions in the manifest repeat the limits. Chart text comes from the summary's fields, so a number cannot be typed into a chart.

### 5. Existing diagrams

`docs/architecture_logical.drawio.svg`, `architecture_physical.drawio.svg`, `run_flow_activity.drawio.svg`, `run_flow_sequence.drawio.svg` (and `work_log_architecture.svg`) are listed in the manifest by repository-relative path with a role (`architecture`, `run-flow`) and caption. They are neither copied nor redrawn. A test checks each parses as XML, has no `<script>` and no external reference. Whether each is legible at slide and print size is judged in changes 2 and 3 where the layout is known.

### 6. Consumer interface (changes 2 and 3)

`presentation/manifest.json`, `schema_version: 1`:

```json
{
  "schema_version": 1,
  "title": {"author": "Jose Luis Barahona", "course": "CAS Applied Machine Learning (ZHAW)",
            "date": null, "date_placeholder": "[DATE: fill in]",
            "headline": "A trustworthy, reproducible, budget-safe evaluation pipeline for a coding agent"},
  "summary": "presentation/evidence/summary.json",
  "figures":     [{"id", "path", "format": "svg", "caption", "alt", "uses": ["deck","report"], "viewbox": "0 0 960 540", "min_render_mm": 160, "min_font_units": 20, "elements": "work-log set", "source_keys": ["comparison.primary", ...]}],
  "diagrams":    [{"id", "path": "docs/...drawio.svg", "format": "svg", "caption", "alt", "role"}],
  "screenshots": [{"id", "path", "format": "png", "caption", "alt", "status": "present|pending", "owner": "coordinator", "shows"}],
  "assets":      [{"id": "zhaw-logo", "path", "format": "jpg", "source_note", "sha256"}],
  "recording":   {"cast": "...", "player_template": "...", "built_player": "report/demo.html", "status"}
}
```

Rules: ids and `schema_version` are stable; a change to either bumps the version. All paths are repository-relative, forward-slash, and resolve from the repository root. Consumers copy or inline files at build time into the Git-ignored `report/` and never fetch anything. Consumers read numbers from `summary.json` (never retype them) and may quote `source_keys` for footnotes. The manifest is generated by `presentation_evidence.py manifest` from a hand-edited list of ids, captions and alt texts kept in the script (so captions are reviewed text, not data), and `check` fails if a path is missing and its status is not `pending`. The date stays `null` with the placeholder visible; neither tooling nor consumers choose a date.

### 7. Screenshots (coordinator-owned)

The coordinator captures these with the Orca browser; MLflow must run on port 5001 and cannot run while the sandbox tests run. Files go to `presentation/screenshots/`, PNG, light theme, viewport-only captures at 1440x900 (no browser chrome, so no `file:///Users/...` address bar), and each is registered `pending` in the manifest until the file exists. Before marking one present the coordinator reviews the PNG for local paths, hostnames, and the artifact tree of `bundle/`, since the text scan cannot read image content:

| File | Shows | Must display |
| --- | --- | --- |
| `mlflow-experiment-runs.png` | experiment `codegen-eval-runs`, runs table | both comparison runs with names/IDs, `success_rate`, tags |
| `mlflow-run-baseline.png` | baseline run overview (params, metrics, tags) | run `930a188254d34d279a88a7613ea55518`, bundle digest tag |
| `mlflow-run-revised.png` | revised run overview | run `bcddf5c9561c43129504555b020a7557` |
| `mlflow-compare.png` | the two-run comparison view | the runs side by side with `success_rate` |
| `mlflow-trace-lists02-baseline.png` | a `lists_02` baseline trace (the explanation-after-failed-check story) | AGENT, CHAT_MODEL, TOOL spans |
| `mlflow-trace-lists02-revised.png` | a `lists_02` revised trace | one model call, final `submission` |
| `mlflow-trace-strings01-t2-revised.png` | `strings_01-t2` of the revised run | the final source |
| `report-local-architecture.png` | `report/index.html` opened from disk, architecture figure | implemented/planned legend |
| `report-local-results.png` | the report's results/comparison section | counts and limits |

All 60 traces read back since the 2026-11-06 re-recording (`docs/progress.md`; the older sentence in `docs/comparison_evidence.md` is stale), so there is no trace constraint; the three listed traces are chosen for the two stories. Screenshots show only local identifiers. They are references to a local service, not evidence of a hosted one.

### 8. Recorder and player

`scripts/record_demo.py record` runs a scripted list of steps (the credential-free part of `docs/demo.md`: credential check `env | grep -c OPENROUTER` printing 0, fixture bundle creation `run_recording --scenario tool_use_and_revision --task strings_01 --trials 2 --grade`, `trace_inspect list/verify/show`, `replay`, `build_work_log.py --check`). No `compare` step is recorded, because the comparison needs two retained complete runs that a fresh checkout does not have; the comparison is shown by the charts and screenshots, so there is no retained-bundles flag. It writes `demo.cast` in asciicast v2 (JSON header line plus `[time, "o", data]` events). Decisions:

- It starts each command through `env -i` with the demo's credential-free PATH, as `docs/demo.md` does; the recorded cast therefore cannot contain an inherited key. A step list of commands is data in the script; a test asserts every command is a command line of `docs/demo.md` (no variants).
- Timing is synthetic and fixed (a constant typing rate, a capped delay after each command, output delivered line by line), so the recording does not depend on machine speed and has no idle gaps; the timings of the real run are not shown.
- Output is scrubbed: the repository root becomes `.`, the home directory becomes `~`, any temporary directory becomes `<tmp>`, and anything matching a secret pattern aborts the recording instead of being masked. The committed-file scan and `record_demo.py check` reject `/Users/`, the home directory, and the recorder's repository root.
- Replay is introduced with a printed line that it regrades saved candidates (no model, no credentials), matching the demo wording.
- Full `pytest -q` (minutes) and the MLflow section are not recorded; MLflow is shown by screenshots. The recording is reproducible from a fresh checkout.
- Commands run exactly as `docs/demo.md` shows them, in the repository root, with the default `run_bundles/` directory, so the displayed command is the command that ran and is never rewritten. To keep this away from retained evidence, `record` refuses to start unless `run_bundles/` is absent or empty (run it in a fresh checkout or worktree); `replay` therefore only writes into the fixture bundle it just created.
- Only Podman and uv are required; no API call is possible because no credential is in the environment.

`player.html` is hand-written (about 150 lines of vanilla JavaScript for play, pause, restart, speed, and a scrubber; no library, no network). `record_demo.py build-player` embeds the cast into the template and writes `report/demo.html`. The transcript is also embedded as static `<pre>` text, so the page is readable with scripting disabled and when printed. `record_demo.py check` validates a cast (header, monotonically increasing times, only `o` events, no absolute home path, no secret pattern) and is part of the offline tests and CI.

Alternative rejected: installing asciinema, agg or vhs (not installed; third-party dependencies need the user's approval). Alternative rejected: recording a live terminal (not reproducible from a script, leaks timings and paths).

### 9. Logo

`presentation/assets/zhaw_rgb.jpg`, downloaded once with a single `curl` from `https://www.zhaw.ch/storage/engineering/ueber-uns/medien/zhaw_rgb.jpg`, committed with `zhaw_rgb.jpg.source.txt` (URL, download date, SHA-256, a line saying it is ZHAW's mark used for the course presentation). The manifest records the digest and `check` recomputes it. No code fetches it again. Whether the course permits using the mark is the user's call (open question).

### 10. Tests

All offline, deterministic, no bundles, no network, no Podman: `tests/fixtures/presentation/` holds a tiny `compare --json` output and two trial records for each story (copied from the real shapes, with invented-free values marked as fixture), a stub documents directory for the quote check, and a golden SVG per chart type. Tests cover: schema validation and arithmetic checks (failing on a tampered count); the quote check failing when a document line is edited; `check` failing on a stale chart or manifest; chart determinism and accessibility (title, desc, labels, counts beside rates, pattern fill present, no `<script>`, no `http` reference); manifest path resolution, pending status and the null date; logo digest; cast validation (accepts a valid cast, rejects a home path, a secret pattern, an out-of-order time); the player build embedding the transcript; a scan that no committed presentation file contains `/Users/`, a key-like string, or a ledger path; a static test that no script imports `codegen_eval.ledger` directly or contains the ledger path, and a runtime test that patches `open` to fail on any path under `~/.codegen_eval` while `collect` runs on the fixtures and asserts `CODEGEN_EVAL_LEDGER` was redirected; a test that tampers with a stored document-derived value while leaving its quote intact and expects `check` to fail, and one that edits a `docs/prompt_comparison.md` fixture line and expects the offline cross-check to fail; a chart test that every `font-size` is at least 20 and only the allowed element set occurs. A separate offline test skips cleanly only on the optional live path (`--bundles`), which is exercised once by hand on the primary checkout and recorded in progress.

Recording status has three values in the manifest: `pending` (no cast), `unreviewed` (a cast is committed, `presentation/recording/review.txt` absent) and `approved` (the user added `review.txt`). The deck and the report must treat anything but `approved` as not yet endorsed by the user.

### 11. Compact half-width chart variants (user decision D1, round 2)

The report keeps exactly four A4 pages, shows about eight key charts across the four sets, and gives the remaining figures as compact numeric tables read from `summary.json`. For that, ten charts get a compact variant with its own id `<id>-compact` and the file `presentation/charts/<id>-compact.svg`; the manifest entry carries `variant: "compact"` and `full_size: "<id>"` (full-size entries carry `variant: "full"`, `full_size: null`). Compact charts exist for `outcome-overview`, `outcome-by-category`, `failure-labels`, `story-lists-02`, `story-strings-01`, `efficiency-calls`, `efficiency-latency`, `cost-charged-reserved`, `engineering-tests` and `engineering-changes`; `outcome-by-task` and `engineering-ci` are tables in the report.

Arithmetic: viewBox `0 0 480 270` (16:9), rendered at no less than 78 mm wide (half of a 160-180 mm A4 text column less a gutter). One unit is then 78/480 = 0.1625 mm, so a 17-unit font is 2.76 mm = 7.8 pt, above the required 7.5 pt (7.5 pt = 2.646 mm needs at least 16.3 units at that width). The minimum font size is therefore 17 units, enforced by a test for every compact text; the full-size minimum stays 20 units at 160 mm. Compact charts use shorter titles, a short legend (`Baseline v1`, `Revised v2`, derived from the prompt versions), counts with a rounded percentage (`27/30 90%`), and a one- or two-line note of at most 48 characters. Same element set, hatch, opaque background and determinism rules as the full charts; an offline test estimates every text's extent and fails if it leaves the viewBox.

### 12. Protocol facts in the summary (D2)

`summary.json` gains a `protocol` section so neither the deck nor the report keeps a quote table of its own: `tasks` (ten), `trials_per_task` (three), `planned_trials_per_variant` (30), `planned_trials_total` (60), `ceiling_chf` (15), `checkpoint_chf` (10), `ledger_total_chf` (the total after both runs, quoted from the comparison document), `probes_passed` (67) and `probe_categories` (the five protected-asset categories of the threat model, whose probes carry the isolation evidence). Each value is an entry of the existing quote table (committed document, verbatim quote, declared extraction), so `check` verifies the quote is in the file and the value is what the quote gives; counts written as words ("ten", "three") are read with a word-to-integer extraction. The ceiling and checkpoint are quoted from the budget decision in `docs/progress.md`; no ledger file or evaluator ledger code is read.

### 13. Shared user text (D3)

`presentation/user_text.toml` has empty slots `motivation`, `takeaways`, each with `deck` (short) and `report` (long), under a comment saying the user writes them and tools never fill them. The manifest lists it under `user_text` with its slots and whether each is `empty` or `filled`; the deck and the report render empty slots as visible placeholders and create no user-text file of their own. No script in this change opens it for writing; a test asserts the committed file's slots are empty and that none of the scripts writes to it. (The report path `report/presentation_report.html` and the deck's link to it are consumer decisions (D4), not part of this interface.)

### 14. Interface additions and the schema version (A5)

The manifest gains `variant` and `full_size` on figures, compact figure entries, a `user_text` object, and required `alt` text on every entry including assets; `summary.json` gains `protocol`. All of these are additions; no id, path, key or meaning of the version-1 interface changed, so `schema_version` stays 1. A consumer written for the earlier version-1 manifest keeps working; a future removal or rename would need a bump.

### 15. Round 3: overlap test hardening and two slide-legible diagrams

**Overlap bug (R1).** The full-size `outcome-by-category` chart ended its last revised bar (stroke included) at y=479 and drew the first footnote line, whose ascenders reach about 0.76 em above the baseline 494, from y=478: they touch. The round 2 overlap test did not fail because its text box was optimistic (0.72 em above the baseline, no descent, no air) and ignored the 2-unit bar outline, which left a computed gap of 2 units. The test now models ascent 0.80 em, a descent of 0.22 em for strings with descenders or parentheses, rect strokes, and a clearance of 2 units, and a fixture (`tests/fixtures/presentation/old_outcome_by_category.svg`, the old chart) proves it would have failed. A text box wholly inside a filled shape (a box label) is allowed; partial overlaps are collisions. Fixes through the generator: grouped bars now end above y=468 (the first footnote line starts near 478), full-size value labels sit 5 units above their bar bottom so a parenthesis cannot touch the next bar, and compact value labels line up to the right of the row's longest bar, with wider label columns for long category and label names.

**Diagrams for the deck (R2).** The `docs/` architecture figures are too dense at slide size, so two new plain-SVG diagrams are generated by `scripts/render_charts.py` (viewBox 960x540, text at least 20 units, the work-log element set, `title` and `desc`, opaque background, deterministic, no script or external reference, arrows drawn as plain paths with a triangular head). They carry no implementation-status labels (those are the subject of another change); they name components and flows only. Manifest ids (additive, `schema_version` 1): `diagram-pipeline-overview` and `diagram-trust-boundary`, in `diagrams[]` with `uses: ["deck", "report"]` (the report cannot use the dense `docs/` draw.io diagrams, which print at 1-2.6 pt), files `presentation/charts/<id>.svg`. Print legibility: at a full A4 text column of 160 mm the 960-unit viewBox gives 160/960 = 0.1667 mm per unit, so the 20-unit minimum text is 3.33 mm = 9.4 pt, above the 7.5 pt floor; the manifest entries state `viewbox`, `min_render_mm` 160 and `min_font_units` 20. No compact variants are made (half a column, 78 mm, would give about 4.6 pt). Every box label is listed in the mapping below, and a test checks that each label drawn appears in this table, that each flow label is drawn exactly as keyed, and that every source path exists. The boundary arrow carries what really crosses it: a bounded, unsigned result from the supervisor to the launcher; the per-check token signature is verified only inside the container, so the diagram does not call the result signed. The overlap test also models arrow paths and heads as thin shapes and allows text inside a drawn box only, never inside a bar.

| Diagram | Box or flow label | Real component or flow (sources) |
| --- | --- | --- |
| pipeline | Task + prompt | `tasks.py` (frozen tasks), `agent_config.py` with `prompts/` (versioned prompt); `docs/architecture_logical.md` |
| pipeline | Bounded agent | `trial.py` (bounded loop), `run_checks.py` (development checks), `model_client.py`; `docs/architecture_logical.md` |
| pipeline | final submission | `contract.py` validates the submission as source, `evaluate.py` grades it; `docs/architecture_logical.md` |
| pipeline | Hidden grading | `evaluate.py`, `contract.py`, `sandbox.py` (one fresh container per check); `docs/threat_model.md` |
| pipeline | Local run bundle | `bundle.py`, `run_recording.py` (bundle written first); `docs/architecture_physical.md` (`run_bundles/`) |
| pipeline | grades | `run_recording.py` grades through `evaluate.py` and writes the result into the bundle; `docs/architecture_logical.md` |
| pipeline | MLflow record | `mlflow_tracking.py` records a bundle after it is written; `docs/architecture_logical.md` |
| pipeline | record | `mlflow_tracking.py` uploads a bundle after it is written; `docs/architecture_logical.md` |
| pipeline | Grading replay | `replay.py` re-grades saved final candidates without a model; `docs/architecture_logical.md` |
| pipeline | re-grade | `replay.py` re-grades saved final candidates from the bundle; `docs/architecture_logical.md` |
| pipeline | Comparison | `comparison.py` compares baseline and revised runs from bundles; `docs/architecture_logical.md` |
| pipeline | compare | `comparison.py` reads two finished bundles; `docs/architecture_logical.md` |
| pipeline | CI: tests and probes on fixtures, no model API | `.github/workflows/ci.yml` (offline and podman jobs, fixtures and probes, no model API); `docs/architecture_logical.md` (CI gate) |
| trust | Trusted host | host CLI process holding answers, scoring, key and ledger; `docs/architecture_physical.md` (laptop, trusted host) |
| trust | Per-check container | disposable candidate container, one per check; `docs/architecture_physical.md`, `docs/threat_model.md` |
| trust | Answers + scoring | hidden expected answers and scoring code stay on the host (`evaluate.py`); `docs/threat_model.md` (Assets, Protections) |
| trust | Key + ledger | the API key and the spending ledger live in the host process only; `docs/architecture_physical.md`, `openrouter_cli.py`, `ledger.py` |
| trust | Launcher | `sandbox.py` starts one fresh container per check with limits; `docs/architecture_logical.md` |
| trust | Candidate function | `worker.py` runs candidate source with one case's arguments; `docs/threat_model.md` (no inputs beyond source, function name and one check's arguments) |
| trust | Supervisor | `worker.py` supervisor is the only writer of the container's stdout and checks the executor's signed report (`parse_report`); `docs/threat_model.md` |
| trust | Never inside | no expected answers, credentials, repository files, network, MLflow or Podman control: `docs/threat_model.md` (Assets, container flags) |
| trust | code + one case | the launcher sends candidate source, function name, one check's arguments, the per-check token and the output limits on the container's stdin to the supervisor (`sandbox.py` `execute_check`); `docs/threat_model.md` |
| trust | bounded result | the supervisor writes one bounded, unsigned JSON response (status, value, arguments after the call, or an outcome) to stdout and the launcher parses it (`worker.py` `respond`, `sandbox.py` `_exchange` and `execute_check`); the signature is checked only inside the container (`worker.py` `parse_report` verifies the token and removes it), the host verifies none; `docs/threat_model.md` (Attribution) |

### 16. Round 4: the latest recorded CI run

`docs/ci_evidence.md` gained a section "Latest run on main" (run 43461309299, commit `e00236d`, workflow success; `offline` tests=1199, skipped=67, failures=0, errors=0; `podman` tests=64, skipped=0, failures=0, errors=0, 0 leftover containers), recorded from the check-run annotations the coordinator read through `scripts/orchestration/ciwatch.sh` on 2026-11-13. Its quote-table entry (`r9`) carries an explicit `latest` marker; the summary stores `engineering.ci.latest` (the marked run id) and the engineering charts (`engineering-tests`, its compact variant, `engineering-ci`) and the report's test figure and CI sentence (`engineering.ci.latest` in `presentation/report/template.html`) read the run with that id; the report has no CI table, never the last item by position and never a typed id. `check` fails when the summary's `latest` differs from the marker in the quote table, and, like every quote, when the section is edited. Earlier runs and sections stay as history; run 41581787430 (825) remains a row of the CI table but is no longer shown as the latest. The additions are additive (`engineering.ci.latest`, extra per-run fields), so `schema_version` stays 1. Because this run ran the three presentation CI steps on `main`, it is also the evidence for task 5.3a.

### 17. Round 5: the presentation date is user text

The manifest used to hold `title.date: null` and `check` failed when it was set, while the deck's strict build and the report's release build failed while it was unset, so the user had no place to write it. The date is now user text: `presentation/user_text.toml` has a `[title]` table with `date = ""` (the one edit to that file in this round; the user writes the value as `YYYY-MM-DD` or free text, tools never fill it). The manifest stays deterministic: `title.date` stays `null` and `title.date_source` is `"presentation/user_text.toml#title.date"`; the manifest does not record whether the date is filled, so writing the date needs no manifest regeneration. The deck's title slide and the report's title read the date from `user_text.toml`, show the placeholder `[DATE: fill in]` while it is empty, and the deck's `--strict` build and the report's `--require-user-text` build keep failing while it is empty (the deck reports `unfilled user slot: title date`). Validation (identical rule in the checker and both builders): a string, at most 40 characters after trimming, no control characters or line breaks; builders escape it. No script writes the file; the never-writes test now covers the two builders as well. `schema_version` stays 1 (`date_source` is additive).

## Risks / Trade-offs

- Documents edited later break quotes → intended; the check names the stale quote so a human re-reviews.
- Test and archive counts grow as changes 2 and 3 land → snapshot carries its commit; `check --staleness` reports staleness non-fatally; refresh the summary after those changes.
- Charts embedded at slide size are small at print size → fonts at least 20 viewBox units (17 in the compact variants, rendered no narrower than 78 mm) and labels on bars rather than legends; the offline tests check font sizes, text extents and overlaps, and the finished pages are confirmed in changes 2 and 3.
- The recording is not byte-reproducible (run IDs) → the script and its command list are the reproducible part; the cast is reviewed once.
- Using a third-party logo → source recorded, user decides.
- Hatched patterns and hand-written JS add code → small, tested, and no dependency.

## Migration Plan

Implement on a branch from `main` in this order: collector and summary, check, charts, manifest, logo, recorder and player, docs and CI wiring. Rollback is deleting `presentation/`, the three scripts, tests, and doc edits; nothing under `src/` changes.

## Decisions confirmed by the coordinator

Branch prefix `jolbax/`; the ZHAW logo may be committed (user approved); the recording may omit MLflow (screenshots cover it); the two `--check` commands join the CI `offline` job; chart SVGs and `demo.cast` are committed and the player page is generated into ignored `report/`; scripts stay in `scripts/`; this change may edit `README.md` (including the `offline` row of its CI table), `docs/progress.md`, `docs/work_log.toml` and `.github/workflows/ci.yml`.
