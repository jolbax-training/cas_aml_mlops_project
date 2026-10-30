# Tasks

All tasks are unstarted planning items. Timebox: day 2, API/budget/smoke (3h). Requires `add-bounded-agent-loop` and `add-run-bundles-and-grading-replay`; the smoke test also requires `harden-candidate-execution` probes to pass.

## 1. Configuration and client

- [ ] 1.1 Add versioned model/request configuration (model, pinned `open-inference/fp4` routing, fallbacks disabled, require-parameters, temperature 0.2, top-p 1, `low` reasoning, 2,000 output, 12,000 input, 60-second deadline) and include its hash in bundles.
- [ ] 1.2 Implement the OpenRouter client behind the agent loop's model interface, sending `tool_choice: none` on the final-only call, with SDK retries disabled and credentials read only by the trusted CLI.
- [ ] 1.3 Implement the pre-send input-size check with verified token accounting or a verified conservative bound; test rejection without sending or reserving, reported to the controller as a non-retryable pre-send rejection (trial outcome per `add-bounded-agent-loop`).

## 2. Retries and attempt records

- [ ] 2.1 Implement transient/retryable classification and bounded backoff with one retry per request and two per trial; mark exhausted retries as run-incomplete. Test with deterministic transport doubles, including non-retryable refusal/malformed/truncated cases.
- [ ] 2.2 Record every physical attempt's model/provider metadata, settings, timing, usage, reported cost, reservation, and error class; verify missing fields are marked missing and no credential is written.

## 3. Spending ledger

- [ ] 3.1 Implement the durable shared ledger with write-before-send reservations from verified prices, token caps, recorded CHF conversion, fees, and safety margin; keep reservations for timed-out or usage-missing attempts.
- [ ] 3.2 Using the checkpoint basis the user accepted on 2026-10-30 (design.md), implement the CHF 10 checkpoint (log once and continue) and CHF 15 ceiling refusal; test checkpoint crossing, ceiling refusal, crash-safe ordering, and incomplete marking of blocked work.
- [ ] 3.3 Keep the ledger outside version control and document its location and inputs.

## 4. Smoke test and freeze

- [ ] 4.1 Recheck endpoint capabilities and prices; record the CHF conversion with date and source as a preflight input.
- [ ] 4.2 Run the paid smoke trial through the ledger and retain its trace showing tool call, feedback, final-only tool disabling, final submission, accepted parameters, usage/provider metadata, and output fitting within 2,000 tokens.
- [ ] 4.3 Compute projected total cost (360 main physical attempts plus development/smoke spend) against the CHF 15 ceiling; escalate to the user if it does not fit.
- [ ] 4.4 Freeze settings; document any pre-freeze adjustment and the reproducibility limitation of fixed identifiers.
- [ ] 4.5 Run focused and offline tests; update `docs/progress.md` with frozen settings, smoke evidence location, ledger totals, and observed results, and register a reviewed summary for the work log. Do not describe metadata support as a live result.
