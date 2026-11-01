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
