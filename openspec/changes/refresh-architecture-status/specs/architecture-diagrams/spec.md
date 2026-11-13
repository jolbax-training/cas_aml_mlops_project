## MODIFIED Requirements

### Requirement: Honest status
Each diagram and its text twin SHALL label every component as implemented, partial (built and tested offline with no live or real run), pending (the evidence does not exist), or, for a system outside the repository, external, using a text label as well as styling. A component whose status depends on a run and that has a documented live run MUST NOT be labelled partial or pending, and such a component without one MUST NOT be labelled implemented. Components that involve no live run (sandbox, grading, CI, the work-log builder) keep the implemented label while their code and tests exist. The diagrams MUST NOT show results, run identifiers, or spend that do not exist, and MUST NOT state a numeric result value, URL, or run identifier of their own; those are cited from the evidence files.

#### Scenario: No live run has happened
- **WHEN** a component has no committed live evidence, for example before a live comparison run or for a part no run has covered
- **THEN** its use is not shown as completed and it is labelled partial or pending
- **AND** no result value, URL, or run identifier appears

#### Scenario: Live evidence exists
- **WHEN** a component has documented live evidence (a paid smoke, a recorded comparison run, an MLflow record of a live run, or a reviewed summary)
- **THEN** its label does not say that no live run has happened
- **AND** the evidence file that supports the label is named in the status-sources file

#### Scenario: Something is still open
- **WHEN** a part has no committed evidence, for example the student's own interpretation
- **THEN** it is stated as open in the twin and is not shown as done
- **AND** no result value, URL, or run identifier appears in the diagram

#### Scenario: History stays history
- **WHEN** a dated progress entry or archived change says no live run had happened
- **THEN** it is left unchanged
- **AND** only current-status figures, twins and status sections are brought up to date

### Requirement: Run-flow diagrams keep the established phase, status, and boundary marking
Both run-flow diagrams SHALL mark OpenRouter and the paid smoke trial with the dashed outline and literal `EXTERNAL` or `PHASE 2` tag of the physical diagram, SHALL draw the candidate-container trust boundary in the same way, and MUST NOT show results, run identifiers, spend, or URLs that do not exist. Status SHALL be carried by lane and lifeline headers, not by action or message nodes, and the twins SHALL state the run status that the status-sources file records (for example that the baseline and revised comparison runs completed) while showing no result value, run identifier, spend amount or URL beyond the ones listed in the evidence files.

#### Scenario: Consistent marking
- **WHEN** the run-flow diagrams are compared with the physical diagram
- **THEN** OpenRouter carries the same `EXTERNAL` and `PHASE 2` tags and the dashed outline, and the candidate container is the only trust-boundary region and has no arrow to MLflow, OpenRouter, or the ledger

#### Scenario: Status on headers
- **WHEN** every swimlane and lifeline header is read
- **THEN** it carries one of the status labels or the external tag

#### Scenario: No invented evidence
- **WHEN** the diagrams and twins are scanned
- **THEN** no result value, run identifier, spend amount other than the documented CHF 10 checkpoint and CHF 15 ceiling, or URL other than the OpenRouter endpoint appears

### Requirement: Run-flow diagrams appear in the work log and are checked against the source
The work log SHALL show both run-flow diagrams with their twins through the existing `[[diagram]]` registration and the unchanged sanitize-and-rebuild step. Offline tests SHALL check that the labels equal the embedded draw.io XML, that every file and function name exists, and that the stated order, limits, and endings agree with the source.

#### Scenario: Registered and rebuilt
- **WHEN** the work log is built offline
- **THEN** both run-flow diagrams appear after the existing diagrams as accessible figures with their twins, and the output validation still passes

#### Scenario: Drift is detected
- **WHEN** a diagram or twin names a function that does not exist, drops a stated ending, or states an order or limit that the source contradicts
- **THEN** the offline tests fail naming the file and claim

#### Scenario: Accepted diagrams untouched
- **WHEN** the physical and logical diagrams and their twins are edited
- **THEN** the sanitizer still rejects every input it rejected before, and the edits only change statuses, the sentences that carried them, and the as-of line

## ADDED Requirements

### Requirement: Status claims are checked against cited evidence offline
The repository SHALL contain a machine-readable status-sources file that gives, for each component whose status depends on a run, the status, a committed evidence file, and a phrase that must occur in it. An offline test SHALL compare every current-status figure, twin, and status section with that file.

#### Scenario: Status differs from the sources file
- **WHEN** a diagram or twin status differs from the sources file, or a twin lacks the sentence the file records for the completed runs
- **THEN** the test fails naming the file and the component

#### Scenario: Stale label reintroduced
- **WHEN** a current-status file contains a phrase from a fixed, case-insensitive stale list (for example `NO LIVE RUN YET`, "no live call has been made", or a `PENDING` label for a component the sources file marks done)
- **THEN** the test fails naming the file and the phrase

#### Scenario: Status without evidence
- **WHEN** a sources entry cites a missing file or a missing phrase
- **THEN** the test fails naming the component

#### Scenario: Drawing and model diverge
- **WHEN** the embedded draw.io model and the rendered text of a `.drawio.svg` differ
- **THEN** the test fails naming the file

#### Scenario: Offline run
- **WHEN** the test runs in CI
- **THEN** it reads only checked-in files and needs no network, Podman, MLflow, draw.io, or retained bundles
