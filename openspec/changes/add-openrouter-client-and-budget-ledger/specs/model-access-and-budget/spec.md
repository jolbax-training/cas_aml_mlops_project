# Model Access and Budget Spec Delta

## Purpose

Provide fixed, observable, cost-bounded OpenRouter model access for the bounded coding agent, with one project-wide spending ledger and a retained smoke test before settings are frozen.

## ADDED Requirements

### Requirement: Pinned model and provider routing
The model client SHALL request `z-ai/glm-5.3-flash` through OpenRouter routed only to the OpenInference `open-inference/fp4` endpoint, with provider fallbacks disabled and support for all requested parameters required. Another endpoint MUST NOT be silently substituted.

Source: issue 04 / Q30, Q32; issue 08.

#### Scenario: Pinned endpoint unavailable
- **WHEN** the pinned endpoint cannot serve a request
- **THEN** the request fails without falling back to another provider and the failure is recorded

### Requirement: Fixed request settings
Every model call SHALL use temperature 0.2, top-p 1, explicit `low` reasoning effort, at most 2,000 output tokens, and a 60-second deadline per physical attempt. The whole rendered request, including history and tool definitions, MUST NOT exceed 12,000 input tokens; oversized requests MUST be rejected before sending. Truncated responses MUST be preserved as returned.

Source: issue 04 / Q31, Q33.

#### Scenario: Oversized request
- **WHEN** a rendered request exceeds 12,000 input tokens by verified accounting or a verified conservative bound
- **THEN** it is not sent, no reservation is charged, and the rejection is recorded and reported to the controller as a non-retryable pre-send rejection

#### Scenario: Truncated output
- **WHEN** a response stops at the output limit
- **THEN** it is retained as returned, without repair or transport retry

### Requirement: Bounded transport retries
The client SHALL retry only transient transport failures and retryable API errors, with bounded backoff, at most one retry per failed request and at most two per trial, outside the four logical model calls. Refusals, malformed responses, truncation, source errors, failed checks, and poor answers MUST NOT trigger transport retries. Unaccounted library retries MUST be disabled. Exhausted retries MUST make the run incomplete.

Source: issue 04 / Q28.

#### Scenario: Third transport failure in a trial
- **WHEN** a trial has already used two transport retries and another request fails transiently
- **THEN** no further retry is sent and the run is marked incomplete due to exhausted transport retries

#### Scenario: Malformed model response
- **WHEN** the model returns a response the loop cannot parse
- **THEN** no transport retry occurs and the loop's failure rules apply

### Requirement: Project-wide spending ledger
One durable ledger SHALL record every paid attempt, including development, smoke tests, main experiments, and retries. Reported costs MUST be recorded separately from estimates and reservations.

Source: issue 04 / Q29.

#### Scenario: Smoke and main calls share the ledger
- **WHEN** smoke-test and main-experiment attempts are made
- **THEN** both are recorded in the same ledger and count toward the same totals

### Requirement: Conservative pre-send reservation
Before each paid attempt the ledger SHALL reserve a conservative maximum cost from verified endpoint prices, enforced token caps, a recorded dated CHF conversion, applicable fees, and a safety margin. Reservations for uncertain charges, including timed-out requests or missing usage, MUST be kept until reconciled.

Source: issue 04 / Q29; issue 08.

#### Scenario: Timed-out attempt
- **WHEN** an attempt times out without reported usage
- **THEN** its reservation remains counted against the budget

### Requirement: CHF checkpoint and ceiling
The ledger SHALL log a single checkpoint entry the first time the checkpoint total reaches CHF 10 and continue automatically; its basis is an open decision in design.md (proposed: committed plus outstanding reservations, as for the ceiling). The client MUST NOT send any request whose reservation would bring total reserved and committed spending above CHF 15. When the ceiling blocks completion, the bundle MUST be preserved and unfinished work marked incomplete.

Source: issue 04 / Q29.

#### Scenario: Crossing the checkpoint
- **WHEN** the checkpoint total first reaches CHF 10
- **THEN** one checkpoint entry is logged and work continues
- **AND** later attempts do not log further checkpoint entries

#### Scenario: Reservation would exceed ceiling
- **WHEN** the next attempt's reservation would push the total above CHF 15
- **THEN** the request is not sent and the affected run is preserved and marked incomplete

### Requirement: Attempt metadata and reproducibility disclosure
Each physical attempt SHALL record the requested model, returned canonical model, actual provider/endpoint/precision metadata, settings, timestamps, latency, token usage, reported cost, reservation, and retry/error classification. Missing metadata MUST be recorded as missing. Credentials and authorization headers MUST NOT be stored. Documentation MUST state that a fixed identifier does not guarantee immutable upstream weights.

Source: issue 04 / Q31, answer; issue 08.

#### Scenario: Inspect an attempt record
- **WHEN** an attempt record is inspected
- **THEN** its provider metadata, usage, and cost fields are present or explicitly marked missing, and no credential appears

### Requirement: Retained functional smoke test
Before the main comparison, endpoint capabilities and prices SHALL be rechecked and a functional smoke trace retained showing a tool call, development feedback, final-only tool disabling, final submission, accepted sampling parameters, returned usage/provider metadata, and code fitting within the 2,000-token reasoning/output allowance. Documented metadata support MUST NOT be reported as a completed live check.

Source: issue 04 / Q31 follow-up, Q32, Q33; issue 08.

#### Scenario: Smoke test reveals insufficient output allowance
- **WHEN** reasoning consumes the output allowance before final code is produced
- **THEN** the failure is retained and settings are not frozen until a documented pre-freeze adjustment is made and smoke-tested

### Requirement: Settings freeze with projected cost
Settings SHALL be frozen only after the smoke test passes and the projected total cost, covering 360 main physical attempts plus development and smoke spend, is verified within the CHF 15 ceiling. Pre-freeze adjustments MUST be documented; model, provider, or settings changes after baseline MUST require comparable reruns.

Source: issue 04 / answer; issue 08.

#### Scenario: Projected cost exceeds the ceiling
- **WHEN** the projection does not fit the remaining budget
- **THEN** settings are not frozen and the main runs do not start

### Requirement: Smoke-only final-only exercise option
The smoke command SHALL offer an opt-in `--exercise-final-only` option that appends a fixed, hashed smoke instruction to the task message asking the model to call `run_checks` on each of its three tool attempts before giving the final answer. The final-only request MUST be built by the normal controller (full history, `tool_choice: none`, tools resent), never scripted or injected.

Source: coordinator evidence 2026-11-01; user decision to add a smoke-only option and re-smoke once.

#### Scenario: Scripted model keeps calling tools
- **WHEN** the smoke runs with the option against a fake transport whose model keeps calling `run_checks`
- **THEN** a fourth request is sent with `tool_choice: none` and the full history, and `calibrate` passes on the resulting bundle

#### Scenario: Model submits early despite the instruction
- **WHEN** the model submits before the fourth call
- **THEN** the trace is retained, `calibrate` still reports the missing final-only call, and no automatic paid retry occurs

### Requirement: Smoke option isolation and identity
The smoke option MUST NOT change the model configuration or `config_hash`, the versioned experiment prompts, the agent limits, or controller semantics, and MUST NOT exist on the experiment `run` path. Without it, the initial messages, request payload, and the non-smoke identity sections MUST be unchanged and no `smoke` section is added; with it, the identity MUST record the smoke mode and instruction hash.

#### Scenario: Option not given
- **WHEN** the smoke runs without the option
- **THEN** the initial messages, the serialized request payload, and the identity sections `model`, `prompt`, `agent_limits`, `execution_limits` and `benchmark` are unchanged from the previous behavior and no `smoke` identity section is added

#### Scenario: Model configuration hash unchanged
- **WHEN** the smoke runs with and without the option
- **THEN** the recorded `config_hash` is identical in both bundles and equals the `model_config_hash` recorded in the experiment configuration

#### Scenario: Bundle identifies the smoke mode
- **WHEN** a bundle is made with the option
- **THEN** its identity records mode `exercise_final_only` and the instruction hash, it has no experiment section, and an experiment run's schedule verification does not accept it as an experiment trial

#### Scenario: Flagged bundle is accepted by freeze and run preconditions
- **WHEN** `calibrate`, settings freeze, and the `run` precondition "retained smoke bundle still passes calibration" evaluate a bundle made with the option
- **THEN** none rejects it for its prompt or identity, and the freeze record discloses the smoke mode

#### Scenario: Experiment path cannot produce a flagged bundle
- **WHEN** the experiment command line is given `--exercise-final-only`, or a bundle is produced by `run_variant`
- **THEN** the command line rejects the option and the bundle never carries an `identity.smoke` section
