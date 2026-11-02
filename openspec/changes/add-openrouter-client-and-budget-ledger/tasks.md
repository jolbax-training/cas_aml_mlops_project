# Tasks

Tasks 1.1-3.3 are implemented and tested offline with a fake transport (no paid call); 4.1-4.5 remain deferred to the end (paid smoke, freeze). Timebox: day 2, API/budget/smoke (3h). Requires `add-bounded-agent-loop` and `add-run-bundles-and-grading-replay`; the smoke test also requires `harden-candidate-execution` probes to pass.

## 1. Configuration and client

- [x] 1.1 Add versioned model/request configuration (model, pinned `open-inference/fp4` routing, fallbacks disabled, require-parameters, temperature 0.2, top-p 1, `low` reasoning, 2,000 output, 12,000 input, 60-second deadline) and include its hash in bundles.
- [x] 1.2 Implement the OpenRouter client behind the agent loop's model interface, sending `tool_choice: none` on the final-only call, with SDK retries disabled and credentials read only by the trusted CLI.
- [x] 1.3 Implement the pre-send input-size check with verified token accounting or a verified conservative bound; test rejection without sending or reserving, reported to the controller as a non-retryable pre-send rejection (trial outcome per `add-bounded-agent-loop`).

## 2. Retries and attempt records

- [x] 2.1 Implement transient/retryable classification and bounded backoff with one retry per request and two per trial; mark exhausted retries as run-incomplete. Test with deterministic transport doubles, including non-retryable refusal/malformed/truncated cases.
- [x] 2.2 Record every physical attempt's model/provider metadata, settings, timing, usage, reported cost, reservation, and error class; verify missing fields are marked missing and no credential is written.

## 3. Spending ledger

- [x] 3.1 Implement the durable shared ledger with write-before-send reservations from verified prices, token caps, recorded CHF conversion, fees, and safety margin; keep reservations for timed-out or usage-missing attempts.
- [x] 3.2 Using the checkpoint basis the user accepted on 2026-10-30 (design.md), implement the CHF 10 checkpoint (log once and continue) and CHF 15 ceiling refusal; test checkpoint crossing, ceiling refusal, crash-safe ordering, and incomplete marking of blocked work.
- [x] 3.3 Keep the ledger outside version control and document its location and inputs.

## 4. Smoke test and freeze

- [ ] 4.1 Recheck endpoint capabilities and prices; record the CHF conversion with date and source as a preflight input.
- [ ] 4.2 Run the paid smoke trial through the ledger using the forced smoke (`smoke --exercise-final-only`, section 5), because unforced smokes never reach the final-only call; the smoke command records `input_token_bound` against reported `prompt_tokens` per attempt. Retain its trace showing tool call, feedback, final-only tool disabling, final submission, accepted parameters, usage/provider metadata, and output fitting within 2,000 tokens.
- [ ] 4.3 Compute projected total cost (360 main physical attempts plus development/smoke spend) against the CHF 15 ceiling; escalate to the user if it does not fit.
- [ ] 4.4 Calibration gate: from the smoke attempts compare the pre-send `input_token_bound` with reported `usage.prompt_tokens`; the bound must be at or above the actual count with margin and not reject realistic fourth-call requests, otherwise change `input_bound_ascii_chars_per_token` (or use a verified tokenizer) and re-smoke; record the observed ratio and decision in `docs/progress.md`. The comparison MUST NOT start until this passes. Then freeze settings; document any pre-freeze adjustment and the reproducibility limitation of fixed identifiers.
- [ ] 4.5 Run focused and offline tests; update `docs/progress.md` with frozen settings, smoke evidence location, ledger totals, and observed results, and register a reviewed summary for the work log. Do not describe metadata support as a live result.

## 5. Smoke-only final-only exercise (amendment 2026-11-02; implement before re-running 4.2)

- [ ] 5.1 Add an optional user-message suffix to `run_trial`/`run_recorded` (default none, controller semantics unchanged) and the `--exercise-final-only` flag on `smoke` only, with the fixed instruction text and its sha256; record `identity.smoke` (mode, instruction hash) only when the flag is set; extend the `smoke` section of the freeze record written by `write_settings_freeze` with `mode`, read from `identity.smoke.mode` and defaulting to `standard` when the section is absent. Verify: with the flag a fake-transport scripted model that keeps calling `run_checks` makes a 4th request with `tool_choice: none`, full history, and tools resent; `experiment_cli` rejects `--exercise-final-only`, and a bundle from `run_variant` never carries `identity.smoke`.
- [ ] 5.2 Verify no-flag invariance: the initial messages and the serialized request payload without the flag match a golden fixture captured before the change, the identity sections `model`, `prompt`, `agent_limits`, `execution_limits` and `benchmark` are unchanged and no `smoke` section is present, and `config_hash` is identical with and without the flag and equals the `model_config_hash` in the experiment configuration.
- [ ] 5.3 Verify compatibility offline: `calibrate` passes on the bundle produced by 5.1; `write_settings_freeze` records `smoke.mode`; the `run` smoke-bundle precondition accepts it; a flagged bundle is not accepted by experiment schedule verification; a scripted early-submission model still fails calibrate with the missing final-only message.
- [ ] 5.4 Run the full offline suite, `scripts/build_work_log.py --check`, and `openspec validate add-openrouter-client-and-budget-ledger --strict`. The re-smoke itself is a paid call owned by the coordinator after user approval and stays under 4.2; record in `docs/progress.md` that the retained trace is of a prompted fourth call.
