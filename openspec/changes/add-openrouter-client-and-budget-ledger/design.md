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

1. **OPEN DECISION FOR THE USER — CHF 10 checkpoint basis (Q29).** Q29 says "Record a CHF 10 checkpoint and continue automatically" without saying whether reservations count. Proposed default: same basis as the ceiling (committed plus outstanding reservations), logged once at first crossing. Alternative: committed/reported spending only. Work continues either way; only checkpoint timing differs.
2. The trial outcome of a pre-send input-limit rejection is an open decision recorded in `add-bounded-agent-loop/design.md`; this change only reports the rejection.

## Risks / Trade-offs

- Endpoint unavailable or behaving differently than advertised → record the smoke failure and escalate to the user; do not silently substitute another endpoint.
- Reasoning consumes the output allowance → detected by the smoke test; any adjustment is a documented pre-freeze decision, re-smoke-tested before freezing.
- Price changes → recheck before running; ledger uses dated verified prices.
- Upstream model changes under a fixed identifier → record canonical/provider metadata and disclose changes.

## Migration Plan

Implement config, client, size check, retry policy, and ledger with deterministic fixtures first (no credentials). Then perform the paid smoke test through the ledger, retain its trace, freeze settings, and record evidence in progress. Rollback removes the client; the ledger file is retained as spending evidence.
