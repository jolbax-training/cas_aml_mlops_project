# Experiment Tracking Spec Delta

## Purpose

Record retained local evaluation runs, agent traces, and grading evidence in a containerized local MLflow service without making tracking a prerequisite for execution or a reason to regenerate paid responses.

## ADDED Requirements

### Requirement: Persistent local tracking service
The project SHALL run MLflow as a persistent local Podman service with durable storage outside ephemeral containers and a localhost tracking endpoint. Candidate containers MUST NOT receive tracking access, endpoints, or credentials.

Source: issue 05 / Q34.

#### Scenario: Service restart preserves data
- **WHEN** a run has been recorded and the MLflow container is stopped and started again
- **THEN** the recorded run, its artifacts, and traces remain available

#### Scenario: Candidates cannot reach tracking
- **WHEN** a candidate check executes in its disposable container
- **THEN** it has no network route, credentials, or configuration for the tracking service

### Requirement: Record runs from retained bundles
Recording SHALL read a retained local run bundle and record its parameters, metrics, artifacts, and agent/model/tool traces, tagged with the bundle identity, benchmark version, prompt version, evaluator revision, and completion status. Recording MUST NOT trigger model generation.

Source: issue 05 / Q35, Answer bullets 2 and 4.

#### Scenario: Record a complete bundle
- **WHEN** a complete retained bundle is recorded
- **THEN** the MLflow run contains the configured settings as parameters, the primary and diagnostic measures as metrics, bundle artifacts, and one trace per trial
- **AND** the run is linked to the bundle identity

#### Scenario: Record an incomplete bundle
- **WHEN** a bundle marked incomplete is recorded
- **THEN** its incomplete status is visible in tracking
- **AND** it is not presented as a headline comparison run

### Requirement: Trial traces reflect the agent interaction
Each trial trace SHALL include logical model calls, physical attempts and transport retries, `run_checks` calls with their bounded feedback, final submission or `no_submission`, and retained usage/latency. Hidden acceptance inputs and expected answers MUST NOT appear in the agent interaction trace.

Source: issue 05 Answer bullet 4; issue 01 Answer.

#### Scenario: Inspect a trial trace
- **WHEN** a recorded trial trace is opened in MLflow
- **THEN** its model calls, tool calls, feedback, and final outcome appear in order
- **AND** hidden grading evidence is linked separately rather than embedded in the interaction

### Requirement: Original trace distinct from grading replay
Grading-replay evidence SHALL be recorded separately from the original agent trace and linked to the original bundle identity. Replay records MUST NOT overwrite or be labelled as a new agent trial.

Source: issue 05 Answer bullets 3 and 4.

#### Scenario: Record a grading replay
- **WHEN** a grading replay of saved final candidates is recorded
- **THEN** it appears as distinct grading evidence linked to the original run
- **AND** the original trace and grades remain unchanged

### Requirement: Tracking outage preserves evidence
Execution SHALL complete and retain its bundle when MLflow is unavailable. The same bundle MUST be recordable later, and paid responses MUST NOT be regenerated to recover tracking.

Source: issue 05 / Q35.

#### Scenario: Upload after an outage
- **WHEN** a run completes while the tracking service is stopped
- **THEN** the bundle is retained and marked not yet recorded
- **AND** a later recording of the same bundle succeeds without new model calls

### Requirement: No secrets in tracking
Recorded parameters, artifacts, and traces MUST exclude credentials, authorization headers, and secret environment data.

Source: docs/project_spec.md "Evidence, MLflow, CI, and replay".

#### Scenario: Scan recorded content
- **WHEN** a fixture bundle is recorded with a configured API key present in the environment
- **THEN** no recorded parameter, tag, artifact, or trace contains that key
