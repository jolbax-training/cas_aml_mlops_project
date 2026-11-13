# Spec Delta

## Purpose
A self-contained offline HTML slide deck for a 15-minute talk, built from committed sources and the shared evidence manifest, with the user's own words kept in user-editable slots.

## ADDED Requirements

### Requirement: Approved outline, fixed order and timing
The deck SHALL contain exactly the 13 slides of the user-approved outline, in that order, with the approved titles and per-slide minutes. The build MUST fail unless the minutes sum to 15.0, and MUST show each slide's minutes and the running total in the notes view.

Source: user-approved outline (2026-11-13).

#### Scenario: Timing check passes
- **WHEN** the deck is built
- **THEN** there are 13 slides whose minutes (0.5, 1, 1.5, 1.5, 1.5, 1.5, 1, 1, 1.5, 1.5, 1, 1, 0.5) sum to 15.0

#### Scenario: A slide is added or a time edited
- **WHEN** the sources define a 14th slide, reorder slides, or the minutes no longer sum to 15.0
- **THEN** the build and its check fail naming the problem

### Requirement: Numbers and figures come from the evidence interface
Every number on a slide MUST be resolved at build time from `presentation/evidence/summary.json`, and every chart, diagram, screenshot and logo MUST be placed by manifest id with the manifest's caption and alt text. The build MUST fail on an unknown id, an unresolved number reference, or a number typed literally into slide text where a summary reference exists.

Source: accepted user decisions; add-presentation-evidence consumer interface.

#### Scenario: Results slide
- **WHEN** slide 9 is built
- **THEN** its counts (27/30 and 29/30 successful trials) are read from the summary and its charts are the manifest figures `outcome-overview` and `outcome-by-category`

#### Scenario: Unknown figure id
- **WHEN** a slide references a figure id absent from the manifest
- **THEN** the build fails naming the slide and the id

### Requirement: Honest framing of the comparison
The deck SHALL present the 27/30 to 29/30 result as a worked example with documented limits and MUST NOT call it an improvement or a breakthrough. Slides 10 and 11 SHALL state why the `lists_02` gain and `strings_01` regression are not proof, and the seven documented limits SHALL be available in the speaker notes of slide 11.

Source: accepted user decisions; docs/prompt_comparison.md.

#### Scenario: Forbidden framing
- **WHEN** the built deck text (including notes and captions) is scanned
- **THEN** neither "improvement" nor "breakthrough" occurs except inside the sentence that denies it

### Requirement: User-authored slots stay the user's words
Slides 2 (Motivation) and 12 (Takeaways) SHALL render the text of a committed user-editable source file. While that text is empty, the slide MUST show a clearly visible placeholder naming the file to edit. The build MUST NOT draft, default or fill these texts, and the same applies to the title-slide date, which stays a visible placeholder while the manifest date is null.

Source: accepted user decisions (authorship).

#### Scenario: Slots unfilled
- **WHEN** the user text file is empty for a slot
- **THEN** the slide shows a visible placeholder box with the slot name and file path, and `--check` reports the slot as unfilled without failing (a `--strict` mode fails)

#### Scenario: Slots filled
- **WHEN** the user writes text into the file and rebuilds
- **THEN** the slide shows that text, HTML-escaped, and no placeholder

### Requirement: Pending evidence is visible
When a manifest screenshot has status `pending` or its file is missing, the slide MUST show a labelled placeholder box with the figure id and its caption instead of an image, and the build report SHALL list it. A `present` screenshot whose file is missing MUST fail the build.

#### Scenario: Pending screenshot
- **WHEN** slide 6 references a screenshot marked pending
- **THEN** the deck builds with a visible "screenshot pending" box and the check prints it as pending

### Requirement: Navigation, counter and layout
The deck SHALL work from `file://` with no network and no library. It SHALL support Right/Left arrows, Space and PageDown/PageUp, Home and End, show a counter "n / 13", and lay each slide out at 16:9 filling the viewport (letterboxed), usable fullscreen. Without JavaScript the slides MUST remain readable as a vertical sequence.

#### Scenario: Keyboard
- **WHEN** the viewer presses Space, ArrowLeft, Home and End
- **THEN** the deck moves to the next slide, the previous slide, slide 1 and slide 13, and the counter updates

#### Scenario: Scripting disabled
- **WHEN** the deck is opened with JavaScript off
- **THEN** all slides, figures and placeholders are visible in order

### Requirement: Legible from the back of a room
Body text MUST be at least 28 px and no text on a slide below 20 px at a 1920x1080 slide, and charts and diagrams MUST be placed at full slide width or large enough that their own minimum font sizes stay above 16 px equivalent. Slides carry few words, with detail in the notes.

#### Scenario: Font floor
- **WHEN** the deck stylesheet is checked
- **THEN** no slide rule sets a font size below the floor, and the check fails otherwise

### Requirement: Print and PDF, one slide per page
Printing the deck SHALL produce one slide per landscape 16:9 page with colours preserved, no navigation chrome, and no notes. A separate generated notes page SHALL print one slide's title, minutes and speaker notes per page.

#### Scenario: Print preview
- **WHEN** the deck is printed to PDF
- **THEN** the page count equals 13 and each page holds exactly one slide

### Requirement: Speaker notes are factual and kept in source
Each slide SHALL have speaker notes in a committed source, stating facts with source references and summary references for numbers, and never the user's interpretation. Notes SHALL be hidden on the slide, toggled with the N key, and written to the notes page.

#### Scenario: Notes toggle
- **WHEN** the viewer presses N
- **THEN** the current slide's notes appear in a panel and pressing N again hides them

### Requirement: Accessibility
Every image and chart MUST carry the manifest alt text; the deck SHALL set `lang="en"`, a document title, landmark roles and slide headings, keep a text contrast ratio of at least 4.5:1 (7:1 for body text), not rely on colour alone, and respect reduced motion by using no animation.

#### Scenario: Missing alt text
- **WHEN** a placed figure has no alt text in the manifest
- **THEN** the build fails

### Requirement: Self-contained and safe output
The built deck MUST need no network or server, MUST inline or copy every asset at build time, and MUST contain no external URL fetched at viewing time (links are plain anchors), no absolute home path, no credential and no ledger content. It SHALL link the recorded demo player and the work log by relative path and mark the link as unavailable text when the target file is not built.

#### Scenario: Output scan
- **WHEN** the built HTML is scanned
- **THEN** it has no `src`/`href`-loaded external resource, no `/Users/`, and no key-like string

### Requirement: Deterministic documented build
One documented command SHALL build `report/deck.html` and `report/deck_notes.html`; `--check` SHALL validate sources, timing, ids and numbers and write nothing; output SHALL be byte-identical for identical sources. A failed build MUST leave previously built files untouched, and the existing `report/index.html` work log MUST remain unchanged.

#### Scenario: Reproducible build
- **WHEN** the build runs twice on unchanged sources
- **THEN** the output files are byte-identical
