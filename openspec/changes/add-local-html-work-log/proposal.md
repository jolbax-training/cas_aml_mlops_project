# Proposal

## Why

The agent-evaluation/MLOps project needs one locally readable view of its architecture, decisions, progress, and experiment evidence. A small Markdown-to-HTML work-log keeps that evidence understandable within the user-confirmed four-day delivery window.

## What Changes

- Generate local `report/index.html` from explicitly selected Markdown and reviewed result summaries, with source provenance and build time.
- Place an accessible architecture diagram first, distinguishing the implemented pilot, planned agent/development-check loop, hidden grading boundary, local persistence/regrading, CI, and containerized MLflow.
- Include scope/status/milestones, dated decisions, benchmark review, results/comparison/limitations, local evidence references, MLflow identifiers, reproduction/demo instructions, and selected student-authored learning notes.
- Use local assets, escaped source/code, validated internal links, and honest pending labels. Building/viewing requires no model API, Podman, MLflow, network, or hosting.
- Provide one documented build command and validation mode; rebuild after meaningful milestones/runs while keeping the agent/evaluator independent of reporting.
- Simplify the earlier extensive report-engine plan: no generic graph engine, automatic raw-source appendices, repository harvesting, private-journal selection framework, live dashboard, or publishing system is required.

## Capabilities

### New Capabilities

- `local-work-log`: Generate and navigate an offline architecture, progress, and reviewed-evidence report from selected authoritative sources.

### Modified Capabilities

None. The main capability inventory is empty; the builder foundation was implemented 2026-10-30; the architecture figure (3.1) was completed 2026-10-31; only real-browser inspection (4.2) remains open.

## Impact

Implementation affects a small standalone builder, explicit source selection, a checked-in diagram asset, focused tests, a locked Markdown development dependency if needed, and reporting instructions/progress. Generated `report/` remains ignored. Agent/evaluator, API, CI, MLflow, benchmark expansion, and the transfer guide are separate implementation work whose evidence the report can reference.

The authoritative [project specification](../../../docs/project_spec.md) now allocates the first report foundation to day two and comparison/report completion to day four. The local fixture/evaluation/persistence/regrading path comes first; live smoke/budget controls precede CI/MLflow. The builder itself has no runtime dependency on those milestones or services. This supersedes the October 16 report-first sequence and larger report scope; earlier planning remains in Git history and dated progress.

Completion evidence is a successful build/check, an offline-opened single entry point with architecture first, correct navigation/pending labels, focused rendering/link/privacy tests, and readable desktop/narrow/zoomed layouts. No live experiment, CI result, student reflection, or tracking run is invented to populate the page.

## Dependencies and milestone

Position 6 of 11 in the implementation order (single ordered list: [prepare-reproducible-demo proposal](../prepare-reproducible-demo/proposal.md#implementation-order)) (revised 2026-10-30 when the remaining Wayfinder work was split into OpenSpec changes). The foundation uses the day-two two-hour HTML slot; completion uses part of the day-four two-hour comparison/report slot.

- **Upstream (runtime):** none. The builder reads selected Markdown only and does not import or run agent, evaluator, API, Podman, MLflow, or CI code.
- **Upstream (evidence it references when it exists):** `harden-candidate-execution`, `add-bounded-agent-loop`, `add-run-bundles-and-grading-replay`, `add-reviewed-benchmark-and-graders`, `add-openrouter-client-and-budget-ledger`, `add-local-mlflow-tracking`, `add-deterministic-ci`, `run-prompt-comparison`, and `add-evaluation-design-guide`. Until their reviewed records are registered, the matching sections stay pending.
- **Downstream:** `prepare-reproducible-demo` uses the rebuilt report as part of the final evidence walk-through.

## Traceability

- Wayfinder [issue 05](../../../.scratch/revise-project-spec/issues/05-containers-and-evidence.md), Q37: minimum HTML work-log content, local-only viewing, one build command, independence from execution.
- Wayfinder [issue 07](../../../.scratch/revise-project-spec/issues/07-delivery-and-spec.md), Q42: day-two foundation and day-four completion; presentation polish is cut first.
- [Map](../../../.scratch/revise-project-spec/map.md) out-of-scope list: no hosting or publishing.
- [Specification](../../../docs/project_spec.md) section "Local HTML work-log" and the completion checklist item for the offline work-log.
