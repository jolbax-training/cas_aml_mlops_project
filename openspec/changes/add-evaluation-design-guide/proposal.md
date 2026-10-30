# Proposal

## Why

One goal of the project is transferable understanding of agent evaluation. A reusable guide plus a worked design for a different kind of agent system — a research-workflow orchestrator — shows the method applies beyond the implemented coding agent, without building a second system.

## What Changes

- Write a reusable evaluation-design guide covering how to define success, select tasks and graders, validate graders, inspect traces, interpret variability, and decide whether a change helps.
- Pair it with a design-only worked example: a research coordinator that splits work into items, one worker and one fresh-context independent verifier per item, and a final check across all items.
- Use the recent OpenRouter investigation as the concrete illustration, with work items for model controls, provider compatibility, and pricing/budget accounting.
- Specify six scenarios — normal completion, missing work item, unsupported worker claim, conflicting item results, worker/verifier failure, budget exhaustion — including a case where items pass individually but combine inconsistently.
- For each scenario give inputs, capabilities, expected outcomes/failure handling, graders, and required trace evidence; label illustrative traces and proposed graders/rubrics as design.

## Capabilities

### New Capabilities

- `evaluation-design-guide`: A reusable agent-evaluation design method with a worked, design-only orchestrator example.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation adds Markdown documentation (guide and worked example; exact paths are an implementation choice) and registers it as a work-log source. No code, services, API calls, or second agent system are introduced.

## Dependencies and milestone

- **Milestone:** Day 4, "transfer guide/example" timebox (2h) in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan).
- **Upstream (conceptual only):** `add-reviewed-benchmark-and-graders` supplies the task/trial/check/run vocabulary, grader-validation, and accounting concepts the guide generalizes; lessons from `run-prompt-comparison` may be referenced if they exist. There is no runtime dependency; drafting can start earlier if time allows.
- **Downstream:** `add-local-html-work-log` includes the guide/example; `prepare-reproducible-demo` presents it.
- **Optional/excluded:** Implementing the orchestrator, running verifiers, or calibrating an LLM judge is out of scope.

Completion evidence is the guide and the six-scenario worked example in the repository, reviewed against this spec, with every illustrative trace and proposed grader explicitly labelled. No orchestrator execution or judge calibration is claimed.

## Traceability

- Wayfinder [issue 06](../../../.scratch/revise-project-spec/issues/06-orchestrator-transfer.md): Q38 (coordinator/worker/verifier/final-check structure), Q39 (six scenarios), Q40 (guide plus worked design), Q41 (fresh-context verifier independence); [issue 03](../../../.scratch/revise-project-spec/issues/03-benchmark-and-graders.md) Q22 (LLM judge may be discussed only as design).
- Specification: "Transferable evaluation-design guide and example" in [docs/project_spec.md](../../../docs/project_spec.md); GLOSSARY.md workflow-orchestrator terms; completion checklist item on the guide.
