# Design

## Context

See proposal.md. Research (issue 08) found that `open-inference/fp4` advertises the agreed sampling parameters, tool calling, and `tool_choice` `auto`/`none`; that the native `z-ai/fp8` endpoint advertises `tool_choice.none:false` and must not be silently substituted; that GLM reasoning is mandatory with efforts `low`/`high`/`max` (default `max`); and a dated price snapshot of USD 0.0052/M input and USD 0.1985/M output. At the enforced caps, 360 main physical attempts give a USD 0.165384 token-price envelope excluding development calls, fees, FX, and margin. These are documented, dated inputs, not tested behavior or a permanent price guarantee. CHF conversion was left as a recorded preflight input.

## Goals / Non-Goals

**Goals:** Fixed, observable model access; requests bounded before sending; accounted retries; a single ledger that cannot exceed CHF 15 in reservations; a retained smoke test and frozen settings.

**Non-Goals:** Running the comparison (owned by `run-prompt-comparison`), choosing other models/providers, prompt design, or exact billing reconciliation beyond recorded reported costs.

## Decisions

### 1. Pinned routing and settings

Send requests with model `z-ai/glm-5.3-flash`, provider order restricted to `open-inference/fp4`, fallbacks disabled, and require-parameters enabled. Settings: temperature 0.2, top-p 1, reasoning effort `low`, `max_tokens` 2,000, 60-second per-attempt timeout. The final (fourth) logical call sends `tool_choice: none`. Configuration is a versioned file whose hash enters the bundle. Exact client library (OpenAI-compatible SDK or plain HTTP) is an implementation choice; SDK automatic retries are disabled.

### 2. Pre-send size check

Before sending, compute the rendered request's input tokens with verified token accounting or a verified conservative bound; reject over 12,000 tokens without sending and without charging a reservation. The rejection is recorded and reported to the controller as a distinct pre-send rejection (not a transport failure, never retried). Its trial outcome is defined by the agent-trial-loop requirement "Pre-send request rejection ends the trial" in `add-bounded-agent-loop`, whose classification is an OPEN DECISION FOR THE USER recorded in that change's design.md.

### 3. Transport retries

Retry only transient transport failures and retryable API errors (for example connection errors, timeouts, rate-limit or 5xx responses — exact classification is an implementation choice documented in code and tests). One retry per failed request, two per trial, bounded backoff. Refusals, malformed responses, truncation, source errors, failed checks, and poor answers are never transport retries. When retries are exhausted, raise an infrastructure outcome so the run becomes incomplete. Every physical attempt is recorded.

### 4. Spending ledger

A single append-only ledger file (location outside Git, an implementation choice) shared by all commands. For each attempt: compute reservation = (input cap × input price + output cap × output price) × recorded CHF conversion × (1 + safety margin) + applicable fees, using verified endpoint prices with their check date. Refuse if committed + reserved + new reservation > CHF 15. Record the CHF 10 crossing once as a checkpoint and continue (basis: see open decision below). After the response, record reported cost separately; release a reservation only when the charge is known. Timed-out, disconnected, or missing-usage attempts keep their reservation — missing usage is never treated as free. Write-before-send ordering ensures a crash cannot leave an unrecorded paid attempt.

The safety margin value and fee inputs are implementation inputs recorded in the ledger; no value is fixed by the planning decisions.

### 5. Attempt metadata

Store per attempt: requested model, returned canonical model, provider/endpoint/precision, request settings, timestamps, latency, token usage, reported cost, reservation, retry index, and error classification. Missing metadata is recorded as missing. Credentials and authorization headers are never written.

### 6. Smoke test and freeze

Before freezing, recheck endpoint capabilities and prices, record the CHF conversion and its date/source, and run a small smoke trial on a pilot or benchmark task that exercises a tool call, development feedback, final-only tool disabling, and final submission. Verify sampling parameters are accepted, usage/provider metadata is returned, and reasoning plus code fit within 2,000 output tokens. Retain the trace. Compute the projected total cost (main 240 logical + 120 retries = 360 attempts, plus development/smoke already spent) and confirm it fits the ceiling. Document any pre-freeze adjustment as a decision; changes after baseline require comparable reruns.

## Open decisions for the user

1. **RESOLVED 2026-10-30 (user accepted the proposed default) — CHF 10 checkpoint basis (Q29).** Q29 says "Record a CHF 10 checkpoint and continue automatically" without saying whether reservations count. Proposed default: same basis as the ceiling (committed plus outstanding reservations), logged once at first crossing. Alternative: committed/reported spending only. Work continues either way; only checkpoint timing differs.
2. The trial outcome of a pre-send input-limit rejection was resolved on 2026-10-30 (accepted default) in `add-bounded-agent-loop/design.md`; this change only reports the rejection.

## Risks / Trade-offs

- Endpoint unavailable or behaving differently than advertised → record the smoke failure and escalate to the user; do not silently substitute another endpoint.
- Reasoning consumes the output allowance → detected by the smoke test; any adjustment is a documented pre-freeze decision, re-smoke-tested before freezing.
- Price changes → recheck before running; ledger uses dated verified prices.
- Upstream model changes under a fixed identifier → record canonical/provider metadata and disclose changes.

## Migration Plan

Implement config, client, size check, retry policy, and ledger with deterministic fixtures first (no credentials). Then perform the paid smoke test through the ledger, retain its trace, freeze settings, and record evidence in progress. Rollback removes the client; the ledger file is retained as spending evidence.

## Amendment 2026-11-02: smoke-only final-only exercise

### Evidence

The paid smoke ran 6 times (`strings_01`, `parsing_formatting_02`, `numeric_logic_02`, `parsing_formatting_01`, `dictionaries_02`, `lists_02`). Every trial submitted after 2-3 model calls, so none reached the final-only call. `experiment_cli calibrate` rejects every bundle only with "the smoke trace shows no final-only call (tool_choice none)". The bound/actual prompt-token ratios were 1.923-2.100 against a required minimum of 1.1, so the bound itself is not in question. Under the existing controller a model that submits on call 2 or 3 never triggers call 4, and the calibration gate (4.4) is unreachable by luck-based smokes. The user chose to add a smoke-only option that drives one trial to the final-only call, then re-smoke once.

### Decisions

A1. **Opt-in `smoke --exercise-final-only`.** Without the flag the initial messages, the serialized request payload, and the identity sections `model`, `prompt`, `agent_limits`, `execution_limits` and `benchmark` are unchanged from today, and no `smoke` section is added. (Whole bundles are not byte-identical: `evaluator_revision`, `evaluator_source_sha256`, `runtime`, run ID and timestamps change with any code edit.) The flag exists only on `openrouter_cli smoke`; `experiment_cli run` has no such option and cannot be given one.

A2. **Mechanism: a smoke-only instruction appended to the user message.** When the flag is set, a fixed text (a constant in the smoke code with its own sha256, not a versioned experiment prompt) is appended after the signature in the initial user message. It asks the model to call `run_checks` on each of its three tool attempts, developing and testing its checks, and only then give the final answer. This is a smoke-only exception to the project-spec sentence that only instruction, signature and the versioned prompt enter the initial model request; it is disclosed in the bundle identity, the freeze record and `docs/progress.md`, and experiment trials still receive only the instruction, signature and versioned prompt. The system prompt, tool schema, agent limits (4 calls / 3 tool attempts / 4 checks per request) and `run_trial` semantics are unchanged; `run_trial` gains an optional, default-empty user-message suffix and nothing else. The controller then reaches the fourth call naturally.

A3. **The fourth call is real.** Nothing is faked, scripted, or injected: the fourth request is built by the normal controller with the full history (including the instruction and three tool results), `tool_choice: none`, and the tool definitions still resent. The pre-send bound is therefore calibrated on a realistic fourth-call request, which is the point of 4.4.

A4. **Model configuration unchanged.** The flag does not touch `ModelConfig`, request settings, or `identity()["config_hash"]`. Calibrate's equality check against the frozen `config_hash` keeps working; a test asserts the hash is identical with and without the flag.

A5. **The bundle records the smoke mode.** With the flag, `run_recorded` receives `identity_extra={"smoke": {"mode": "exercise_final_only", "instruction_sha256": ..., "instruction": ...}}`. Without it no `smoke` section is added (so existing smoke bundles stay as they are). The system prompt section (`prompt.version` / `prompt.sha256`) still shows the baseline prompt, because the system prompt is not changed; the appended instruction is visible in the recorded messages and in the `smoke` section. Such a bundle has no `identity.experiment` section, so `verify_schedule` for a comparison run can never accept it as an experiment trial.

A6. **Compatibility with calibrate, freeze-settings, and `run`.** Checked in `src/codegen_eval/experiment.py`: `calibrate` compares only the client, `config_hash`, trial status, tool attempts, `tool_choice` none, bound/prompt ratios, and output cap, not the prompt or the user message; `write_settings_freeze` stores the bundle path, run ID, and manifest hash; the `run` precondition re-hashes the manifest, compares the container image, and re-runs `calibrate`. None compares the smoke bundle's prompt, so a flagged bundle passes unchanged. `write_settings_freeze` additionally records `smoke.mode` (`standard` or `exercise_final_only`, read from `identity.smoke.mode` and defaulting to `standard` when the section is absent) in the freeze record as disclosure, with no gate on it. Honest limitation: the retained trace is of a prompted fourth call rather than an organic one; the freeze record and `docs/progress.md` state this.

A7. **Early submission is still possible.** The instruction asks, it does not force. The model may still submit early or skip tool calls, and then the bundle fails calibrate again. The option does not retry by itself: each smoke is one trial; the coordinator caps paid retries with the user's approval and chooses the task. Rejected alternatives: (a) scripting or injecting tool turns, which would make the fourth request unrealistic; (b) lowering the agent limits for the smoke, which changes the controller contract; (c) a second system prompt, which would put a new prompt hash in the bundle and blur it with experiment prompts; (d) waiving the calibrate final-only requirement, which removes the evidence the gate exists for. No reason against the coordinator's preferred approach was found.

### Risks added

- The model ignores the instruction and submits early → calibrate fails again; the failure is retained; paid retries need user approval.
- A forced trial uses more calls (up to 4 attempts) than an organic one → still within the per-attempt reservation and the ledger ceiling; the coordinator checks the projected spend before approving.
