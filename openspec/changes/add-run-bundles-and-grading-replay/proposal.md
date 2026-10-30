# Proposal

## Why

Paid model interactions cannot be regenerated identically, so every trial's evidence must be saved locally before anything else consumes it. Inspection, regrading, and tracking all need one durable record, and they must stay distinct so regrading saved code is never mistaken for a fresh agent trial.

## What Changes

- Persist a durable local run bundle per evaluation run before any MLflow recording: requests/responses, tool interactions, candidate history, final source, configuration/version hashes, usage, and grading results.
- Provide trace inspection: read retained interactions and results with no model API, Podman, or tracking service.
- Provide grading replay: execute saved final candidates against the retained benchmark with Podman and no model calls or credentials, producing new grading evidence kept distinct from the original.
- Record run completeness: verify every planned task/trial record exists, and mark runs incomplete with partial evidence preserved.
- Keep credentials, authorization headers, and secret environment data out of bundles; keep bundles excluded from version control.

## Capabilities

### New Capabilities

- `run-evidence`: Durable local run bundles, service-free trace inspection, and Podman grading replay of saved final candidates.

### Modified Capabilities

None. The main capability inventory is empty.

## Impact

New persistence and CLI modules under `src/codegen_eval/` (plus a bounded fix to the container cleanup in `sandbox.py`, see design decision 6), a bundle directory outside version control (exact layout and command names are bounded implementation choices to document), `.gitignore` coverage verification, and focused tests. MLflow upload is in `add-local-mlflow-tracking`; CI automation is in `add-deterministic-ci`; the API-free interaction fixtures belong to `add-bounded-agent-loop`.

Completion evidence: a fixture-driven run writes a complete bundle; inspection works with Podman and network unavailable; grading replay of known candidates reproduces recorded grades as separate evidence; tests show secrets are excluded and incomplete runs are flagged. Nothing here is implemented.

## Dependencies and milestone

- **Milestone:** Day 1, bundles/regrading timebox (2h) in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan); completes day 1 exit evidence "inspectable limits/failures/persistence/replay".
- **Upstream:** `harden-candidate-execution` (execution for replay, limit config hash), `add-bounded-agent-loop` (trial records and fixtures).
- **Downstream:** `add-reviewed-benchmark-and-graders` (benchmark version/hash and per-check grades stored here), `add-openrouter-client-and-budget-ledger` (physical attempts, usage, reservations recorded here), `add-local-mlflow-tracking` (uploads bundles), `add-local-html-work-log` (links reviewed summaries to bundle identities), `run-prompt-comparison`, `prepare-reproducible-demo`.

## Traceability

- Wayfinder: [issue 05 — Define Podman services and reproducible evidence](../../../.scratch/revise-project-spec/issues/05-containers-and-evidence.md), Q35 (bundles, three offline capabilities), Q34 (host CLI); issue 03 / Q24 (completeness checks, incomplete runs); issue 01 / Q16 (drafts retained on `no_submission`).
- Specification: [Evidence, MLflow, CI, and replay](../../../docs/project_spec.md#evidence-mlflow-ci-and-replay); [Glossary](../../../GLOSSARY.md) grading replay, trace inspection, incomplete evaluation run.
