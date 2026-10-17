# Proposal

## Why

Project goals, decisions, and evidence are spread across Markdown files, making it difficult to see the intended MLOps workflow and follow progress in one place. A locally generated work log with an opening architecture diagram gives the user a shared view before further evaluator work.

## What Changes

- Generate `report/index.html` from an explicit selection of authoritative Markdown sources, with embedded content, section navigation, source provenance, and a build timestamp.
- Make the first visible content an accessible offline architecture/goal diagram showing the local generation/evaluation/replay loop and later CI/tracking phase, with planned versus implemented status clearly distinguished.
- Include status, plans, dated decisions, pilot/benchmark information, selected learning-journal material, historical context, and registered future review/result records; show absent evidence as pending.
- Provide a repeatable local generation command and link/output validation, using no hosting, runtime web service, client-side fetching, or external assets.
- Limit included files and links; render candidate code as inert text and exclude credentials, private files, and raw experiment bundles by default.
- Update documentation during implementation to record the user-directed sequencing change: this focused report foundation comes first, while the laptop evaluation loop remains the first major functional milestone and a prerequisite for CI/MLflow integration.

## Capabilities

### New Capabilities

- `local-work-log`: Build and navigate an offline project work log from reviewed sources, including its opening architecture diagram, evidence handling, privacy boundary, and validation.

### Modified Capabilities

None. The main OpenSpec capability inventory is empty.

## Impact

Proposed implementation affects a standalone report builder, report source manifest and diagram definition, tests, development dependencies/lockfile if needed, and project documentation. Generated `report/` remains ignored by Git. Product evaluator code, live generation, infrastructure integration, and benchmark expansion are outside this change.

The project currently has an offline three-task evaluator and no report generator. Existing planning places report implementation in week two; the user's latest instruction explicitly brings this independent report foundation forward. A working local agent loop is not a prerequisite for this change, but remains mandatory before GitHub Actions and MLflow work. This small first change does not add a hosting requirement or change the four-week deliverables.

Completion evidence is a successful build from the current sources, offline opening of one HTML entry point with the diagram first, validated navigation and links, accessible text equivalents, and automated tests proving that hostile content and private paths are not included or executed. No model API, Podman, GitHub, or MLflow service is required for those checks.
