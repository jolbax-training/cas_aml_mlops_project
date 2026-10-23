# Define the coding agent's behavior and tools

Label: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: none

## Question

What is the smallest tool-using coding agent that teaches the intended evaluation concepts within the time budget? Define its task and final artifact, development tools and visible feedback, stopping behavior, resource limits, and the boundary between one trial's internal revisions and separate trials. Identify which existing single-response and source-contract requirements must change.

## Comments

### Q12 — User-confirmed agent scope

The user accepted the function-writing agent with one optional development tool, `run_checks`, and explicit final submission. Each trial starts from an instruction and typed function signature. The agent writes a candidate and its own example checks, may execute those checks in a restricted Podman container, inspect feedback, and revise within fixed limits. The final function is graded separately against hidden acceptance tests. Internal revisions belong to the same trial. General shell access, repository editing, and network tools are outside the agent's scope.

Exact limits, feedback format, final-response contract, and stopping behavior remain open; this ticket is not resolved.

### Q13–Q15 — User-confirmed limits, feedback, and submission contract

- Each trial permits at most four model calls and three `run_checks` calls, with earlier submission allowed. Limits are configurable and fixed across compared variants.
- `run_checks` accepts candidate source and agent-authored example inputs/expected outputs. It returns structured per-check pass/fail, actual values, and bounded syntax/runtime diagnostics. Hidden acceptance inputs, expected answers, and scores remain unavailable during the trial. Tool use is optional.
- Final output retains the existing raw-source contract: exactly one function with the requested typed signature, optional standard-library imports, no helper functions, and no explanatory prose. The existing source contract remains applicable; do not silently repair invalid submissions or generate another answer after final submission.
- A final contract violation is a recorded candidate failure. Internal development feedback and revisions do not constitute additional trials.

This supersedes the preceding comment's open items for interaction limits, feedback format, and final-response contract. Stopping behavior and handling tool failures still need agreement before resolution.

### Q16–Q17 — User-confirmed stopping and failure behavior

The fourth model call is reserved for final submission, with `run_checks` unavailable on that call. Earlier submission is allowed. Missing final submission produces `no_submission`; drafts and traces are retained. Agent-code and tool-argument errors become bounded recovery feedback and consume the attempted tool call. Container unavailability and broken worker protocols make the trial incomplete due to infrastructure rather than an agent-performance failure.

## Answer

User-confirmed through Q12–Q17:

- Implement a function-writing agent receiving an instruction and typed signature, with one optional development tool, `run_checks`, and explicit final submission. General shell access, repository editing, and network tools are outside the agent's scope.
- A trial contains the entire bounded interaction, including all development candidates, checks, feedback, and revisions. Those revisions are not additional trials. This replaces the previous single-response/no-internal-revision requirement; no new trial or repair is triggered by final grading.
- Permit at most four model calls and three attempted development-tool calls per trial. Make limits configurable and fix them across compared variants. Reserve the fourth model call for final submission and disable the tool on that call; allow earlier submission.
- The agent supplies candidate source and its own example inputs/expected outputs to `run_checks`. Return structured per-check pass/fail, actual values, and bounded syntax/runtime diagnostics from restricted Podman execution. Hidden acceptance inputs, expected answers, and scores never enter development feedback.
- Final submission retains the existing raw Python source contract: one synchronous function matching the requested typed signature, optional standard-library imports, and no Markdown fences, prose, helper functions, classes, decorators, or top-level executable statements. The existing validator's other restrictions remain applicable. Do not silently repair the response.
- Grade only the submitted final function against hidden acceptance checks. Final syntax/contract errors remain recorded candidate failures. If no final submission occurs, record `no_submission` and preserve drafts/trace for inspection.
- Agent source errors, failed development checks, candidate exceptions, and malformed tool arguments consume the attempted tool call and return bounded feedback, allowing recovery within the remaining allowance. Container unavailability and broken worker protocols make the trial incomplete due to infrastructure, rather than a poor-performance trial.
- Retain the existing final evaluator's role while adding a separate agent interaction loop and development-check tool. Detailed containment, benchmark/grader semantics, experiment settings, transport retry policy, and storage are decisions owned by the remaining tickets.
