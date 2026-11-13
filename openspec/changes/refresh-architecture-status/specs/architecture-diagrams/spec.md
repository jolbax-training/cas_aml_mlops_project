## MODIFIED Requirements

### Requirement: Honest status
Each diagram and its text twin SHALL label every component as implemented, partial (built and tested offline with no live or real run), pending (the evidence does not exist), or, for a system outside the repository, external, using a text label as well as styling. A status MUST match the committed evidence at the time the diagram is dated: a component with a documented live run is not labelled partial or pending, and a component without one is not labelled implemented. The diagrams MUST NOT show results, run identifiers, or spend that do not exist, and MUST NOT state a numeric result value, URL, or run identifier of their own; those are cited from the evidence files.

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
- **AND** only current-status figures and twins are brought up to date

## ADDED Requirements

### Requirement: Status claims are checked against cited evidence offline
The repository SHALL contain a machine-readable status-sources file that gives, for each component whose status depends on a run, the status, a committed evidence file, and a phrase that must occur in it. An offline test SHALL fail when a diagram or twin status differs from the file, when an evidence file or phrase is missing, when a stale-status phrase from a fixed list occurs in a current-status figure or twin, or when the embedded draw.io model and the rendered text of a `.drawio.svg` differ.

#### Scenario: Stale label reintroduced
- **WHEN** a current-status figure or twin contains `NO LIVE RUN YET`, a `PENDING` label for a component the sources file marks done, or a sentence such as "no live call has been made"
- **THEN** the test fails naming the file and the phrase

#### Scenario: Status without evidence
- **WHEN** a component is labelled implemented or external-and-used and its sources entry cites a missing file or a missing phrase
- **THEN** the test fails naming the component

#### Scenario: Offline run
- **WHEN** the test runs in CI
- **THEN** it reads only checked-in files and needs no network, Podman, MLflow, draw.io, or retained bundles
