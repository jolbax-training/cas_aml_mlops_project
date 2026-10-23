# Define tasks, graders, and evaluator validation

Label: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: 01, 02

## Question

What benchmark and grading approach demonstrate trustworthy outcome and agent-behavior evaluation within 32 hours? Decide task coverage and size, development versus hidden acceptance cases, independent expected-answer/reference validation, deterministic and human review roles, trace checks, failure labels, fixed denominators, and evaluator test evidence. Distinguish mandatory requirements from stretch work and settle the task/trial/check/run vocabulary.

## Comments

### Q21 — User-confirmed benchmark scope

Use ten tasks: two each for strings, lists, dictionaries, numeric logic, and parsing/formatting. Each task has four hidden acceptance checks, split into two ordinary and two edge cases. The suite therefore contains forty checks, including twenty edge cases. Reuse the three pilot tasks only after reviewing their expected answers. Freeze the benchmark before the comparison.

### Q22 — User-confirmed grader validation

Every task requires a separately reasoned reference solution and reviewed expected answers. Deterministic evaluator fixtures must cover successful and deliberately faulty candidates, including wrong answers, mutation, invalid source, exceptions, and execution limits. Use deterministic grading and human inspection of selected traces for the implemented project. An LLM judge may be discussed in the orchestrator transfer design without becoming an implementation requirement.

### Q23 — User-confirmed success and diagnostic criteria

A trial passes only when its final function satisfies the source contract and passes all hidden checks without input mutation. Use strict type-aware comparisons and the existing JSON-compatible scope; exclude floating-point tolerance and expected-exception tasks. Keep per-check results and failure labels. Tool use, revisions, recovery, latency, and cost are diagnostic measures; do not prescribe tool-call sequences or fail an otherwise correct early submission merely because it did not use the optional development tool.

Fixed-denominator accounting and incomplete-run treatment remain to be confirmed before resolution.

### Q24 — User-confirmed accounting and completeness

Keep full planned denominators. Wrong answers, mutation, candidate exceptions, timeouts, and excessive output count as candidate failures. Final syntax/contract errors and missing submissions mark all four hidden checks unsuccessful and unexecuted. Deadline-interrupted checks count as attempted and unsuccessful. Container unavailability, broken worker protocols, and exhausted API transport retries make the run incomplete; preserve partial evidence and exclude incomplete runs from headline comparisons rather than reducing denominators. Completion requires records for every planned task/trial and valid outcomes for executed checks. Report counts alongside rates.

## Answer

User-confirmed through Q21–Q24:

- Freeze a ten-task benchmark before comparison: two tasks each in strings, lists, dictionaries, numeric logic, and parsing/formatting, each with two ordinary and two edge acceptance checks. That is forty hidden checks, including twenty edge cases, for one trial of each task. Re-review the existing pilot before inclusion.
- Give every task a separately reasoned reference solution and reviewed expected answers. Retain review evidence and validate the evaluator with deterministic fixtures for correct code, wrong answers, mutation, source violations, exceptions, and execution limits. Human review covers selected traces; an implemented LLM judge is not required.
- A trial succeeds only when the submitted function meets the source contract and all four hidden acceptance checks pass without input mutation. Use strict recursive type-aware equality for the agreed JSON-compatible scope. Floating-point tolerance and expected-exception tasks are excluded. Retain per-check results and failure labels.
- Treat tool use, revisions, recovery, latency, and cost as diagnostics. Optional tool use and valid alternative action sequences do not themselves determine failure. The final function can pass after an early submission without development-tool use.
- Keep every planned check in the denominator. Candidate failures count against scores. Final syntax/contract errors and `no_submission` make all four hidden checks unsuccessful and unexecuted; an execution deadline makes the interrupted check unsuccessful and attempted.
- Mark runs incomplete for unavailable containers, broken worker protocols, or exhausted API transport retries. Preserve observed results without headline comparisons or artificially reduced denominators. Verify every scheduled task/trial is represented, rather than checking aggregate counts alone, and require valid outcomes for executed checks.
- Report counts as well as rates. Repeated-trial counts, comparison intervention, transport retries, and model settings are owned by the experiment-design ticket.
