# continuous-integration Specification

## Purpose
Provide automated deterministic evidence that the evaluator, benchmark, agent loop, and Podman execution boundary behave as specified, without model credentials or paid generation.

## Requirements

### Requirement: Two required deterministic check groups
The project SHALL run two required GitHub Actions check groups: evaluator/benchmark/agent-loop tests, and real Podman execution/isolation tests.

Source: issue 05 / Q36.

#### Scenario: Change pushed
- **WHEN** a change is pushed or proposed against the main branch
- **THEN** both check groups run and report status independently

### Requirement: Real Podman checks on a compatible Linux runner
The Podman group SHALL execute candidate checks in real restricted Podman containers on a compatible Linux runner using the pinned candidate image. Podman-dependent tests MUST NOT pass by being skipped in CI.

Source: issue 05 / Q36; issue 02 Answer.

#### Scenario: Podman unavailable on the runner
- **WHEN** Podman or the pinned image cannot be used in the CI job
- **THEN** the Podman check group fails with a diagnostic rather than skipping

#### Scenario: Isolation probes run
- **WHEN** the Podman group runs
- **THEN** host-file, environment, network, filesystem, timeout, excessive-output, forged-response, and concealed-mutation probes execute against the configured limits

### Requirement: Pinned and documented environment
CI SHALL install locked dependencies and use pinned Python and container image versions, and the tested versions MUST be documented.

Source: issue 05 / Q36, Answer bullet 8.

#### Scenario: Inspect CI provenance
- **WHEN** a reader checks the documentation for a CI run
- **THEN** the runner, Python, dependency lock, Podman, and image digest versions used are identifiable

### Requirement: No model credentials or paid generation
CI MUST NOT require model credentials or perform paid generation. Interaction behavior SHALL be verified with deterministic recorded-response fixtures.

Source: issue 05 / Q36.

#### Scenario: Run without secrets
- **WHEN** the workflow runs with no model API key configured
- **THEN** all checks complete using fixtures and no model request is sent

### Requirement: Fixture-based verification without pass-rate gates
CI SHALL verify failure classification, execution limits, scoring, and accounting with fixtures of known candidates. Candidate or model success rates MUST NOT be used as CI thresholds.

Source: issue 05 / Q36; issue 03 / Q22.

#### Scenario: Broken grading behavior
- **WHEN** a fixture expectation for a wrong-answer, mutation, or timeout candidate no longer matches the evaluator's classification
- **THEN** the corresponding check group fails

### Requirement: Retained CI evidence
Successful and failing CI runs relied upon as completion evidence SHALL be recorded in progress with identifiers and dates. CI results MUST NOT be claimed before such runs exist.

Source: docs/project_spec.md "Evidence, MLflow, CI, and replay"; completion checklist.

#### Scenario: Record CI completion
- **WHEN** both groups pass on GitHub Actions
- **THEN** progress records the run identifiers, commit, and versions
