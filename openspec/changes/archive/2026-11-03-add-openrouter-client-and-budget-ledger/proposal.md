# Proposal

## Why

The agent loop needs live model access whose settings are fixed, observable, and bounded in cost. The user confirmed a specific model, pinned endpoint, request settings, transport-retry policy, and a project-wide CHF budget (issue 04, Q28–Q33), supported by primary-source research (issue 08). None of this exists yet: there is no OpenRouter client, spending ledger, or smoke trace.

## What Changes

- Add an OpenRouter model client implementing the agent loop's model interface for `z-ai/glm-5.3-flash`, pinned to OpenInference `open-inference/fp4` with provider fallbacks disabled and required parameter support.
- Enforce request settings: at most 12,000 input tokens for the whole rendered request (history and tool definitions included), 2,000 output tokens per call, temperature 0.2, top-p 1, explicit `low` reasoning effort, and a 60-second deadline per physical attempt. Reject oversized requests before sending; preserve truncated responses as returned.
- Implement transport retries: one retry per failed request, at most two per trial, outside the four logical model calls, with bounded backoff for transient/retryable API failures only. Disable unaccounted SDK retries. Exhausted retries make the run incomplete.
- Add one durable project-wide spending ledger for every paid attempt (development, smoke, main runs, retries). Reserve a conservative maximum cost before each attempt; log a CHF 10 checkpoint and continue; refuse any attempt whose reservation would exceed CHF 15.
- Record requested model, canonical identifier, actual provider/endpoint/precision metadata, usage, reported cost, and reservations for every attempt.
- Run and retain a functional smoke test against the selected endpoint, then freeze settings for the comparison.

## Capabilities

### New Capabilities

- `model-access-and-budget`: Pinned OpenRouter model access, request limits, transport retries, attempt metadata, a shared CHF spending ledger, and the pre-freeze smoke test.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation adds a model-client module, configuration for model/provider/settings and budget inputs, a persistent ledger file outside version control, attempt records written into run bundles, deterministic fixtures for retries/limits/budget refusal, and a retained smoke trace. It adds an HTTP/SDK dependency locked through uv if needed. API credentials stay in the trusted host CLI environment only and never enter candidate containers, bundles, or reports.

Completion evidence: deterministic tests of size rejection, retry limits, reservation/checkpoint/ceiling behavior; a retained smoke trace showing tool call, development feedback, final-only tool disabling, accepted sampling parameters, usage/provider metadata, and code fitting within the 2,000-token allowance; a verified projected total cost; and a progress entry recording frozen settings. No experiment results are produced here.

## Dependencies and milestone

- **Milestone:** Day 2, API/budget/smoke (3h) in the four-day plan of [the specification](../../../docs/project_spec.md). Exit evidence: verified live tool interaction and accounting.
- **Upstream:** `add-bounded-agent-loop` (2) defines the model interface, tool schema, and final-only fourth call; `add-run-bundles-and-grading-replay` (3) stores attempt records. `harden-candidate-execution` (1) must pass before any live candidate executes during the smoke test.
- **Downstream:** `run-prompt-comparison` (9) uses the frozen settings and the ledger; `add-local-mlflow-tracking` (7) records usage/cost; `add-deterministic-ci` (8) runs the API-free fixtures without credentials.
- **Optional / out of scope:** Additional models or providers, a model comparison study, paid CI.

## Traceability

- Wayfinder [issue 04](../../../.scratch/revise-project-spec/issues/04-experiment-design.md): Q28 (transport retries), Q29 (spending ledger), Q30 (model), Q31 and follow-up (request settings, temperature verification), Q32 (provider pinning), Q33 (low reasoning effort); answer bullet on 360 physical attempts.
- Wayfinder [issue 08](../../../.scratch/revise-project-spec/issues/08-openrouter-model-research.md): research input — canonical slug `z-ai/glm-5.3-flash-20260826`, endpoint tool/`tool_choice` support, dated price snapshot, CHF conversion as a preflight input; [retained findings](https://github.com/jolbax-training/cas_aml_mlops_project/blob/44d1fff8e7d5c947c56c50e4fec355f47991f08a/docs/research/openrouter-model-choice.md).
- Specification sections: "Experiment and model configuration" and "Transport retries and spending".
