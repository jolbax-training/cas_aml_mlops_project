# run-evidence Specification

## Purpose
Retain complete local evidence for every evaluation run and support inspection and grading replay without new model generation.

## Requirements

### Requirement: Durable local bundle before tracking
The system SHALL persist a local run bundle containing rendered requests, raw responses, tool interactions, candidate history, final source, configuration and version hashes, usage, and grading results before any tracking upload. Records MUST be written incrementally so partial evidence survives interruption. Source: issue 05 / Q35.

#### Scenario: Interrupted run
- **WHEN** a run stops partway through its planned trials
- **THEN** records for already-completed trials remain on disk
- **AND** the run is marked incomplete

### Requirement: Versioned run identity
Each bundle SHALL record run and trial IDs, timestamps, completion status, planned task/trial IDs, and identities of the prompt version, benchmark and review content, execution limits, evaluator revision, Python/dependency versions, container image digest, and model/provider settings when available. Source: spec Evidence, MLflow, CI, and replay; issue 05 / Q35.

#### Scenario: Inspect run configuration
- **WHEN** a bundle's manifest is read
- **THEN** it identifies the configuration and versions under which its trials ran

### Requirement: Secrets excluded
Bundles MUST NOT contain credentials, authorization headers, or secret environment data, and bundle storage MUST be excluded from version control. Source: spec Evidence, MLflow, CI, and replay; issue 05 / Q35.

#### Scenario: API key present during run
- **WHEN** a run executes with an API key in the environment
- **THEN** the key appears nowhere in the bundle
- **AND** `git status` does not list bundle files

### Requirement: Service-free trace inspection
The project SHALL provide trace inspection of retained requests, responses, tool interactions, and outcomes without a model API, Podman, or tracking service. Inspection MUST NOT execute candidates. Source: issue 05 / Q35.

#### Scenario: Inspect offline
- **WHEN** Podman and network are unavailable
- **THEN** inspection shows a trial's messages, tool feedback, final source, and grades

### Requirement: Grading replay of saved final candidates
The project SHALL provide grading replay that executes saved final candidates against the retained benchmark with Podman and no model API calls or credentials. Replay results MUST be stored separately from and linked to the original grading evidence, and MUST NOT be described as a fresh model interaction or agent-trial reproduction. Source: issue 05 / Q35; Glossary grading replay.

#### Scenario: Regrade a run
- **WHEN** grading replay runs on a retained bundle without an API key
- **THEN** new grading evidence is written alongside the original without overwriting it
- **AND** no model request is made

#### Scenario: Benchmark mismatch
- **WHEN** the retained benchmark content does not match the hash recorded in the bundle
- **THEN** replay fails with a diagnostic rather than grading against different checks

### Requirement: Completeness verification
The system SHALL verify that every planned task/trial ID has a record and that executed checks have valid outcomes, rather than relying on aggregate counts. Runs failing this check MUST be marked incomplete with partial evidence preserved and planned denominators unchanged. This capability is the single owner of the record-level check; outcome classification and headline exclusion rules belong to `benchmark-and-grading` (change `add-reviewed-benchmark-and-graders`). Source: issue 03 / Q24.

#### Scenario: Missing trial record
- **WHEN** one planned trial has no record
- **THEN** the run is reported incomplete and identifies the missing trial
