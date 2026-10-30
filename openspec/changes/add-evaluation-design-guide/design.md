# Design

## Context

See proposal.md. The orchestrator structure and scenarios were confirmed in issue 06; GLOSSARY.md defines coordinator, work item, worker, independent verifier, and final check. Retained OpenRouter research (issue 08) can supply evidence fixtures. Nothing here is implemented; all tasks remain unstarted.

## Goals / Non-Goals

**Goals:** A concise reusable method, one concrete worked design with six scenarios, honest labelling of proposed versus executed evidence.

**Non-Goals:** Building or running the orchestrator, executing verifiers, calibrating an LLM judge, generic multi-agent framework comparison, or claiming that the OpenRouter research was produced by this workflow.

## Decisions

### 1. Two documents with shared vocabulary

A guide document states the method in transferable steps: define the outcome and success criteria; choose representative tasks and scenarios; choose graders (deterministic checks first, human review, rubric-based judging only with validation); validate graders with known-good and known-bad fixtures; define trace evidence; set fixed denominators and incompleteness rules; interpret variability with counts and small-sample caution; decide keep/reject. Each step cites how the implemented coding-agent project applied it. A separate worked-example document applies the steps to the research coordinator. Exact file paths are an implementation choice.

### 2. Worked orchestrator design

The coordinator splits a research request into work items: model controls, provider compatibility, pricing/budget accounting. Each item has one worker and one verifier. The verifier receives a fresh context with only the item's requirement and the worker output/citations, independently inspects supporting sources, and returns pass, needs revision, or unverifiable with evidence. It does not inherit the worker conversation and does not treat confidence as proof; a different model is not required. The final check assesses coverage, unresolved verification failures, and cross-item contradictions.

### 3. Six scenarios with a common template

Each scenario lists inputs, available capabilities, expected outcome and failure handling, graders, and required trace evidence: normal completion; missing work item; unsupported worker claim; conflicting item results; worker/verifier failure; budget exhaustion. One scenario (or a variant) has items passing individually but combining inconsistently, which only the final check catches. Observable checks (coverage, citation presence, verdict recorded) are distinguished from subjective-quality rubrics, and any rubric/judge includes a described validation approach marked as proposed.

### 4. Honest evidence labels

Existing research findings may appear as evidence fixtures with their provenance. Any example trace is labelled illustrative. The documents state that the orchestrator was not executed, independent verification did not occur, and no judge is calibrated.

## Risks / Trade-offs

- Two-hour timebox → keep the guide concise and use the template to avoid sprawl; presentation polish is cut first.
- Reader confusing illustration with results → consistent labels and an explicit status statement at the top of the example.
- Vocabulary drift from the implemented project → reuse GLOSSARY.md terms.

## Migration Plan

Write the guide and example, review them against the spec scenarios, register them as work-log sources, and record completion in progress. Rollback removes the documents only.
