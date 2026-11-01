# orchestration-helpers Specification

## Purpose
Provide generic, offline-checkable helper scripts for waiting on Orca worker messages and watching GitHub CI runs.

## Requirements

### Requirement: Scripts live in the repository and are parameterized
The helper scripts SHALL live under `scripts/orchestration/` and MUST NOT contain hard-coded scratchpad paths, run IDs, dispatch IDs, terminal handles, or a fixed repository name. The repository for CI polling SHALL come from an explicit option or environment variable, defaulting to the `origin` remote.

#### Scenario: Run from a different clone
- **WHEN** the CI watcher runs in a clone whose `origin` is another repository
- **THEN** it queries that repository without editing the script

### Requirement: Worker wait scripts
A single-batch wait script SHALL block until a `worker_done`, `escalation`, or `question` message arrives or a timeout elapses and print a readable summary including the delivery id. A loop script SHALL repeat it, acking batches that contain no actionable message, and SHALL return when an actionable message arrives while leaving that delivery for the caller to ack explicitly.

#### Scenario: Heartbeat-only batch
- **WHEN** a batch contains no actionable message
- **THEN** the loop acks it and waits again, up to a bounded number of rounds

#### Scenario: Actionable delivery
- **WHEN** a batch contains a `worker_done`, question, or escalation
- **THEN** the script prints it with its delivery id and stops without silently acking it

#### Scenario: Error or non-JSON response
- **WHEN** the Orca call fails, prints extra diagnostic lines, or returns a body that is not the expected JSON
- **THEN** the script prints the response and exits non-zero instead of printing a misleading summary

#### Scenario: Loop exhausted
- **WHEN** the bounded rounds pass with no actionable message
- **THEN** the script says so and exits non-zero

### Requirement: CI watcher
The CI watcher SHALL poll a GitHub Actions run through the unauthenticated API at a configurable, gentle interval until it completes, then print the run result and URL, each job's conclusion and non-successful steps, and check-run annotations (omitting known runtime-deprecation noise), and SHALL exit non-zero when the run did not succeed.

#### Scenario: Run failed
- **WHEN** the run concludes with failure
- **THEN** the watcher prints the failing steps and annotations and exits non-zero

#### Scenario: API returns an error or rate limit
- **WHEN** the API response is a rate-limit or error body
- **THEN** the watcher reports that clearly instead of printing misleading results

### Requirement: Offline checks
Each script SHALL support a dry-run or help path, and the repository SHALL include tests that run the scripts against stub `orca` and `curl` programs with canned output, without network access, Orca, Podman, or credentials.

#### Scenario: Test suite runs offline
- **WHEN** the unit test group runs on a machine without Orca or network
- **THEN** the script tests pass using only stubs
