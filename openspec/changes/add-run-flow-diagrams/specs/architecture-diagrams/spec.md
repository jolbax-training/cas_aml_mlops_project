# Spec Delta

## ADDED Requirements

### Requirement: Run-flow activity diagram
A UML activity diagram with swimlanes SHALL show one experiment run from the experiment CLI `run` command to every possible ending, as an editable `docs/run_flow_activity.drawio.svg` with a Markdown text twin. It MUST be drawn only from flows that exist in the code, and the twin MUST trace each node to a function in `src/codegen_eval/`.

#### Scenario: Read the content
- **WHEN** the activity diagram is inspected
- **THEN** it contains the start node, the precondition checks (frozen benchmark, settings and platform, probe evidence, budget), the loop over scheduled trials, the bounded agent loop, the final submission or `no_submission`, hidden grading in a fresh sandbox container, the run bundle, the MLflow recording, and, as separate steps after the run, schedule verification, summary and comparison, human review, and the work-log rebuild

#### Scenario: Read the start and the gates
- **WHEN** the activity diagram is inspected
- **THEN** a single start node is labelled with the experiment CLI `run` command
- **AND** the precondition checks come before any model client is built or bundle is written, and a failed check leads to a refusal final node

#### Scenario: Read the loop and one trial
- **WHEN** the schedule loop and a trial are inspected
- **THEN** the order is: reserve in the ledger, send the model request, receive the response, tool attempt and development check within the limits, final submission or `no_submission`, grading of every case in a fresh container, then the trial record written to the bundle
- **AND** the stop conditions of the agent loop are decision nodes labelled with the limits in `agent_config.py`

#### Scenario: Read the evidence order
- **WHEN** the end of the run is inspected
- **THEN** the bundle is finalized before the MLflow recording is attempted, and an unreachable MLflow service leaves an outage marker without changing the run outcome
- **AND** comparison is drawn reading bundles, not MLflow

### Requirement: Every way a run ends is an explicit final node
The activity diagram SHALL have a separate, labelled final node for each ending the code implements: completed, refused by preconditions, stopped at the budget ceiling, incomplete because of infrastructure outcomes, and aborted by an exception or interrupt. The CHF 10 checkpoint MUST NOT be drawn as an ending. The twin MUST state, per final node, the exit status, the bundle manifest status, and the run marker status the code produces.

#### Scenario: Name the endings
- **WHEN** the final nodes are read
- **THEN** each carries its exit status, bundle manifest status, and run marker status as the code produces them

#### Scenario: Enumerate the endings
- **WHEN** the final nodes are compared with `experiment.run_variant`, `run_recording.run_recorded`, and `experiment_cli.main`
- **THEN** every ending that these functions can produce appears as one final node and no final node is drawn for an ending the code cannot produce

#### Scenario: Checkpoint versus ceiling
- **WHEN** the budget behaviour is inspected
- **THEN** the checkpoint is shown as an action that continues the run and the ceiling as a stop that leaves an incomplete bundle with the unfinished trials unrecorded

### Requirement: One-trial sequence diagram
A UML sequence diagram SHALL show the exact call order of one trial in `docs/run_flow_sequence.drawio.svg` with a Markdown text twin, using the real components of a trial as participants, `loop` and `alt` fragments for the agent loop, the model response outcomes, and the grading of each case, and the trust boundary drawn around the container.

#### Scenario: Read the participants
- **WHEN** the sequence diagram is inspected
- **THEN** it shows the experiment and run recorder, the trial loop, the model client and OpenRouter client, the ledger, OpenRouter, `run_checks`, the sandbox host launcher, the worker in the container, the evaluator, the bundle writer, and the MLflow recorder

#### Scenario: Read the message order
- **WHEN** the sequence diagram is inspected
- **THEN** the ledger reservation precedes each send to OpenRouter, the request is logged to the bundle before it is sent, and grading uses expected answers that exist only on the host side of the boundary
- **AND** only candidate source plus one case's arguments cross into the container and only a bounded result crosses out

#### Scenario: Cross-reference the logical view
- **WHEN** the participant names of the sequence diagram and the box names of the activity diagram are compared with the logical diagram
- **THEN** each participant and lane that corresponds to a logical-diagram box uses that box's module name

### Requirement: Run-flow diagrams keep the established phase, status, and boundary marking
Both run-flow diagrams SHALL mark external and phase-2 elements (OpenRouter, the API key, the live ledger use) with the same dashed outline and literal `PHASE 2` or `EXTERNAL` tag as the physical diagram, SHALL draw the candidate-container trust boundary in the same way, and MUST NOT show results, run identifiers, spend, or URLs that do not exist. Their twins SHALL state that no live run has happened.

#### Scenario: Consistent marking
- **WHEN** the run-flow diagrams are compared with the physical diagram
- **THEN** OpenRouter carries the same `EXTERNAL` and `PHASE 2` tags, and the candidate container is the only trust-boundary region and has no arrow to MLflow, OpenRouter, or the ledger

#### Scenario: No invented evidence
- **WHEN** the diagrams and twins are scanned
- **THEN** no result value, run identifier, spend amount other than the documented CHF 10 checkpoint and CHF 15 ceiling, or URL other than the OpenRouter endpoint appears

### Requirement: Run-flow diagrams appear in the work log and are checked against the source
The work log SHALL show both run-flow diagrams with their twins through the existing `[[diagram]]` registration and the unchanged sanitize-and-rebuild step. Offline tests SHALL check that the labels equal the embedded draw.io XML, that every file and function name written in a diagram or twin exists, and that the stated order, limits, and endings agree with the source.

#### Scenario: Registered and rebuilt
- **WHEN** the work log is built offline
- **THEN** both run-flow diagrams appear after the existing diagrams as accessible figures with their twins, and the output validation still passes

#### Scenario: Drift is detected
- **WHEN** a diagram or twin names a function that does not exist, drops a stated ending, or states an order or limit that the source contradicts
- **THEN** the offline tests fail naming the file and claim

#### Scenario: Accepted diagrams untouched
- **WHEN** this change is complete
- **THEN** the bytes of the physical and logical diagrams and their twins are unchanged and the sanitizer still rejects every input it rejected before
