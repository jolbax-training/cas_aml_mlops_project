# Proposal

## Why

The project is complete only when its evidence is verified against the completion checklist and a reader can set up, inspect, replay, and navigate it with exact tested commands. A planned delivery change makes the final day's setup/replay/demo work, buffer use, and cut order explicit so incomplete work is reported honestly rather than hidden.

## What Changes

- Verify and document setup, trace inspection, grading replay, evidence/MLflow navigation, and report opening with exact tested commands.
- Rehearse the final demo along a defined path from setup through comparison evidence and the transfer guide.
- Review every completion-checklist item against actual retained evidence and mark unmet items incomplete.
- Apply the agreed buffer and cut order: use the 2h buffer where needed and simplify presentation polish first; never reduce benchmark/trial counts or waive scoring-integrity checks.
- Update progress and the work-log sources with final observed status.

## Capabilities

### New Capabilities

- `project-delivery`: Verified setup, inspection, replay, and demo path plus honest completion accounting for the four-day project.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation affects README/setup documentation, a demo script or checklist document, progress entries, and work-log source registration. It adds no new runtime behavior beyond documenting and verifying commands delivered by other changes.

## Dependencies and milestone

- **Milestone:** Day 4, "setup/replay/demo" (2h) plus the 2h movable buffer in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan). Day-4 exit evidence is finished evidence, transferable design, and a rehearsed demo.
- **Upstream:** All other changes: `harden-candidate-execution`, `add-bounded-agent-loop`, `add-run-bundles-and-grading-replay`, `add-reviewed-benchmark-and-graders`, `add-openrouter-client-and-budget-ledger`, `add-local-html-work-log`, `add-local-mlflow-tracking`, `add-deterministic-ci`, `run-prompt-comparison`, `add-evaluation-design-guide`.
- **Downstream:** None; this is the final change.
- **Cut order:** Presentation polish is simplified first. Required checks, benchmark/trial counts, run evidence, and scoring-integrity checks are never cut to claim completion; unfinished work stays labelled incomplete.

Completion evidence is a documented and re-executed setup/inspection/replay/navigation command set, a rehearsed demo, and a progress entry mapping each checklist item to evidence or an explicit incomplete label. No demo or completion is claimed by this plan.

## Traceability

- Wayfinder [issue 07](../../../.scratch/revise-project-spec/issues/07-delivery-and-spec.md): Q42 (four-day allocation, buffer, cut order, exit evidence).
- Specification: "Four-day delivery plan", "Completion checklist", and "Exclusions and supersession" in [docs/project_spec.md](../../../docs/project_spec.md); map notes that reflections do not block delivery.
- Q1–Q11 have no per-question record in the Wayfinder issues (which start at Q12). The written record of those early confirmations is the map's Notes section ([map.md](../../../.scratch/revise-project-spec/map.md)), the Purpose and constraints section of [docs/project_spec.md](../../../docs/project_spec.md), and Git history (commit `c1ec419`). Traceability references to Q1–Q11 should cite those sources.

## Implementation order

This is the single ordered list of the planned OpenSpec changes; other proposals reference positions in it.

1. `harden-candidate-execution` — day 1, boundary/probes (3h)
2. `add-bounded-agent-loop` — day 1, agent/fixtures (3h)
3. `add-run-bundles-and-grading-replay` — day 1, bundles/regrading (2h)
4. `add-reviewed-benchmark-and-graders` — day 2, benchmark/reference review (3h)
5. `add-openrouter-client-and-budget-ledger` — day 2, API/budget/smoke (3h)
6. `add-local-html-work-log` — day 2, HTML foundation (2h); completed on day 4
7. `add-local-mlflow-tracking` — day 3, MLflow/traces (2h)
8. `add-deterministic-ci` — day 3, CI (2h)
9. `run-prompt-comparison` — day 3, baseline/inspection/revision/revised run (4h); day 4 comparison write-up
10. `add-evaluation-design-guide` — day 4, transfer guide/example (2h)
11. `prepare-reproducible-demo` — day 4, setup/replay/demo (2h) plus 2h buffer
