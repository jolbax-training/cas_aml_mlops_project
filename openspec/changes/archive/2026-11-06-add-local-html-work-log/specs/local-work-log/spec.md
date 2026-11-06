# Local Work Log Spec Delta

## Purpose

Provide a locally readable architecture, progress, and reviewed-evidence report from selected authoritative sources, supporting the four-day agent-evaluation/MLOps project without depending on live services.

## ADDED Requirements

### Requirement: Single offline entry point
The work log SHALL be available at `report/index.html`, with all included narrative, navigation, styling, and architecture readable from the local filesystem without a server, network, or JavaScript.

#### Scenario: Read without services
- **WHEN** the built entry point is opened offline with no model API, Podman, GitHub, or MLflow service available
- **THEN** included content and internal navigation work
- **AND** no remote resource is automatically requested

### Requirement: Architecture first with honest status
The first visible main content SHALL be an accessible architecture figure distinguishing implemented and planned components, with readable labels and a text equivalent. Status meaning MUST remain understandable without color.

#### Scenario: Inspect the opening figure
- **WHEN** the entry point is opened at its initial scroll position
- **THEN** the goal figure precedes narrative, status tables, and full navigation
- **AND** its implemented/planned labels reflect the selected documentation

#### Scenario: Read the diagram at different sizes
- **WHEN** viewed at desktop width, 375-pixel width, or 200-percent zoom
- **THEN** labels remain readable through resizing or scrolling
- **AND** an accessible title/description and text explanation convey the architecture

### Requirement: Agent and evidence flows are visible
The architecture SHALL show the bounded agent/development-check loop, external model, final source validation, hidden acceptance execution/scoring, local bundles and grading replay, CI, MLflow, comparison, and Markdown-to-report flow. It MUST expose candidate execution's trust boundary.

#### Scenario: Distinguish development from final grading
- **WHEN** the architecture is inspected
- **THEN** agent-authored checks produce development feedback and explicit final submission leads to separate hidden grading
- **AND** expected answers, scoring, credentials, repository files, tracking, and Podman controls stay outside candidate containers
- **AND** saved final candidates support grading replay without model generation, still using Podman
- **AND** local persistence precedes MLflow recording, and reviewed summaries feed the report

### Requirement: Selected sources and provenance
The generator SHALL include explicitly selected authoritative Markdown and reviewed summaries, preserve substantive content and historical context, and identify sources and generation time. Unselected neighboring files MUST NOT be harvested.

#### Scenario: Regenerate after an approved source edit
- **WHEN** a selected progress or result record changes and the user rebuilds
- **THEN** the report reflects it with source provenance without duplicate prose edits
- **AND** unrelated files remain excluded

### Requirement: Required content and pending evidence
The work log SHALL expose scope/status/milestones, dated decisions, benchmark/review, results/comparison/limitations, local evidence and MLflow references, setup/replay/demo instructions, the transfer guide/example, and selected learning material. Missing evidence MUST be pending; no results, URLs, or personal reflections may be invented.

#### Scenario: Build before experiments or guide delivery
- **WHEN** required evidence or the guide is not yet registered
- **THEN** the corresponding sections are visibly pending
- **AND** existing pilot results remain distinct from planned experiments and illustrative orchestrator examples

#### Scenario: Personal material is unfinished
- **WHEN** selected journal material contains unanswered prompts or historical plans
- **THEN** prompts remain unanswered and supersession context remains visible
- **AND** missing personal reflections do not block report generation

### Requirement: Navigation and local references are validated
The report SHALL provide unique section/heading targets and keyboard-accessible navigation. Included-document links MUST resolve inside the report; approved local source/evidence references MUST be correctly rebased and validated. Missing registered sources and unresolved internal targets MUST fail build/check.

#### Scenario: Follow included and local reference links
- **WHEN** a reader follows an included-document heading or approved local evidence link
- **THEN** it reaches the intended target
- **AND** non-embedded source references are labelled

#### Scenario: Broken registered reference
- **WHEN** a required source or internal target is missing
- **THEN** validation fails with a useful diagnostic and preserves the previous successful output

### Requirement: External evidence remains optional
Recorded CI/MLflow references SHALL retain descriptions or identifiers locally and be labelled as external or local-service references. Generation and viewing MUST NOT automatically fetch them.

#### Scenario: Tracking is stopped
- **WHEN** a recorded MLflow URL cannot be reached
- **THEN** its retained identifier/summary and the report remain readable
- **AND** opening/building the report does not start or query tracking

### Requirement: Explicit inclusion and inert content
The generator SHALL reject secret/private files, machine state, automatic raw-bundle/tracking-store inclusion, escaping paths/symlinks, credential-bearing URLs, and unsafe schemes. Source HTML/code MUST remain inert; external resources MUST NOT load automatically. Only the reviewed local architecture asset is accepted as SVG.

#### Scenario: Unsafe selection or rendered content
- **WHEN** selected paths escape the repository or include forbidden private stores
- **THEN** generation refuses those inputs
- **AND** a selected Python snippet, raw HTML, or remote-image reference is rendered without execution or automatic network access

### Requirement: Repeatable independent build and check
The project SHALL document one build command and a no-output-write check mode. After dependency setup, both MUST run offline without model/container/tracking services, preserve source documents, and leave previous successful output intact after failure. Generated HTML MUST remain ignored by Git.

#### Scenario: Build and validate independently
- **WHEN** valid selected sources are built and checked with services unavailable
- **THEN** build creates the local entry point and check validates without output writes
- **AND** source documents remain unchanged and execution commands do not depend on reporting

### Requirement: Maintain the work log with actual evidence
Editable status/result records SHALL be updated and the report rebuilt after meaningful milestones/runs. Historical decisions and incomplete work MUST retain their labels.

#### Scenario: Record a partial or completed milestone
- **WHEN** new reviewed evidence is registered and rebuilt
- **THEN** the report shows the observed state with provenance
- **AND** incomplete work is not presented as completion
