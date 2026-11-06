# project-delivery Specification

## Purpose
Define the verified setup, inspection, replay, and demo path and the honest completion accounting for the four-day agent-evaluation/MLOps project.

## Requirements

### Requirement: Exact tested commands
The project SHALL document setup, trace inspection, grading replay, evidence/MLflow navigation, report build/open, and local CI reproduction with exact commands that were re-executed before being recorded.

Source: issue 07 / Q42; docs/project_spec.md completion checklist.

#### Scenario: Follow setup documentation
- **WHEN** a reader follows the documented commands on a prepared laptop
- **THEN** each command runs as documented and its recorded date/versions match what was tested

### Requirement: Rehearsed demo without required new generation
The final demo SHALL cover trace inspection without API or Podman, grading replay of saved final candidates with Podman and no model API, MLflow navigation, the offline report, the comparison, and the transfer guide. The demo MUST NOT require new paid generation; any live call shown is charged to the shared ledger.

Source: issue 07 / Q42; issue 05 / Q35.

#### Scenario: Rehearse the demo offline from the model API
- **WHEN** the demo is rehearsed with no model credentials configured
- **THEN** inspection, grading replay, report viewing, and evidence navigation all work
- **AND** grading replay is described as regrading, not a fresh agent trial

### Requirement: Checklist-to-evidence accounting
Final status SHALL map each completion-checklist item and each day's exit evidence to retained evidence or an explicit incomplete label with reason. Results, CI runs, MLflow runs, or reflections MUST NOT be invented.

Source: issue 07 Answer; docs/project_spec.md "Completion checklist".

#### Scenario: A required item is unmet
- **WHEN** an item such as a complete comparable run lacks evidence at delivery
- **THEN** progress and the report label it incomplete with the reason
- **AND** the project is not described as complete

### Requirement: Buffer use and cut order
Delivery SHALL use the movable buffer where required work needs it and simplify presentation polish first. Benchmark size, trial counts, fixed denominators, required checks, and scoring-integrity probes MUST NOT be reduced or waived to claim completion.

Source: issue 07 / Q42.

#### Scenario: Time runs short on day four
- **WHEN** remaining time cannot cover both report polish and required evidence
- **THEN** polish is simplified first
- **AND** required evidence work keeps priority or is labelled incomplete

### Requirement: Reflections do not gate delivery
Delivery MUST NOT require completed personal reflections, and unanswered reflection prompts SHALL remain unanswered rather than filled in.

Source: map notes; docs/project_spec.md "Purpose and constraints".

#### Scenario: Reflections missing at delivery
- **WHEN** learning-journal prompts remain unanswered
- **THEN** delivery proceeds and the prompts remain unanswered
