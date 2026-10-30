# Evaluation Design Guide Spec Delta

## Purpose

Provide a reusable agent-evaluation design method and a design-only worked example for a research-workflow orchestrator, demonstrating transfer beyond the implemented coding agent.

## ADDED Requirements

### Requirement: Reusable evaluation-design guide
The project SHALL provide a guide explaining how to define success, select tasks and graders, validate graders, inspect traces, interpret variability, and decide whether a change helps, with references to how the implemented coding-agent evaluation applied each step.

Source: issue 06 / Q40; docs/project_spec.md "Transferable evaluation-design guide and example".

#### Scenario: Apply the guide to a new agent
- **WHEN** a reader follows the guide for an agent system other than the coding agent
- **THEN** each step states what to decide and what evidence to retain
- **AND** the coding-agent project is cited as an applied example

### Requirement: Research coordinator worked design
The worked example SHALL describe a research coordinator that splits a request into work items, assigns one worker and one independent verifier per item, and runs a final check across all items. It MUST use the OpenRouter investigation as the concrete illustration with items for model controls, provider compatibility, and pricing/budget accounting.

Source: issue 06 / Q38.

#### Scenario: Read the example structure
- **WHEN** a reader opens the worked example
- **THEN** the coordinator, the three work items, their workers and verifiers, and the final check are described with their inputs and outputs

### Requirement: Fresh-context independent verification
Each verifier in the design SHALL receive a fresh context containing only the item's requirement and the worker output/citations, independently inspect supporting sources, and return pass, needs revision, or unverifiable with evidence. It MUST NOT inherit the worker conversation or treat worker confidence as proof; a different model is not required.

Source: issue 06 / Q41.

#### Scenario: Worker claim lacks support
- **WHEN** a worker's claim is not supported by the cited sources
- **THEN** the designed verifier returns needs revision or unverifiable with the evidence it checked

### Requirement: Final cross-item check
The design SHALL include a final check assessing coverage of all items, unresolved verification failures, and contradictions across items.

Source: issue 06 / Q38, Answer bullet 6.

#### Scenario: Individually passing items combine inconsistently
- **WHEN** every item passes its verifier but two item results contradict each other in the combined recommendation
- **THEN** the final check is designed to detect and report the inconsistency

### Requirement: Six specified scenarios
The worked example SHALL specify normal completion, a missing work item, an unsupported worker claim, conflicting item results, worker/verifier failure, and budget exhaustion. Each scenario MUST state inputs, capabilities, expected outcomes and failure handling, graders, and required trace evidence.

Source: issue 06 / Q39.

#### Scenario: Review scenario completeness
- **WHEN** a reviewer checks the six scenarios
- **THEN** each has all five required elements
- **AND** observable checks are distinguished from subjective-quality rubrics with a described validation approach where a rubric is proposed

### Requirement: Honest design-only labelling
The guide and example MUST label proposed graders, rubrics, and traces as design or illustrative, and MUST NOT claim that the orchestrator ran, that independent verification occurred, or that any LLM judge is calibrated. Existing research MAY be used as labelled evidence fixtures.

Source: issue 06 Answer bullets 2, 4, 6; issue 03 / Q22.

#### Scenario: Illustrative trace shown
- **WHEN** the example includes a trace or grader output
- **THEN** it is visibly labelled illustrative
- **AND** the document states that no orchestrator system was built or executed
