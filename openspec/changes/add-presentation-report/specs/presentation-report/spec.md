## ADDED Requirements

### Requirement: Four-page printable HTML report
The project SHALL build one self-contained HTML report of four fixed A4 pages, readable on screen and printable as exactly four pages, in English, from committed sources.

Source: accepted user decisions; docs/project_spec.md (report section).

#### Scenario: Structure
- **WHEN** the report is built
- **THEN** it contains exactly four page sections and each page footer shows its number out of four

#### Scenario: Printed length
- **WHEN** the report is printed to A4 with margins none
- **THEN** the result has four pages and no blank fifth page

### Requirement: Page content follows the deck structure
Pages 1 and 2 MUST carry the motivation slot with the problem statement, and the approach (architecture and run-flow diagrams, sandbox and scoring integrity, reproducibility, the budget ledger). Pages 3 and 4 MUST carry the results and statistics, and the limits, lessons learned, conclusions slot and references/evidence section.

Source: accepted user decisions; approved talk outline.

#### Scenario: Chart sets present
- **WHEN** page three is inspected
- **THEN** outcome comparison, failure labels with the two trace stories, efficiency and cost, and engineering statistics each have at least one chart, and omitted values appear as a table from the summary

#### Scenario: Pages carry their sections
- **WHEN** the report is built
- **THEN** page one has the title information, motivation slot and problem statement, page two the approach, page three the results and page four the limits, lessons, conclusions slot and references

### Requirement: Page overflow is detected
The project SHALL detect content that does not fit its page: offline checks MUST fail on a structural or budget violation (including uncalibrated budgets) without a browser, and a browser measurement SHALL fail when a page's content is taller than its box or the printed PDF does not have four pages.

Source: accepted user decisions (exactly four printed pages).

#### Scenario: A page overflows
- **WHEN** a page's content is taller than its box in the measurement
- **THEN** the measurement exits non-zero and names the page and the excess height

#### Scenario: Spare space is visible
- **WHEN** a page's content is shorter than its box
- **THEN** the measurement reports the content height, not the box height, so spare space shows as less than full

#### Scenario: Missing browser is not a pass
(A missing browser MUST be reported as skipped, never as a pass, and an unreadable page count MUST fail distinctly.)

#### Scenario: No browser available
- **WHEN** the measurement runs without a browser
- **THEN** it reports that it was skipped with a distinct exit status and does not report success

#### Scenario: Uncalibrated budgets
- **WHEN** the per-page budgets carry no calibration note
- **THEN** the offline check fails with "budgets not calibrated" instead of passing

#### Scenario: Page count undeterminable
- **WHEN** the printed PDF's page count cannot be read or its two counts disagree
- **THEN** the measurement fails with a message distinct from a wrong count

#### Scenario: Print rules that change layout
(The print stylesheet MUST NOT change box geometry or type size relative to screen, so the screen measurement stands for the printed layout.)
- **WHEN** the print stylesheet contains a rule other than the page size, break rules, colour adjustment and the navigation hide rule
- **THEN** the check fails

#### Scenario: CI without a browser
- **WHEN** the offline check runs in CI
- **THEN** it validates structure, print rules and per-page budgets and needs no browser, network, Podman, bundles or credentials

### Requirement: Numbers and figures come only from recorded evidence
Every number in the report MUST be resolved from the evidence summary by reference, and every figure, diagram, screenshot, logo, caption and alt text MUST be resolved by manifest identifier. The report SHALL NOT contain a typed number in its prose, SHALL render a caption exactly as the manifest gives it, and SHALL show the source keys of each chart.

Source: accepted user decisions.

#### Scenario: A typed number
- **WHEN** the template prose contains a digit sequence that is not a directive or on the reviewed allowlist
- **THEN** the check fails and names the text

#### Scenario: Unknown reference
- **WHEN** a directive names an id, key or slot that does not exist
- **THEN** the build fails and names it, and no empty value is rendered

### Requirement: Print legibility
The report SHALL place only figures whose text prints at 7.5 pt (2.646 mm) or more, computed by viewBox arithmetic for figures and read directly from the stylesheet, with text contrast of at least 4.5:1. Page three uses the compact chart variants and page two the pipeline-overview and trust-boundary diagrams.

Source: accepted user decision D1 (compact charts and tables, nothing below 7.5 pt printed).

#### Scenario: Dense draw.io diagrams
- **WHEN** the references are read
- **THEN** the draw.io diagrams appear only as repository paths, not as figures

#### Scenario: Dense diagram as a figure
- **WHEN** a figure, including a diagram, would print text below 7.5 pt
- **THEN** the check fails and does not merely warn

#### Scenario: Chart too small
- **WHEN** a chart's minimum font size in viewBox units times its rendered width over its viewBox width is below 2.646 mm
- **THEN** the check fails naming the chart and the computed size

#### Scenario: Small type in the stylesheet
- **WHEN** the stylesheet sets a font size below 7.5 pt or a low-contrast text colour
- **THEN** the check fails naming the rule

#### Scenario: Compact variant by identifier
- **WHEN** the template names a chart id absent from the manifest
- **THEN** the build fails and names the id

### Requirement: Figure numbering and cross-references
The report SHALL number figures, diagrams and screenshots once, in order of appearance, and every in-text figure reference MUST resolve to that numbering.

Source: accepted user decisions.

#### Scenario: Reference agrees with figure
- **WHEN** a text refers to a figure by identifier
- **THEN** it shows the same "Figure N" label as the figure's caption

### Requirement: Honest framing and limits
The report SHALL describe the prompt comparison as a worked example with limits, SHALL include all seven documented limits and the non-claim from the evidence summary, and MUST NOT use the words "improvement" or "breakthrough" anywhere except inside elements the builder marks as verbatim quotations of the evidence summary (limits, non-claim, quoted document lines); the user's slot text is checked too.

Source: accepted user decisions; docs/prompt_comparison.md.

#### Scenario: Limits present on page four
- **WHEN** the report is built
- **THEN** all seven limits and the non-claim appear, each from its recorded quote

#### Scenario: Forbidden framing
- **WHEN** a text outside a marked verbatim quotation, including a user slot, uses the word improvement or breakthrough
- **THEN** the check fails and names the text or slot

#### Scenario: Quotation marker
- **WHEN** the template tries to mark its own text as a verbatim quotation
- **THEN** the check fails, because only the limits and quote directives emit the marker

### Requirement: User-authored slots are visible placeholders
The motivation and takeaways SHALL come from the `report` keys of the shared `presentation/user_text.toml`, and no tool or agent MUST draft them. An empty slot SHALL render as a placeholder that survives print and a filled slot as escaped text, and a filled text MUST NOT be cut off: it fails when it does not fit its box.

Source: accepted user decisions (authorship).

#### Scenario: Empty slot
- **WHEN** the user text file has an empty motivation
- **THEN** the report shows a visible placeholder, with a border so it survives printing without background graphics, naming the slot and `presentation/user_text.toml`

#### Scenario: Release build with placeholders
- **WHEN** a release build runs while a slot, the date or a used screenshot is unfilled
- **THEN** it exits non-zero listing each unfilled item

#### Scenario: Release gate
- **WHEN** a release build runs
- **THEN** it fails while any slot, the date or a used screenshot is unfilled

#### Scenario: No second user-text file
- **WHEN** the change's files are listed
- **THEN** none is a user-text file

#### Scenario: Slot fit rule
(A text that does not fit its fixed box, paragraph breaks included, MUST fail the check and the build naming the slot and the limit, and the browser measurement MUST report it if it is clipped there.)

#### Scenario: Slot too long
- **WHEN** the user's `report` text, with its paragraph breaks, needs more lines than the slot's box holds
- **THEN** the check and the build fail naming the slot and the limit, and nothing is written

#### Scenario: Slot clipped in the browser
- **WHEN** the browser measurement finds a slot or figure box whose content is taller than the box
- **THEN** the measurement fails naming it

### Requirement: Pending screenshots and the date are shown, not hidden
A screenshot that the manifest marks pending, or whose file is absent, SHALL render as a visible placeholder naming what it will show and its owner, and the default build MUST succeed with it. A null date SHALL render the manifest's date placeholder, and the builder MUST NOT choose a date.

Source: accepted user decisions; change add-presentation-evidence.

#### Scenario: Pending screenshot
- **WHEN** the manifest marks a used screenshot pending
- **THEN** the report shows a placeholder box with its description and owner and builds

### Requirement: Screen navigation absent from print
The report SHALL offer navigation links between the four pages on screen without scripting, and every navigation element MUST be hidden in print.

Source: accepted user decisions.

#### Scenario: Navigation in print
- **WHEN** the report is printed
- **THEN** no navigation element is visible and the page counter remains

### Requirement: References and evidence section
Page four SHALL list, as visible text, the comparison and smoke run IDs with their full bundle digests (not only in an attribute or tooltip), MLflow run IDs where recorded, and the repository paths of the documents the report relies on, and SHALL link the work log and recorded demo player as relative references whose absence is a non-fatal note.

Source: accepted user decisions; docs/project_spec.md (evidence).

#### Scenario: Evidence on paper
- **WHEN** the report is printed
- **THEN** run IDs, digests and document paths are readable without following a link

### Requirement: Self-contained, script-free, offline report
The built report SHALL contain no JavaScript, no external reference and no network dependency, inline its stylesheet, diagrams, charts, logo and screenshots, pass the work-log SVG allowlist for inlined SVG, and open from a local file. The build MUST be deterministic and write only under the Git-ignored `report/` directory without modifying the work log.

Source: accepted user decisions; docs/project_spec.md line 175.

#### Scenario: Static inspection
- **WHEN** the built file is scanned
- **THEN** it has no script element, event-handler attribute or external URL, declares its language and a title, and keeps the role and title references of inlined charts

#### Scenario: Identical rebuild
- **WHEN** the report is built twice from the same sources
- **THEN** the files are byte-identical

#### Scenario: Work log untouched
- **WHEN** the report is built
- **THEN** `report/index.html` is neither read for content nor changed

### Requirement: Credential, ledger and bundle isolation
The report build and checks MUST read no credential, make no model call, never read the spending ledger, and read no raw bundle; its only evidence inputs are the committed summary, manifest and assets.

Source: accepted user decisions; docs/project_spec.md line 175.

#### Scenario: Build without any secrets
- **WHEN** the build and the checks run with no credentials and no bundles directory
- **THEN** they succeed

### Requirement: Offline deterministic tests
The change SHALL be tested offline against the committed evidence and small templates written per test, with no browser, bundles, network, Podman or credentials, in the existing offline CI group; the browser measurement is run and recorded by hand on a prepared laptop.

Source: docs/project_spec.md (CI section).

#### Scenario: Clean runner
- **WHEN** `pytest -q` runs on a clean runner
- **THEN** the report tests run and pass using fixtures
