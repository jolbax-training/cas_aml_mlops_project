# benchmark-and-grading Specification

## Purpose
Provide a reviewed, frozen coding-task benchmark and deterministic, fixed-denominator grading of final submissions for the bounded coding agent.

## Requirements

### Requirement: Ten-task balanced benchmark
The benchmark SHALL contain ten tasks, two each in strings, lists, dictionaries, numeric logic, and parsing/formatting. Each task MUST have exactly four hidden acceptance checks: two ordinary and two edge cases, giving forty checks and twenty edge cases per trial of every task. Pilot tasks MUST be re-reviewed before inclusion.

Source: issue 03 / Q21.

#### Scenario: Validate benchmark structure
- **WHEN** the benchmark is loaded
- **THEN** validation confirms ten unique task IDs, two per category, four uniquely identified cases per task with two ordinary and two edge cases, and arguments matching each typed signature
- **AND** any deviation fails validation with a diagnostic

### Requirement: Independent reference validation and review evidence
Every task SHALL have an unambiguous instruction and typed signature, a separately reasoned reference solution, and reviewed expected answers. Review evidence MUST record reviewer, date, derivation/reference, corrections, task/case IDs, and benchmark version/hash. An additional unreviewed model answer MUST NOT count as independent validation.

Source: issue 03 / Q22.

#### Scenario: Reference disagrees with an expected answer
- **WHEN** a reference solution produces a result different from a reviewed expected answer
- **THEN** the benchmark is not frozen until the discrepancy is resolved and the correction is recorded in the review evidence

### Requirement: Frozen versioned benchmark
The benchmark and its review evidence SHALL be frozen with a recorded version and content hash before the baseline run. Any change after freezing MUST create a new version and require comparable reruns or rescoring.

Source: issue 03 / Q21, Q22; specification "Benchmark, graders, and evaluator validation".

#### Scenario: Edit after freeze
- **WHEN** a task or expected answer changes after freezing
- **THEN** the content hash changes, a new benchmark version is recorded, and earlier runs are not compared against it without rerunning

### Requirement: Strict deterministic comparison
Grading SHALL use strict recursive type-aware equality over JSON-compatible strings, integers, booleans, lists, string-keyed dictionaries, and null where required: list order matters and dictionary key order does not. Inputs MUST remain unchanged. Floating-point tolerance, invalid-input-type tasks, and expected-exception tasks MUST be excluded. Comparison and expected answers MUST remain in trusted orchestration.

Source: issue 03 / Q23.

#### Scenario: Type-confusable result
- **WHEN** a candidate returns `1` where `True` is expected, or a list in a different order
- **THEN** the check fails as a wrong answer

#### Scenario: Input mutation
- **WHEN** a candidate returns the correct value but mutates an argument
- **THEN** the check fails with a mutation label

### Requirement: Trial success and diagnostics
A trial SHALL pass only when its submitted final source satisfies the source contract and all four hidden acceptance checks pass without input mutation. Per-check results and all applicable failure labels MUST be retained. Tool use, revisions, recovery, latency, and cost MUST be diagnostics only; optional tool use or a particular action sequence MUST NOT determine success.

Source: issue 03 / Q23.

#### Scenario: Early submission without tool use
- **WHEN** the agent submits on its first model call without calling `run_checks` and the final function passes all four hidden checks
- **THEN** the trial is recorded as successful

### Requirement: Fixed-denominator accounting
Scores SHALL use full planned denominators. Wrong answers, mutation, candidate exceptions, timeouts, and excessive output MUST count as candidate failures. Final syntax/contract errors and `no_submission` MUST mark all four hidden checks unsuccessful and unexecuted. A check interrupted by the execution deadline MUST count as attempted and unsuccessful. Reports MUST show counts alongside rates.

Source: issue 03 / Q24.

#### Scenario: Contract violation
- **WHEN** a final submission violates the source contract
- **THEN** the trial fails and its four hidden checks are recorded as unexecuted and unsuccessful within the denominator

#### Scenario: Timeout
- **WHEN** a hidden check exceeds the execution deadline
- **THEN** it is recorded as attempted, unsuccessful, and labelled as a timeout

### Requirement: Incomplete-run classification and headline exclusion
A run SHALL be classified incomplete when containers are unavailable, a worker protocol is broken, API transport retries are exhausted, or the record-level completeness check owned by the `run-evidence` capability (change `add-run-bundles-and-grading-replay`) fails. Partial evidence MUST be preserved, incomplete runs MUST be excluded from headline comparisons, and denominators MUST NOT be reduced. The `run-evidence` check MUST be reused, not reimplemented.

Source: issue 03 / Q24.

#### Scenario: Completeness check fails
- **WHEN** the `run-evidence` completeness check reports a missing scheduled task/trial record
- **THEN** the run is classified incomplete and excluded from headline comparison with planned denominators unchanged

#### Scenario: Infrastructure failure
- **WHEN** a container is unavailable during a trial
- **THEN** the run is marked incomplete rather than the trial being scored as a candidate failure

### Requirement: Deterministic evaluator fixtures
The evaluator SHALL be validated with deterministic fixtures covering correct candidates, ordinary and edge wrong answers, syntax/signature/other contract errors, exceptions, mutation, timeouts, and excessive output, asserting the expected per-check results, labels, and accounting. Human inspection of selected traces SHALL be the qualitative review; an implemented LLM judge MUST NOT be required.

Source: issue 03 / Q22.

#### Scenario: Run evaluator fixtures
- **WHEN** the fixture suite runs without model access
- **THEN** each fixture yields its expected outcome and accounting, and any mismatch fails the suite
