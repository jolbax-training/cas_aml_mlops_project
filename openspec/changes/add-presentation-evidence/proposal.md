# Proposal

## Why

The project is complete (see `docs/progress.md`, `docs/prompt_comparison.md`, `docs/smoke_evidence.md`, `docs/ci_evidence.md`, `docs/demo.md`). Two deliverables remain: a 15-minute HTML presentation and a 4-page printable HTML report, for classmates and examiners, in English. Both must show the same numbers, and every number must come from recorded evidence, never typed in. Building the figures twice, once per deliverable, would let them drift apart and invite hand-typed values. This change produces the shared evidence once, with provenance, behind a documented interface that the two later changes (`add-presentation-deck`, `add-presentation-report`) consume.

The framing is fixed by the user: the headline is "a trustworthy, reproducible, budget-safe evaluation pipeline for a coding agent". The prompt comparison (27/30 to 29/30 successful task trials) is the worked example with its honest limits; it is not presented as a measured improvement or breakthrough. The evidence must carry those limits with it.

## What Changes

- Add a reviewed, committed evidence summary (`presentation/evidence/summary.json`) computed from the retained bundles (via the existing `comparison` and `trace_inspect` code) and from committed documents, with per-value provenance: source command or file, run IDs, bundle digests.
- Add a `--check` mode that fails when the summary drifts from the committed documents, and, when the bundles are present, from the bundles. In CI no bundles exist, so the offline check uses the committed summary and fixtures.
- Add a plain-Python SVG chart generator (no JavaScript, nothing vendored, no network at viewing time) for four chart sets: outcome comparison, failure labels plus the two trace stories (`lists_02` gain, `strings_01` regression), efficiency and cost, and engineering statistics. Charts are accessible (`title`/`desc`, text labels, counts beside rates) and legible in light and in print. The existing `docs/*.drawio.svg` diagrams are registered for reuse, not redrawn.
- Add a stable consumer interface: one manifest (`presentation/manifest.json`) listing every figure, diagram, screenshot, logo, recording, and the title information, with paths, formats, captions, and provenance references.
- Plan the MLflow UI and local HTML report screenshots as coordinator-owned captures with a fixed file list, paths, and content (this change does not capture them).
- Add a scripted, credential-free terminal recording of the demo path of `docs/demo.md`: a small Python recorder writing asciicast v2 and a hand-written self-contained HTML player, no voice, kept for interested viewers and not shown in the talk.
- Add the ZHAW logo (downloaded once from the URL the user gave, committed with its source URL) for the title slide.
- Document the interface in `docs/presentation_evidence.md` and register it in the work log.

No slides and no report pages are built here, and no evaluator, agent, grading, ledger, or tracking behaviour changes.

## Capabilities

### New Capabilities

- `presentation-evidence`: Provenanced evidence summary, drift check, deterministic accessible SVG charts, consumer manifest, screenshot plan, scripted demo recording, and shared title assets for the presentation and the report.

### Modified Capabilities

None. `project-delivery`, `prompt-comparison`, and `architecture-diagrams` are consumed, not changed.

## Impact

New files under `presentation/` (evidence summary, chart SVGs, manifest, logo, screenshots, recording and player template), three new scripts under `scripts/`, new offline tests with fixtures under `tests/`, `docs/presentation_evidence.md`, and small edits to `README.md`, `docs/progress.md` and `docs/work_log.toml`. No new runtime or third-party dependency. Source under `src/` is not touched, so evaluator hashes of future runs are unaffected.

## Dependencies and milestone

Depends on the completed project evidence (comparison runs `20261103T053309Z-280182` and `20261103T095324Z-d25905`, forced passing smoke `20261103T050806Z-30949f`). It is the first of three presentation changes and blocks `add-presentation-deck` and `add-presentation-report`. It is delivery polish: the cut order of `project-delivery` applies (this never reduces benchmark, trials, denominators, probes, CI, or MLflow records).

## Completion evidence

Offline tests pass without bundles; `presentation_evidence.py --check` passes both offline and, on the primary checkout, against the retained bundles; charts regenerate byte-identically; the recording was produced by the recorder and its transcript reviewed; coordinator-captured screenshots exist at the listed paths. Items needing the user's judgment (recording review, logo usage) stay unchecked until the user decides.
