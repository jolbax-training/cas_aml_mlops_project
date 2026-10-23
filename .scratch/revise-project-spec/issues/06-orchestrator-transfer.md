# Transfer the evaluation method to a workflow orchestrator

Label: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: 03

## Question

What concrete orchestrator scenario and worked evaluation design will demonstrate transfer beyond coding agents without building a second system? Specify representative tasks, desired outcomes, routing/handoff/recovery criteria, appropriate graders and their validation, trace evidence, and efficiency/reliability measures. Define the reusable guide and the minimum evidence that makes the example substantive.

## Comments

### Q38 — User-selected orchestrator structure

The user replaced the proposed research/drafting/review example with a coordinator that splits the work, one worker agent per item, one independent verifier per item, and one final check across all items. The task can be the assistant's searching/research. Use the recent OpenRouter research as the proposed concrete illustration, rather than assuming a fixed document-pack brief. The four-stage structure is confirmed; precise verifier independence, handling failed verification, and example coverage still need agreement.

Q39 (the proposed six-scenario coverage) and Q40 (guide plus worked design and illustrative graders/traces) were not answered and remain open. They must be adapted to this updated scenario rather than treated as accepted.

### Q39–Q41 — User-confirmed coverage, deliverable, and independence

The user accepted the adapted six scenarios, guide plus worked design, and fresh-context source-checking verifiers. These confirmations supersede the preceding open-items note.

## Answer

User-confirmed through Q38–Q41:

- Use a research coordinator that splits work into items, one worker per item, one independent verifier per item, and a final check across all items. This supersedes the earlier proposed fixed-document-pack research/drafting/review brief.
- Use the assistant's recent OpenRouter investigation as the concrete example: work items for model controls, provider compatibility, and pricing/budget accounting. The final check evaluates completeness and consistency of the combined recommendation. Existing research can supply evidence fixtures; do not retroactively claim the proposed orchestrator or independent-verifier workflow was executed.
- Cover six evaluation scenarios: normal completion, a missing work item, an unsupported worker claim, conflicting item results, worker/verifier failure, and budget exhaustion. Include a case where items pass individually but their combination is inconsistent, exercising the final check.
- Produce a reusable evaluation-design guide plus this worked design with concrete inputs, grading criteria, required evidence, and clearly labelled illustrative traces. Distinguish proposed behavior from executed or verified evidence. This is a design transfer exercise, not a second implemented agent system.
- A verifier uses a fresh context with the item's requirement and worker output/citations, independently inspects supporting sources, and returns pass, needs revision, or unverifiable with evidence. It does not inherit the worker conversation or treat confidence as proof. Independence requires separate execution/evidence checking, not necessarily a different model.
- The final check assesses coverage, unresolved verification failures, and cross-item contradictions. Proposed graders and any subjective-quality rubric must be labelled as a design; do not fabricate executed results or evidence of judge calibration.
