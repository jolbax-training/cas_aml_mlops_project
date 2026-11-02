# architecture-diagrams Specification

## Purpose
Provide a physical (deployment) and a logical (components and data flow) architecture diagram that match the implemented code, state phase and status honestly, and stay editable, accessible, and safe to show in the offline work log.

## Requirements

### Requirement: Physical view of both phases
The physical diagram SHALL show the phase-1 local system and, marked as phase 2, the external subsystems used once live model calls begin. Each element MUST be labelled with where it runs.

#### Scenario: Read the local phase
- **WHEN** the physical diagram is inspected
- **THEN** it shows the laptop host with the uv/Python CLI, Podman running one disposable candidate container per check, the MLflow Podman service with durable storage reachable on `127.0.0.1` only, run bundles and the spending ledger on disk, and the generated HTML work log

#### Scenario: Read the external subsystems
- **WHEN** the phase-2 elements are inspected
- **THEN** OpenRouter (API key, budget ledger), GitHub with GitHub Actions (offline and podman jobs), and the image registries for the pinned images are visibly marked as phase 2 or external
- **AND** the marking does not depend on colour alone

### Requirement: Trust boundaries are explicit
Both views SHALL expose the candidate-execution boundary: candidate containers have no network, no credentials, no repository files, and no access to MLflow, the model API, or Podman controls. Expected answers and scoring MUST be shown on the trusted host side.

#### Scenario: Locate the secrets and the boundary
- **WHEN** a reader looks for where the API key, hidden expected answers, and scoring live
- **THEN** they sit in the trusted host process outside every candidate container
- **AND** the only data crossing into a container is candidate source plus one case's arguments, and only a bounded result crosses out

### Requirement: Logical view matches the modules
The logical diagram SHALL label components with real module names under `src/codegen_eval/` (and scripts where relevant) and draw only data flows that exist in the code. Comparison MUST be shown reading run bundles, not MLflow.

#### Scenario: Names resolve to files
- **WHEN** every module or script name written in either diagram or text twin is checked
- **THEN** each names an existing file in the repository

#### Scenario: Evidence flow direction
- **WHEN** the evidence flow is inspected
- **THEN** run bundles are written before MLflow recording, MLflow is a secondary record that is never read back, and comparison and summaries read the bundles
- **AND** grading replay re-runs hidden grading from saved candidates without model generation

### Requirement: Honest status
Each diagram SHALL label every component as implemented, partial (built and tested offline with no live or real run), or pending, using a text label as well as styling, and MUST NOT show results, run identifiers, or spend that do not exist.

#### Scenario: No live run has happened
- **WHEN** the diagrams are inspected before any live comparison run
- **THEN** OpenRouter use, MLflow recording of real runs, and comparison are not shown as completed
- **AND** no result value, URL, or run identifier appears

### Requirement: Editable draw.io SVG with a text twin
Each diagram SHALL be a checked-in `*.drawio.svg` file that renders as an image and carries its editable draw.io XML, and SHALL have a Markdown text twin conveying the same components, flows, boundaries, and statuses.

#### Scenario: Edit and render
- **WHEN** a `.drawio.svg` file is opened in draw.io or a browser
- **THEN** draw.io shows the editable diagram and the browser renders the image
- **AND** the embedded XML decodes to a diagram whose text matches the rendered labels

#### Scenario: Read without seeing the image
- **WHEN** only the Markdown twin is read
- **THEN** it states every component, arrow, boundary, phase marking, and status of the diagram in text

### Requirement: Diagrams appear in the offline work log without weakening its checks
The work log SHALL show both diagrams, each with its text twin, through registered sources. The existing validation of the work-log figure MUST remain unchanged, and a draw.io SVG MUST be embedded only after being rebuilt from an allowlist of elements and attributes that excludes scripts, event handlers, external references, `foreignObject`, embedded images, and the editable XML payload.

#### Scenario: Build with the diagrams registered
- **WHEN** the work log is built offline
- **THEN** both diagrams appear as accessible figures with their text twins and no network resource is requested
- **AND** the output validation still passes

#### Scenario: Unsafe draw.io content
- **WHEN** a registered diagram contains a script, event handler, external or data reference, `foreignObject`, or an element outside the allowlist
- **THEN** the build fails with a diagnostic naming the file and construct
- **AND** the previous successful output is preserved

#### Scenario: Existing figure unchanged
- **WHEN** the work-log figure is validated
- **THEN** the original element and attribute rules still apply and still reject the same unsafe inputs

### Requirement: Experiment-lifecycle activity diagram
A UML activity diagram with swimlanes SHALL show the whole experiment from its start node to its final node as an editable `docs/run_flow_activity.drawio.svg` with a Markdown text twin, with the experiment `run` command drawn as one sub-activity expanded in the same diagram. It MUST be drawn only from flows and commands that exist in the code, and the twin MUST trace each node to a function or command.

#### Scenario: Read the lifecycle
- **WHEN** the top-level flow is inspected
- **THEN** it passes through setup commands (benchmark freeze, `build-config`, `record-probes`, the smoke trial, `calibrate`, `freeze-settings`, `check`), the `run` for the baseline variant, human inspection of the baseline failures, the revised prompt and `build-config`, the `run` for the revised variant, `compare`, human review, and the work-log rebuild
- **AND** both `run` actions refer to the single expanded sub-activity and one start node and one `experiment complete` final node bound the lifecycle

#### Scenario: Read the gates and the loop in the run
- **WHEN** the run sub-activity is inspected
- **THEN** the precondition checks (frozen benchmark, settings and platform, probe evidence, budget, and the others `check_preconditions` makes) come before the run marker is written and before any model client is built, and a failed check leads to a refusal final node
- **AND** the schedule loop covers each planned task and trial in the configured order

#### Scenario: Read one trial
- **WHEN** the agent loop and grading in the run sub-activity are inspected
- **THEN** the order is: build the request, log it, reserve in the ledger, send, settle or keep, log the response, then one of five outcomes (request rejected, infrastructure failure, tool request while tools are disabled, tool request with development checks within the limits, final submission or no final message)
- **AND** a final submission is graded case by case in fresh containers and the trial record is written to the bundle

#### Scenario: Read the evidence order
- **WHEN** the end of the run sub-activity is inspected
- **THEN** the bundle is finalized, the schedule verified, the MLflow recording attempted, and the run marker finalized, in that order, and an unreachable MLflow service leaves an outage marker without changing the run outcome
- **AND** `compare`, human review, and the work-log rebuild are drawn as separate commands outside the run, and comparison reads bundles, not MLflow

### Requirement: Every way a run or lifecycle command ends is an explicit final node
The activity diagram SHALL have a separate, labelled final node for each ending the code implements, and a completed run SHALL be the exit edge of the sub-activity, not a final node. The CHF 10 checkpoint MUST NOT be drawn as an ending. The twin MUST state, per ending, the exit status, the bundle manifest status, and the run marker status the code produces.

#### Scenario: List the final nodes
- **WHEN** the final nodes are counted
- **THEN** the run sub-activity has refused, stopped at the budget ceiling, incomplete after infrastructure outcomes, and aborted by an exception or interrupt, and the lifecycle has `check` with unmet preconditions, `compare` without a headline comparison, and experiment complete

#### Scenario: Name the endings
- **WHEN** the final nodes are read
- **THEN** each carries its exit status, bundle manifest status, and run marker status as the code produces them, including the three observable variants of an abort

#### Scenario: Enumerate the endings
- **WHEN** the final nodes are compared with `experiment_cli.main`, `experiment.run_variant`, and `run_recording.run_recorded`
- **THEN** every ending these functions can produce appears as one final node and no final node is drawn for an ending the code cannot produce

#### Scenario: Checkpoint versus ceiling
- **WHEN** the budget behaviour is inspected
- **THEN** the checkpoint is shown as a ledger action that continues the run and the ceiling as a stop that leaves an incomplete bundle with the unfinished trials unrecorded

### Requirement: One-trial sequence diagram
A UML sequence diagram SHALL show the exact call order of one trial in `docs/run_flow_sequence.drawio.svg` with a Markdown text twin, using the real components of a trial as participants, `loop` and `alt` fragments for the agent loop, the five response outcomes, and the grading of each case, and the trust boundary drawn around the container.

#### Scenario: Read the participants
- **WHEN** the sequence diagram is inspected
- **THEN** it shows the experiment and run recorder, the trial loop, the model client and OpenRouter client, the ledger, OpenRouter, `run_checks`, the sandbox host launcher, the worker in the container, the evaluator, the bundle writer, and the MLflow recorder

#### Scenario: Read the message order
- **WHEN** the sequence diagram is inspected
- **THEN** the request is logged to the bundle and the ledger reservation made before each send to OpenRouter, and grading compares results with expected answers that exist only on the host side of the boundary
- **AND** only candidate source plus one case's arguments cross into the container and only a bounded result crosses out

#### Scenario: Cross-reference the logical view
- **WHEN** the participant and lane names are compared with the logical diagram
- **THEN** each participant and lane that corresponds to a logical-diagram box uses that box's module name

### Requirement: Run-flow diagrams keep the established phase, status, and boundary marking
Both run-flow diagrams SHALL mark OpenRouter and the paid smoke trial with the dashed outline and literal `EXTERNAL` or `PHASE 2` tag of the physical diagram, SHALL draw the candidate-container trust boundary in the same way, and MUST NOT show results, run identifiers, spend, or URLs that do not exist. Status SHALL be carried by lane and lifeline headers, not by action or message nodes, and the twins SHALL state that no live run has happened.

#### Scenario: Consistent marking
- **WHEN** the run-flow diagrams are compared with the physical diagram
- **THEN** OpenRouter carries the same `EXTERNAL` and `PHASE 2` tags, and the candidate container is the only trust-boundary region and has no arrow to MLflow, OpenRouter, or the ledger

#### Scenario: Status on headers
- **WHEN** every swimlane and lifeline header is read
- **THEN** it carries one of the three status labels or the external tag

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
- **WHEN** this change is complete
- **THEN** the bytes of the physical and logical diagrams and their twins are unchanged and the sanitizer still rejects every input it rejected before
