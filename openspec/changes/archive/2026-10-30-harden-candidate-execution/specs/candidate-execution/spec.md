# Candidate Execution Spec Delta

## Purpose

Execute untrusted candidate functions one check at a time in fresh restricted Podman containers, returning trustworthy raw outcomes to trusted scoring under fixed, configurable limits.

## ADDED Requirements

### Requirement: Shared per-check execution mechanism
The system SHALL execute agent-authored development checks and hidden acceptance checks through the same restricted mechanism, starting a fresh disposable Podman container for every individual check and not intentionally reusing filesystem or process state between checks. Source: issue 02 / Q19.

#### Scenario: Two checks for one candidate
- **WHEN** a candidate is executed against two checks
- **THEN** each check runs in its own newly created container
- **AND** state written during the first check is not visible to the second

### Requirement: Minimal candidate inputs
Candidate execution SHALL receive only the candidate source, the function name, and the current check's arguments. Expected answers, comparison logic, and scoring MUST remain in trusted orchestration. Source: issue 02 / Q19.

#### Scenario: Inspect container inputs
- **WHEN** a hidden acceptance check is executed
- **THEN** the container payload contains no expected value, label, or score
- **AND** pass/fail is decided outside the container

### Requirement: Restricted container environment
Candidate containers MUST have no repository mounts, credentials, API keys, tracking access, Podman control socket, or network access, and SHALL run with a read-only root filesystem, an unprivileged user, dropped capabilities, and restricted temporary writes. Source: issue 02 / Q19; spec Execution and scoring integrity.

#### Scenario: Hostile candidate probes the environment
- **WHEN** a probe candidate tries to read host files, read host environment secrets, open a network connection, or write outside temporary storage
- **THEN** the attempt fails inside the container
- **AND** no host file, secret, or service is exposed in its outcome

### Requirement: Configurable fixed execution limits
The system SHALL enforce configurable limits defaulting to a 10-second wall-time deadline per check including container startup and code loading, 128 MiB memory, 1 CPU, 32 processes, 16 MiB writable temporary storage, 64 KiB source-and-arguments payload, 32 KiB captured print output, and 64 KiB worker-protocol output. Cleanup MUST be handled outside the deadline. Limits MUST be recorded and held fixed across compared variants. Source: issue 02 / Q20.

#### Scenario: Candidate exceeds the deadline
- **WHEN** a candidate runs longer than 10 seconds including startup
- **THEN** the check is stopped and classified as a timeout
- **AND** container cleanup completes separately

#### Scenario: Oversized payload
- **WHEN** source plus arguments exceed 64 KiB
- **THEN** no container is started for that check
- **AND** the outcome reports the payload limit

#### Scenario: Excessive print output
- **WHEN** a candidate prints more than 32 KiB
- **THEN** the outcome is classified as excessive output without unbounded capture

### Requirement: Trustworthy worker reporting
The trusted side MUST NOT accept a candidate-forged worker response as a genuine result, and MUST detect input mutation that remains in the post-call arguments even when candidate code attempts to conceal it. Mutation is judged on net post-call state. The limitation that a candidate introspecting its own executor can still sign a report MUST stay documented. Host isolation passing MUST NOT be treated as evidence of scoring integrity. Source: issue 02 / Q18.

#### Scenario: Forged worker response
- **WHEN** a probe candidate writes a fabricated success message in the worker protocol format
- **THEN** the trusted side does not record it as a passing result

#### Scenario: Concealed mutation
- **WHEN** a probe candidate mutates its inputs and tries to hide a change that remains in the post-call arguments (for example by patching serialisation or returning a lying value)
- **THEN** the outcome records mutation

#### Scenario: Introspection-forged report
- **WHEN** a probe candidate introspects its executor and signs a report itself
- **THEN** the report can yield only outcomes reachable honestly, since expected answers never enter the container and mutation is judged on net state
- **AND** the limitation is recorded in the threat model

#### Scenario: Mutation fully undone before returning
- **WHEN** a probe candidate mutates its inputs and restores them exactly before returning
- **THEN** the outcome does not record mutation, because the post-call arguments equal the originals

### Requirement: Infrastructure outcomes are distinct
The system SHALL classify container unavailability and malformed or missing output from the trusted supervisor (the container's PID 1) as infrastructure outcomes, distinct from candidate failures such as exceptions, timeouts, excessive output, and mutation. Because the candidate shares the executor process with the reporter, executor report and exit failures are candidate outcomes. Source: issue 02 / Q19; issue 01 / Q16–Q17.

#### Scenario: Podman unavailable
- **WHEN** a container cannot be started
- **THEN** the outcome is an infrastructure failure rather than a candidate failure

#### Scenario: Trivial correct candidate
- **WHEN** a trivial correct candidate is executed in an environment
- **THEN** the outcome is a returned result, guarding the executor itself

#### Scenario: Missing or forged executor report
- **WHEN** the executor report is missing, malformed, forged, or oversized, or the executor exits non-zero
- **THEN** the outcome is a candidate outcome

#### Scenario: Candidate disrupts the supervisor
- **WHEN** a probe candidate signals PID 1, returns a deeply nested value, or forges a report holding NaN, overflowing, or expanding numbers
- **THEN** the outcome is a candidate outcome and never an infrastructure outcome

### Requirement: Mandatory probes and threat model before live comparison
The project SHALL provide probes for host files, host environment, network, read-only paths, timeout, excessive output, input mutation, forged worker responses, and concealed mutation, run them in every execution environment actually used, and document the threat model and residual limitations. A demonstrated scoring bypass MUST be resolved before live comparison results are trusted. Source: issue 02 / Q18, Q20.

#### Scenario: Probe suite before baseline
- **WHEN** the baseline comparison run is about to start in an environment
- **THEN** the full probe suite has passed in that environment with recorded evidence
- **AND** the threat model lists protections and residual limitations

#### Scenario: Bypass discovered
- **WHEN** a probe demonstrates a scoring bypass
- **THEN** live comparison results are not treated as trustworthy until the bypass is fixed and probes pass
