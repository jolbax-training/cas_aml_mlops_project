## ADDED Requirements

### Requirement: Evidence summary derived from recorded sources
The project SHALL provide one committed machine-readable evidence summary for the presentation and the report. Every number in it MUST be derived by code from retained bundles (through the existing comparison and trace-inspection code) or from a committed document, never typed by hand.

Source: accepted user decisions; docs/project_spec.md (evidence, report sections).

#### Scenario: A figure traces back to its source
- **WHEN** a reader looks up any value used in a chart
- **THEN** the summary names the command or document, the run IDs, and the bundle digests that produced it

### Requirement: Summary content is safe to commit
The summary MUST contain no absolute path, credential, or authorization header, and no raw bundle content beyond reviewed aggregates and short trace excerpts.

Source: docs/project_spec.md line 175.

#### Scenario: Committed summary scanned
- **WHEN** the summary is scanned for absolute home paths and key-like strings
- **THEN** none are found

### Requirement: Honest framing travels with the data
The summary SHALL include the documented limits of the prompt comparison (30 trials per variant, one model and provider, fixed sampling, no repeated runs, benchmark-informed prompt change) and a statement that the comparison is not a measured improvement or breakthrough.

Source: accepted user decisions; docs/prompt_comparison.md.

#### Scenario: Limits are present
- **WHEN** a consumer reads the comparison section of the summary
- **THEN** the limits and the non-claim are present, each quoting its source document

### Requirement: Drift check against documents and charts
A check command SHALL fail with a readable message when the summary disagrees with its committed sources. Offline it SHALL validate structure and arithmetic, confirm each document-cited value still appears in its cited document, and confirm the committed charts and manifest equal a fresh render. It MUST NOT need the network, Podman, MLflow, or credentials.

Source: accepted user decisions.

#### Scenario: CI has no bundles
- **WHEN** the check runs without bundles
- **THEN** it validates the committed summary, documents, charts, and manifest and exits zero without silently skipping

#### Scenario: A cited document changed
- **WHEN** a quoted line no longer occurs in its document
- **THEN** the check exits non-zero and names the stale quote

### Requirement: Drift check against retained bundles
When the retained bundles are supplied, the check SHALL recompute the bundle-derived sections and require equality with the committed summary. It MUST open bundles read-only and MUST NOT read the spending ledger.

Source: accepted user decisions.

#### Scenario: Summary no longer matches the bundles
- **WHEN** a bundle-derived value differs from the committed summary
- **THEN** the check exits non-zero and names the differing field

### Requirement: Deterministic SVG charts without scripts
Charts SHALL be generated as plain SVG from the summary alone, with no JavaScript, vendored library, or network reference, and the output MUST be byte-identical for identical input.

Source: accepted user decisions.

#### Scenario: Requested chart sets exist
- **WHEN** the charts are generated
- **THEN** there are charts for (a) successful trials, hidden checks, edge cases, per category and per task, (b) failure labels and the `lists_02` and `strings_01` stories, (c) model calls, tool attempts, tokens, latency, and charged versus reserved CHF, (d) test counts, CI evidence, and archived changes

#### Scenario: Charts regenerate identically
- **WHEN** the generator runs twice on the same summary
- **THEN** the SVG files are byte-identical and contain no script or external reference

### Requirement: Accessible, print-legible charts
Each chart MUST have a title and description naming what is compared and the two variants, an opaque light background, text value labels with counts beside rates, and a pattern or marker difference between variants so it stays legible in greyscale print.

Source: accepted user decisions.

#### Scenario: Chart is read by assistive technology
- **WHEN** a chart is opened in a browser or read by a screen reader
- **THEN** the title and description state the comparison and the counts, and values are also present as text

### Requirement: Charts make no unsupported claims
Captions MUST NOT present the comparison as a measured improvement or breakthrough, and the latency and cost charts MUST state that figures were measured once per variant at different times and are not attributed to the prompt.

Source: accepted user decisions; docs/prompt_comparison.md.

#### Scenario: Latency chart caption
- **WHEN** the latency chart is listed in the manifest
- **THEN** its caption states the single measurement per variant and makes no attribution to the prompt

### Requirement: Stable consumer manifest
The project SHALL publish one manifest listing every figure, reused diagram, screenshot, logo, recording, and the title information, each with a stable identifier, repository-relative path, format, caption, alt text, and provenance reference. Identifiers and the schema version MUST NOT change without a version bump.

Source: planned changes `add-presentation-deck` and `add-presentation-report`.

#### Scenario: A consumer resolves every asset
- **WHEN** a consumer loads the manifest
- **THEN** every listed path exists, or the entry is marked pending with its owner

### Requirement: Title information and date placeholder
The manifest SHALL carry "Jose Luis Barahona" and "CAS Applied Machine Learning (ZHAW)" and a visible date placeholder for the user to fill in; tooling MUST NOT choose a date.

Source: accepted user decisions.

#### Scenario: Date not invented
- **WHEN** the title information is read
- **THEN** the date is empty and the placeholder is present

### Requirement: Existing diagrams reused by reference
The existing `docs/*.drawio.svg` diagrams SHALL be listed in the manifest by path with caption and alt text, and MUST NOT be copied or redrawn.

Source: accepted user decisions.

#### Scenario: Diagram registered
- **WHEN** the manifest is loaded
- **THEN** each listed diagram path points at the original file under `docs/`

### Requirement: Coordinator-owned screenshots
The project SHALL define the MLflow UI and local HTML report screenshots as a fixed list with path, content, and required identifiers. The coordinator captures them; until a file exists the manifest MUST list it as pending.

Source: accepted user decisions.

#### Scenario: Screenshot not yet captured
- **WHEN** a listed screenshot file is absent
- **THEN** the manifest marks it pending with the coordinator as owner and the check does not count it as present

### Requirement: Scripted credential-free recording
The project SHALL provide a script that records the credential-free part of `docs/demo.md` as an asciicast v2 file, without voice, from a scripted command list. It MUST run commands with no inherited credentials, call no model API, scrub absolute paths, abort on a secret pattern, and describe grading replay as regrading.

Source: accepted user decisions; docs/demo.md.

#### Scenario: Recording is reproducible from the script
- **WHEN** the recorder runs on a prepared laptop
- **THEN** it writes a valid asciicast v2 file whose commands match the script and whose output has no credential or absolute home path

### Requirement: Self-contained player
The project SHALL provide a hand-written HTML player needing no network and no third-party library, with the full transcript also present as static text. The recording is kept for interested viewers and is not part of the talk.

Source: accepted user decisions.

#### Scenario: Player without scripting
- **WHEN** the player page is opened with scripting disabled
- **THEN** the transcript is readable as static text

### Requirement: Shared title logo with source
The project SHALL commit the ZHAW logo, downloaded once from `https://www.zhaw.ch/storage/engineering/ueber-uns/medien/zhaw_rgb.jpg`, with a note recording the URL, download date, and SHA-256. Nothing may fetch it at build or viewing time.

Source: accepted user decisions.

#### Scenario: Logo provenance
- **WHEN** the logo is listed in the manifest
- **THEN** its source note names the URL and the recorded digest matches the file

### Requirement: Git boundaries for generated outputs
Committed outputs SHALL be sources, the reviewed summary, chart SVGs, the manifest, the logo, reviewed screenshots, and the reviewed recording with its player template. Built HTML pages MUST be generated into the Git-ignored `report/` directory.

Source: docs/project_spec.md line 175 and the report section.

#### Scenario: Built player page
- **WHEN** the player page is built
- **THEN** it is written under `report/` and not tracked

### Requirement: Raw evidence and ledger stay out
Raw bundles, MLflow stores, and the spending ledger MUST stay out of Git, and no script of this change may read the ledger. Ledger totals appear only as values quoted from committed documents.

Source: docs/project_spec.md line 175; accepted user decisions.

#### Scenario: Scripts avoid the ledger
- **WHEN** the scripts are statically inspected
- **THEN** none imports the ledger module or opens the ledger path

### Requirement: Offline deterministic tests
The change SHALL be tested with fixtures and no bundles, network, Podman, or credentials, so the tests run in the existing offline CI group.

Source: docs/project_spec.md (CI section).

#### Scenario: Tests run on a clean runner
- **WHEN** `pytest -q` runs without `run_bundles/`
- **THEN** the presentation-evidence tests run and pass using fixtures
