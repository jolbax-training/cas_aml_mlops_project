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

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation affects a small standalone builder, explicit source selection, a checked-in diagram asset, focused tests, a locked Markdown development dependency if needed, and reporting instructions/progress. Generated `report/` remains ignored. Agent/evaluator, API, CI, MLflow, benchmark expansion, and the transfer guide are separate implementation work whose evidence the report can reference.

The authoritative [project specification](../../../docs/project_spec.md) now allocates the first report foundation to day two and comparison/report completion to day four. The local fixture/evaluation/persistence/regrading path comes first; live smoke/budget controls precede CI/MLflow. The builder itself has no runtime dependency on those milestones or services. This supersedes the October 16 report-first sequence and larger report scope; earlier planning remains in Git history and dated progress.

Completion evidence is a successful build/check, an offline-opened single entry point with architecture first, correct navigation/pending labels, focused rendering/link/privacy tests, and readable desktop/narrow/zoomed layouts. No live experiment, CI result, student reflection, or tracking run is invented to populate the page.
