# Design

## Context

See proposal.md. The pilot evaluates a supplied source string against hidden cases; there is no agent loop. The confirmed design adds a trusted host-side controller that talks to a model through an interface, offers one tool, and hands the final submission to existing contract validation and hidden grading. All of this is planned.

## Goals / Non-Goals

**Goals:** Correct trial boundaries; enforced limits; development feedback that never leaks hidden information; explicit final submission graded as returned; deterministic fixtures for the whole loop.

**Non-Goals:** Live OpenRouter calls, cost reservation, transport retries (owned by `add-openrouter-client-and-budget-ledger`); shell, repository, or network tools; multi-agent behaviour; prescribing tool-call sequences; automatic repair.

## Decisions

### 1. Controller state machine

A trial holds: task instruction and typed signature, prompt version, conversation messages, logical call count, attempted tool-call count, candidate history, and terminal status. Each logical model call returns either a `run_checks` tool call or a final submission. Calls 1–3 offer the tool; call 4 is sent with tools disabled (for OpenRouter: `tool_choice` none, verified later in smoke testing) and must be final. Terminal states: submitted, `no_submission`, or infrastructure-incomplete. A model-client failure other than a pre-send rejection (for example `transport_exhausted`, reported by the live client once its transport retries are used up) ends the trial as infrastructure-incomplete with the partial trace kept (project_spec: exhausted transport retries make the run incomplete). Limits come from one configuration object (defaults 4 calls / 3 tool attempts / 4 checks per request) whose hash is recorded.

Transport retries are physical attempts inside one logical call and are not counted here; the client reports them.

### 2. `run_checks` contract

Arguments: candidate source and a list of checks, each with arguments and an expected output, as JSON data rather than test code. The controller validates the request (schema, at most four checks, payload limits), validates candidate source with the existing contract checker, executes each check through the candidate-execution mechanism, and compares actual to the agent's own expected value in trusted code, reusing the pilot's existing strict comparison and mutation detection in `src/codegen_eval/evaluate.py` (`_strict_equal`, mutated-input detection) rather than reimplementing them; `add-reviewed-benchmark-and-graders` later verifies and extends that same code against Q23. Feedback lists per-check pass/fail, actual value, and bounded diagnostics. Malformed arguments, oversized batches (no checks executed), invalid source, and candidate exceptions all consume the attempt and return bounded feedback. Hidden acceptance inputs, expected answers, and scores never appear in feedback.

### 3. Final submission

The final message content is treated as raw Python source and validated by the existing contract (one synchronous function matching name/arguments/annotations, optional standard-library imports; no fences, prose, helpers, nested functions, lambdas, classes, decorators, async, third-party/relative imports, or top-level statements). No stripping or repair. Contract failure is a recorded candidate failure. Grading of a valid submission is delegated to the benchmark/grading change.

How a "final submission" is signalled (plain assistant message vs a dedicated submit tool) is an implementation choice, constrained by: explicit, distinguishable from tool use, and available on call 4 with tools disabled.

### 4. Model-client interface and fixtures

The client owns wire translation: the controller keeps a neutral conversation (tool calls as `{id, name, arguments}`) and the live client converts it to its provider's shape on each send. The controller records `truncated` and `usage` from each response in the `model_call` trace event, and a rejection or failure `detail`; truncation never triggers a retry. Physical-attempt metadata is left to the live client change to define.

The controller depends on a narrow interface: send the rendered request, receive a normalised response (tool call, final content, truncation flag, usage/metadata if present) or a classified failure. A recorded-response fixture client replays scripted responses per call, making tests deterministic and API-free. Fixtures cover: early submission without tool use, tool use then revision, malformed arguments then recovery, oversized batch, fourth-call submission, tool request on call 4, no submission, contract violation, candidate exception feedback, and container unavailability. Fixtures prove controller behaviour, not how a live model would react.

## Open decisions for the user

These were not settled by Q12–Q42. On 2026-10-30 the user accepted the proposed defaults below; implementation uses them.

1. **RESOLVED 2026-10-30 (user accepted the proposed default) — pre-send input-limit rejection (Q31/Q24).** Proposed default: the rejection ends the trial without further model calls; the rejected logical call is consumed; with no final submission the trial is `no_submission` plus a `request_rejected` label, a candidate-side outcome counted within planned denominators (limits are fixed across variants), not infrastructure-incomplete. Alternative: treat it as infrastructure-incomplete, which would exclude the run from headline comparison.
2. **RESOLVED 2026-10-30 (user accepted the proposed default) — submission signalling.** Chosen: a plain final assistant message (keeps the existing strict function contract). Considered: plain final assistant message versus a dedicated submit tool (Decision 3). With a plain message, a non-source final message (including a blank one) is a contract failure; only an absent message (`content` is null) is `no_submission` (label `no_final_message`); with a submit tool, absence of the submit call is `no_submission`. A tool request returned on call 4 despite tools being disabled is `no_submission` under either option. Accounting is identical (issue 03 / Q24) but labels differ, so decide before the fixture tests in task 3.1.
3. **RESOLVED 2026-10-30 (user accepted the proposed default) — multiple tool calls, or content plus a tool call, in one response.** Proposed default: count the response as one attempted tool call, execute only the first `run_checks` call, and return argument-error feedback for the extras in the same feedback; content alongside a tool call is not a final submission. Alternatives: count each call as an attempt, or reject the whole response as malformed arguments.

### Proposed glossary addition (not applied to GLOSSARY.md)

**Infrastructure-incomplete trial**: A trial stopped by container unavailability or a broken worker protocol (issue 01 / Q17), recorded with partial evidence and not scored as an agent-performance failure; it makes its evaluation run incomplete. _Avoid_: counting it as a candidate failure. Add to GLOSSARY.md only with the user's approval.

## Risks / Trade-offs

- Provider may ignore tool disabling on call 4 → treat a tool request on call 4 as a non-submission outcome per the spec; smoke test verifies `tool_choice` none.
- Feedback size growth may exceed the 12,000-token input cap → bounded diagnostics now; the cap itself is enforced by the live client change.
- Strict raw-source contract may reject many live answers → intended; prompt revision addresses it in the experiment.

## Migration Plan

Add the interface, fixture client, controller, tool, and baseline prompt file; wire final validation; add fixture tests; record commands and results in progress. The pilot single-response evaluator remains usable for known candidates. Rollback removes the new modules without affecting the pilot.
