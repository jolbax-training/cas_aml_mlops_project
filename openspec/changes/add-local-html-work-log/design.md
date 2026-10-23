# Design

## Context

See proposal.md for motivation and scope. The current repository has Python 3.12/uv/pytest, an offline evaluator, Markdown sources, a configured GitHub origin, and no HTML builder. The user-confirmed [specification](../../../docs/project_spec.md) budgets a two-hour foundation on day two and later report completion. The previous report-first sequence and extensive report engine are superseded.

This design produces a view of reviewed documentation, not a runtime interface or proof that source claims are true. All tasks remain unstarted.

## Goals / Non-Goals

**Goals:** One offline entry point, architecture first, faithful selected-source rendering, honest evidence status, readable navigation, and a small independently runnable builder.

**Non-Goals:** Running agents/candidates/services, querying external evidence, publishing, interactive dashboards, a generic graph-layout engine, raw artifact ingestion, source-code appendices, or a general private-journal excerpt system.

## Decisions

### 1. A standalone static build

Use `.venv/bin/python scripts/build_work_log.py` to build `report/index.html`, with `--check` validating current sources/output structure without writing. These are target commands, not existing commands. Use a maintained Markdown parser with raw HTML disabled and table support; lock it through uv. Standard-library code handles paths, HTML assembly, provenance, and validation.

Embed local CSS and the reviewed diagram in one HTML file. No JavaScript, CDN, remote fonts/images, HTTP server, API calls, or evaluation imports are needed. Build time and selected source identities/hashes make the snapshot inspectable. Validate before atomic output replacement so failures preserve the last good report; source Markdown is never rewritten.

A full site framework adds unnecessary lifecycle work. A custom Markdown parser adds rendering risk. The small static approach fits the existing Python project and offline entry-point requirement.

### 2. Explicit source selection and pending evidence

Maintain a small checked-in source list, for example `docs/work_log.toml`, ordered by section with exact paths and current/historical/personal labels. Register existing authoritative scope/progress/setup/pilot documents and later reviewed benchmark/results/guide records. Do not recursively follow files or links. Wayfinder/OpenSpec records can be referenced rather than automatically embedded in full.

Render selected sources as sections; preserve dates, tables, code, checklists, and supersession context. Pending review/results/CI/MLflow/learning sections remain visibly pending until actual approved records exist. Registered files that disappear are errors. Personal material is selected deliberately; do not harvest journals or fill unanswered prompts. Learning reflections are non-blocking.

Reviewed Markdown summaries hold results and evidence identifiers; raw bundles and tracking stores remain excluded from automatic reads. References to local run evidence are explicit links, not instructions to embed whole bundles. External URLs remain labelled references whose availability is not queried.

### 3. A small checked-in architecture asset

Use a directly editable local SVG with accessible title/description and an adjacent HTML/text explanation. A small declarative definition is acceptable if simpler during implementation; a reusable graph-rendering system is not required. Review the trusted asset for scripts/external references; arbitrary source-provided SVG is not accepted.

The figure is the first visible main content, before narrative/status/navigation, with a goal title and implemented/planned labels that do not rely only on color. Show:

- Instruction/signature and versioned prompt to the bounded agent, which calls OpenRouter.
- Agent-authored examples through `run_checks`, fresh Podman execution per check, and bounded development feedback back to the agent.
- Explicit final submission to source validation and separate hidden acceptance grading.
- Expected answers/scoring outside candidate containers; no credentials, repository mounts, tracking, network, or Podman controls inside them.
- Durable local bundles before containerized local MLflow; saved-final-candidate grading replay without generation.
- Deterministic CI fixtures/probes, baseline/revised comparison, and reviewed Markdown to the report.

A legend and text equivalent explain these boundaries. Keep labels readable with narrow-screen scrolling, and verify desktop, 375-pixel width, and 200-percent zoom. The orchestrator example is labelled a design exercise, not another implemented service.

### 4. Safe rendering and validated navigation

Give sections/headings stable unique anchors; rewrite links between included Markdown sections to those anchors. Rebase other approved local evidence/source references relative to the report and validate their existence/fragments where applicable. Label non-embedded source references. A pending placeholder is explicit and cannot masquerade as a validated link to a nonexistent artifact.

Reject unsafe URL schemes, embedded credentials, absolute/escaping paths, and selections resolving into secrets, machine state, raw bundles, or tracking stores. Resolve symlinks before inclusion checks. External HTTPS and loopback HTTP evidence links are references only. External images become alt text, never automatic loads. Render Python, raw HTML, and code as inert text; the builder never executes selected content. Use a restrictive output CSP and semantic headings/navigation/focus styling.

This replaces the old requirement to embed linked Python/JSON/YAML as appendices and to build a private-heading omission framework. Keep the author-reviewed allowlist as the inclusion boundary; do not claim automated scanning guarantees all private prose is detected.

## Risks / Trade-offs

- Stale source claims → show provenance, preserve historical labels, and update progress after actual evidence arrives.
- Small report timebox → prioritize required content, inert rendering, links, and offline readability; defer generic rendering features and extra visual polish.
- External evidence unavailable → retain descriptions/identifiers and readable summaries locally.
- Private material in approved prose → explicit source selection and review; no harvesting or automatic publishing.
- Diagram/text drift → maintain both in the same focused report change and review them together.

## Migration Plan

Implement the builder/source list and focused validation tests, add the small architecture asset/text, register current documents and pending sections, and document build/check/open commands. Add actual result/review/guide summaries when delivered elsewhere in the project, then regenerate after meaningful milestones/runs. Keep generated HTML ignored and product execution independent.

Run build/check and focused/offline checks, inspect the report directly without network/services, and record commands/browser/evidence in progress. Rollback removes reporting files/output without changing authoritative Markdown or evaluator behavior. The earlier October 16 plan remains historical; this design implements Q37 within the four-day sequence.
