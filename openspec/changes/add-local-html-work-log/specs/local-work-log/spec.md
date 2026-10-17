# Local Work Log Spec Delta

## Purpose

Provide one locally readable view of the project's intended architecture, authoritative planning documents, dated progress, and reviewed evaluation evidence without requiring live infrastructure or duplicating editable prose.

## ADDED Requirements

### Requirement: Single offline entry point
The work log SHALL be available at `report/index.html`, readable directly from the local filesystem after generation. All included narrative, navigation, styling, and the architecture diagram MUST work without a server, network access, or JavaScript.

#### Scenario: Read while services are unavailable
- **WHEN** the generated entry point is opened with network access disabled and no OpenRouter, Podman, GitHub, or MLflow service available
- **THEN** the diagram and included content render and internal navigation works without opening the source Markdown files
- **AND** no remote resources or services are requested automatically

### Requirement: Architecture is the opening content
The first visible main content SHALL be an architecture/goal figure showing the intended MLOps system. It MUST visually distinguish the laptop milestone, the external generation API, later CI/tracking, and the report, with phase and implementation-status labels that do not rely on color alone.

#### Scenario: Open the work log
- **WHEN** the entry point opens at its initial scroll position
- **THEN** the architecture figure and its goal title precede the status table, narrative documents, and full navigation
- **AND** the figure distinguishes implemented pilot components from planned local and planned later components

### Requirement: Architecture shows components and evidence flows
The architecture SHALL show versioned benchmark/tasks and prompt, the OpenRouter generation agent, contract validation/trusted evaluator, Podman execution, trusted scoring, saved local requests/responses/results and replay, later GitHub Actions deterministic checks, later MLflow tracking, baseline/revised comparison, and the Markdown-to-work-log flow.

#### Scenario: Inspect the execution and evidence boundaries
- **WHEN** the architecture is inspected
- **THEN** labeled flows show task instruction/signature and prompt going to generation, accepted code and case inputs going to Podman, and execution outcomes returning to trusted scoring
- **AND** expected answers feed scoring outside Podman and are not shown entering the generation API or sandbox
- **AND** contract failures are recorded without execution, saved candidates support replay without new generation, and the diagram states that execution replay still uses Podman
- **AND** local results feed comparison and later MLflow, deterministic fixtures feed later GitHub Actions, and reviewed summaries/evidence references feed Markdown and the report
- **AND** credentials and scoring are outside the sandbox trust boundary

### Requirement: Maintainable and accessible architecture
The diagram SHALL be generated from a checked-in editable architecture definition and SHALL have an accessible title, description, and complete text equivalent derived from that same definition. Invalid component or edge references MUST fail validation.

#### Scenario: Evolve the architecture
- **WHEN** an author changes a component label or flow in the architecture definition and regenerates
- **THEN** the visual diagram and text equivalent reflect that change together without separately editing generated HTML

#### Scenario: Invalid graph
- **WHEN** an edge references a nonexistent node or node IDs are duplicated
- **THEN** generation fails with an actionable diagnostic and preserves the previous valid report

#### Scenario: Read at narrow width or with assistive technology
- **WHEN** a user views the report at 375-pixel width, zooms to 200 percent, or reads the figure using a screen reader
- **THEN** labels remain legible through resizing or scrolling and every component/flow is available in the text equivalent

### Requirement: Authoritative sources and provenance
The generator SHALL render explicitly selected Markdown sources without requiring duplicate hand-maintained narrative. It MUST preserve substantive text, dates, tables, code blocks, checklists, and historical context, identify each source, and show generation time and source hashes. Unselected files MUST NOT be harvested automatically.

#### Scenario: Update a progress entry
- **WHEN** an author edits a selected progress Markdown document and rebuilds
- **THEN** the new text appears in its report section with the source identified
- **AND** the author does not need to edit the same prose in a second file

#### Scenario: Register a new reviewed record
- **WHEN** an author explicitly registers a new benchmark-review or experiment-result Markdown record
- **THEN** it becomes readable and navigable from the same entry point on regeneration
- **AND** an unregistered neighboring document remains excluded

### Requirement: Honest status and missing evidence
The work log SHALL expose current status, plans, dated progress/decisions, benchmark context and review, results/comparison, reproduction instructions, selected learning notes, and historical ideas. Missing evidence MUST be visibly pending; historical content and incomplete runs MUST retain their labels. The generator MUST NOT invent results, URLs, or personal reflections.

#### Scenario: Build before any live experiment
- **WHEN** no benchmark-review record, live comparison, CI result, or MLflow run is registered
- **THEN** the corresponding sections show pending evidence rather than success metrics or fabricated links
- **AND** existing pilot evidence remains distinguishable from future experiment results

#### Scenario: Include unfinished journal material
- **WHEN** a selected journal entry contains unanswered reflection prompts or a superseded plan
- **THEN** the prompts remain unanswered and the historical/supersession context remains visible

### Requirement: Navigable content and validated local references
The work log SHALL provide keyboard-accessible section and heading navigation with unique targets. Links among included sources MUST resolve inside the report. Approved local text references MUST be readable as inert appendices. Unresolved local paths/fragments or missing registered sources MUST fail validation; intentionally omitted references MUST be labeled without exposing private destinations.

#### Scenario: Follow links between source documents
- **WHEN** a reader follows a link to an included document or heading, including repeated heading names in different documents
- **THEN** navigation reaches the correct generated section or unique heading target

#### Scenario: Missing source or fragment
- **WHEN** a registered source is missing or an included local link targets a missing heading
- **THEN** build/check exits nonzero with the source and faulty reference identified
- **AND** the previous successful output remains intact

#### Scenario: Approved source-code reference
- **WHEN** an included document links to a specifically approved Python, JSON, or YAML reference
- **THEN** that reference is available as escaped text inside the report and is not executed

### Requirement: External evidence is optional to read
External CI and MLflow evidence references SHALL retain their recorded descriptions or run identifiers locally and be labeled as unchecked external or local-service links. The builder MUST NOT fetch them. Credential-bearing URLs and unsafe URL schemes MUST be rejected.

#### Scenario: MLflow is stopped
- **WHEN** a report contains a recorded loopback MLflow link but the service is stopped
- **THEN** the saved description/run identifier and report remain readable
- **AND** viewing or generating the report does not start the service or attempt automatic access

#### Scenario: Unsafe evidence link
- **WHEN** a selected source includes a credential-bearing URL or executable URL scheme
- **THEN** validation fails without printing credential values

### Requirement: Explicit privacy boundary
Only explicitly approved sources and references SHALL be included. Credential files, private sources, raw run bundles, tracking stores, machine state, and paths escaping the repository MUST be rejected even if accidentally selected. Recognizable credential tokens in selected content MUST cause failure with redacted diagnostics. Future private journal entries MUST require deliberate selection before inclusion.

#### Scenario: Excluded artifact or path escape
- **WHEN** the selection or a local reference resolves to a secret file, raw run bundle, private source, or path/symlink outside the repository
- **THEN** generation refuses that input without reading its contents into the report

#### Scenario: Accidental token in a selected document
- **WHEN** a selected document contains a recognizable API-token or private-key pattern
- **THEN** validation fails with a location-only diagnostic and neither output nor diagnostic contains the token

### Requirement: Rendered content remains inert
Candidate code and embedded raw HTML SHALL be displayed as escaped text, never executed during build or viewing. The report MUST contain no runnable source-provided scripts, active embeds, or automatic external resource loads. The generated architecture is the only accepted SVG source.

#### Scenario: Hostile candidate snippet
- **WHEN** a source contains Python that writes a sentinel file, HTML script/event-handler markup, or a remote image
- **THEN** the Python and HTML are inert text, the image is represented by its alt text, no sentinel file appears, and no network request is made

### Requirement: Repeatable build and check
The project SHALL document `.venv/bin/python scripts/build_work_log.py` for generation and the same command with `--check` for validation without output writes. After dependency setup, both MUST work offline without invoking evaluation or infrastructure. Failed builds MUST preserve previous output. Generated HTML MUST remain ignored by Git.

#### Scenario: Successful regeneration and validation
- **WHEN** the user runs the build and check commands on valid sources
- **THEN** build creates the entry point, check returns success without modifying output, and source Markdown is unchanged
- **AND** repeating the build with unchanged inputs changes only the explicit generation timestamp

#### Scenario: Build/check with no credentials or services
- **WHEN** credentials are absent and all depicted infrastructure is unavailable
- **THEN** build/check still succeed for valid local documentation inputs without invoking model or container commands

### Requirement: Accessible report navigation
The report SHALL use semantic headings, labeled navigation, visible keyboard focus, a skip link, and readable text/table layouts. Phase/status meaning MUST remain understandable without color.

#### Scenario: Keyboard navigation
- **WHEN** the reader uses only the keyboard to skip navigation and follow section links
- **THEN** each intended section is reachable with visible focus and a meaningful heading
