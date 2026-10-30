# Agent Trial Loop Spec Delta

## Purpose

Run one bounded trial of the function-writing agent with an optional development-check tool and explicit final submission, verifiable without a model API.

## ADDED Requirements

### Requirement: Trial boundary
A trial SHALL be one fresh conversation for one coding task, starting from the instruction, typed function signature, and versioned agent prompt only. All candidates, development checks, feedback, and revisions within it MUST belong to that single trial, and the trial MUST NOT receive earlier-trial results. Source: issue 01 / Q12, Q17; issue 04 / Q26.

#### Scenario: Agent revises twice
- **WHEN** the agent submits two development candidates before final submission
- **THEN** one trial is recorded containing both candidates
- **AND** no additional trial is created

### Requirement: Optional development tool
The agent SHALL have exactly one optional tool, `run_checks`, accepting candidate source and agent-authored example arguments with expected outputs as structured data. General shell, repository editing, and network tools MUST NOT be offered. Source: issue 01 / Q12–Q13.

#### Scenario: Submission without tool use
- **WHEN** the agent submits a final function on its first call without calling `run_checks`
- **THEN** the submission is graded normally
- **AND** lack of tool use is not itself a failure

### Requirement: Structured bounded development feedback
`run_checks` SHALL execute each agent-authored check through the shared candidate-execution mechanism and return per-check pass/fail, actual values, and bounded syntax/runtime diagnostics. Hidden acceptance inputs, expected answers, and scores MUST NOT appear in development feedback. Source: issue 01 / Q13–Q14; issue 02 / Q19.

#### Scenario: Failing development check
- **WHEN** an agent-authored check's actual value differs from its expected output
- **THEN** feedback reports that check as failed with the actual value
- **AND** no hidden acceptance information is included

### Requirement: Interaction limits
Each trial SHALL permit at most four logical model calls, at most three attempted `run_checks` calls, and at most four checks per request, so at most twelve development checks run before hidden grading. The fourth model call MUST be reserved for final submission with the tool disabled; earlier submission MUST be allowed. Limits SHALL be configurable, recorded, and fixed across compared variants. Transport retries are not logical calls. Source: issue 01 / Q13, Q16; issue 02 / Q20; issue 04 / Q28.

#### Scenario: Fourth call
- **WHEN** three logical calls have completed without final submission
- **THEN** the fourth request is sent with the tool disabled

#### Scenario: Oversized check batch
- **WHEN** a `run_checks` request contains more than four checks
- **THEN** no checks execute, argument-error feedback is returned, and the attempt is consumed

### Requirement: Recovery feedback for agent errors
Agent source errors, failed development checks, candidate exceptions, and malformed tool arguments SHALL consume the attempted tool call and return bounded feedback, allowing recovery within the remaining allowance. Source: issue 01 / Q16–Q17.

#### Scenario: Malformed tool arguments then recovery
- **WHEN** a tool call has malformed arguments and a later call is valid
- **THEN** the first attempt counts toward the three-attempt limit with error feedback
- **AND** the later call executes normally

### Requirement: Final submission contract without repair
The final submission SHALL be explicit and validated as raw Python source under the existing source contract: exactly one synchronous function matching the requested name, arguments, and annotations, with optional standard-library imports only. The system MUST NOT repair the response or generate another answer after final submission, and contract violations SHALL be recorded candidate failures. Source: issue 01 / Q15.

#### Scenario: Disallowed constructs
- **WHEN** the final source contains prose, helper or nested functions, lambdas, classes, decorators, async functions, third-party or relative imports, or top-level executable statements
- **THEN** it is recorded as a contract failure

#### Scenario: Fenced final answer
- **WHEN** the final submission is wrapped in Markdown fences
- **THEN** it is recorded as a contract failure without stripping the fences
- **AND** no new model call is made

### Requirement: Missing submission
If a trial ends without a final submission, the system SHALL record `no_submission` and retain drafts and the trace for inspection. Source: issue 01 / Q16.

#### Scenario: Limits exhausted without submission
- **WHEN** the fourth call returns no final submission, for example only a tool request despite the tool being disabled
- **THEN** the trial outcome is `no_submission`, not a contract failure; a submitted but invalid source remains a contract failure
- **AND** all candidates and messages are retained

#### Scenario: Non-source final message
- **WHEN** a final message is present but is not valid source (for example prose)
- **THEN** it is labelled a contract failure under the chosen plain-final-message signalling (resolved 2026-10-30; see design.md); accounting is identical to `no_submission` under issue 03 / Q24

### Requirement: Infrastructure-incomplete trials
Container unavailability and broken worker protocols during a trial SHALL make the trial incomplete due to infrastructure rather than an agent-performance failure. Source: issue 01 / Q17.

#### Scenario: Container fails during development check
- **WHEN** Podman cannot start a container for a development check
- **THEN** the trial is marked infrastructure-incomplete, not a candidate failure

#### Scenario: Model client reports exhausted transport retries
- **WHEN** the model client returns a failure other than a pre-send rejection, such as `transport_exhausted`
- **THEN** the trial ends as infrastructure-incomplete with its drafts, messages, and trace retained

### Requirement: API-free recorded-response fixtures
The controller SHALL depend on a model-client interface, and deterministic recorded-response fixtures MUST verify tool handling and stopping behaviour without a model API or credentials. Fixture results MUST NOT be presented as live model behaviour. Source: issue 05 / Q35; spec Evidence, MLflow, CI, and replay.

#### Scenario: Fixture suite runs offline
- **WHEN** the fixture tests run with no API key or network
- **THEN** they exercise early submission, tool use, recovery, oversized batches, fourth-call disabling, no submission, contract failure, and infrastructure classification

### Requirement: Pre-send request rejection ends the trial
When the model client rejects a rendered request before sending because it exceeds the 12,000-token input limit, the controller SHALL make no further model calls in that trial and MUST record the rejection. The trial outcome SHALL follow the proposed default below until the user decides the open decision in design.md. Source: issue 04 / Q31; issue 03 / Q24; classification not settled by the sources.

#### Scenario: Input limit exceeded on a later call
- **WHEN** the third logical call's rendered request exceeds 12,000 input tokens
- **THEN** it is not sent, no further model calls are made, and the trial records the rejection
- **AND** under the accepted default (resolved 2026-10-30) the rejected call is consumed and the trial is `no_submission` labelled `request_rejected`, a candidate-side outcome counted within planned denominators rather than infrastructure-incomplete

### Requirement: Deterministic handling of multi-part responses
A model response containing more than one tool call, or both final content and a tool call, SHALL be handled by one documented deterministic rule that is recorded in the trace and counts toward the three-attempt limit. The rule itself is an open decision recorded in design.md. Source: issue 01 / Q13, Q16 (attempt accounting); rule not settled by the sources.

#### Scenario: Two tool calls in one response
- **WHEN** a response contains two `run_checks` calls
- **THEN** the controller applies the documented rule and records how many attempts were consumed
