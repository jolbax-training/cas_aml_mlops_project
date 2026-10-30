# Proposal

## Why

The project's evaluation subject is a bounded tool-using coding agent, not a single-response generator. A trial must allow the agent to write its own example checks, run them, inspect feedback, and revise within fixed limits before an explicit final submission is graded on hidden checks. This replaces the pilot's single-response/no-internal-revision rule.

## What Changes

- Add a trial controller: one fresh conversation per trial from an instruction, typed signature, and versioned agent prompt.
- Add one optional development tool, `run_checks`, accepting candidate source and agent-authored example arguments/expected outputs as data; results return structured per-check pass/fail, actual values, and bounded syntax/runtime diagnostics.
- Enforce interaction limits: at most four logical model calls and three attempted `run_checks` calls per trial, at most four checks per request (twelve development checks per trial); the fourth model call is reserved for final submission with tools disabled; earlier submission allowed. Limits are configurable and fixed across compared variants.
- Retain the existing raw-source final contract; never repair a response or regenerate after final submission.
- Record `no_submission` when no final submission occurs; retain drafts and trace.
- Convert agent-code and tool-argument errors into bounded recovery feedback that consumes the attempted tool call; classify container unavailability and broken worker protocols as infrastructure-incomplete trials.
- Define a model-client interface and deterministic recorded-response fixtures that exercise the loop, tool handling, and stopping behaviour without an API.
- **BREAKING (planning):** supersedes the pilot's single-response/no-internal-revision trial definition.

## Capabilities

### New Capabilities

- `agent-trial-loop`: Run one bounded agent trial with optional development checks, explicit final submission, and API-free fixture verification.

### Modified Capabilities

None. The main capability inventory is empty.

## Impact

New controller/tool modules under `src/codegen_eval/`, a versioned baseline agent prompt file, tool schema definition, fixture files of recorded model responses, and focused tests. Reuses `src/codegen_eval/contract.py` for final validation and the per-check mechanism from `harden-candidate-execution`. No live API client, cost ledger, transport retries, or MLflow are part of this change. Exact module, prompt-file, and fixture names are implementation choices.

Completion evidence: deterministic fixture tests covering successful early submission without tool use, tool use and revision, malformed tool arguments, oversized check batches, recovery, fourth-call tool disabling, missing submission, final contract violations, and infrastructure classification. These validate the controller, not live model quality. Nothing here is implemented.

## Dependencies and milestone

- **Milestone:** Day 1, agent/fixtures timebox (3h) in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan).
- **Upstream:** `harden-candidate-execution` (per-check execution and limits); existing source contract validator.
- **Downstream:** `add-run-bundles-and-grading-replay` (records trials), `add-reviewed-benchmark-and-graders` (hidden grading and accounting of the submitted function), `add-openrouter-client-and-budget-ledger` (live client implementing the interface, transport retries outside the logical-call limit), `add-local-mlflow-tracking` (trace mapping), `add-deterministic-ci`, `run-prompt-comparison` (baseline/revised prompts).

## Traceability

- Wayfinder: [issue 01 — Define the coding agent's behavior and tools](../../../.scratch/revise-project-spec/issues/01-agent-behavior.md), Q12 (scope/tool), Q13–Q15 (limits, feedback, submission contract), Q16–Q17 (stopping/failure behaviour); issue 02 / Q20 (four checks per request); [issue 05](../../../.scratch/revise-project-spec/issues/05-containers-and-evidence.md) Q35 (recorded-response fixtures).
- Specification: [Coding agent and trial contract](../../../docs/project_spec.md#coding-agent-and-trial-contract); [Glossary](../../../GLOSSARY.md) trial/candidate/development check.
