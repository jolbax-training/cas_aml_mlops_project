# Proposal

## Why

The comparison is only meaningful if the benchmark and graders are trustworthy. The current pilot has three tasks and twelve cases whose expected answers have not been re-reviewed; the user-confirmed plan (issue 03, Q21–Q24) requires a frozen ten-task benchmark with independent reference validation, deterministic grading, and fixed-denominator accounting before any baseline run.

## What Changes

- Expand the benchmark to ten tasks: two each in strings, lists, dictionaries, numeric logic, and parsing/formatting. Each task has two ordinary and two edge hidden acceptance checks (forty checks, twenty edge cases, per trial of every task). Re-review the three pilot tasks before including any of them.
- Require a separately reasoned reference solution and reviewed expected answers for every task, with retained review evidence (reviewer, date, derivation/reference, corrections, task/case IDs, benchmark version/hash).
- Validate unique IDs, category distribution, argument/schema shape, and case counts; freeze and version the benchmark before baseline.
- Define deterministic grading: strict recursive type-aware equality over the JSON-compatible scope, input-mutation detection, per-check results, and multiple failure labels. Exclude floating-point tolerance and expected-exception tasks.
- Define trial success (contract-valid final source and all four hidden checks pass without mutation) and treat tool use, revisions, recovery, latency, and cost as diagnostics only.
- Define fixed-denominator accounting and run completeness: candidate failures count against scores; contract errors and `no_submission` mark all four checks unsuccessful and unexecuted; deadline interruptions are attempted and unsuccessful; infrastructure and exhausted-transport failures make the run incomplete.
- Add deterministic evaluator fixtures for correct and deliberately faulty candidates. Human inspection of selected traces is the qualitative review; an implemented LLM judge is not required.

## Capabilities

### New Capabilities

- `benchmark-and-grading`: Reviewed, frozen coding-task benchmark; deterministic final-submission grading; failure labels; fixed-denominator accounting and completeness verification.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation affects the task dataset (new versioned benchmark file alongside the pilot), review records, task/dataset validation, the comparison and grading logic in the trusted evaluator, accounting/summary code, and evaluator fixtures/tests. Candidate execution mechanics belong to `harden-candidate-execution`; the agent interaction that produces final submissions belongs to `add-bounded-agent-loop`.

Completion evidence: a validated, frozen ten-task benchmark with forty reviewed checks, reference solutions, and retained review evidence; passing deterministic fixture tests covering every accounting row; and a progress entry with the benchmark version/hash. No benchmark result or model score is produced by this change.

## Dependencies and milestone

- **Milestone:** Day 2, benchmark/reference review (3h) in the four-day plan of [the specification](../../../docs/project_spec.md). Exit evidence: reviewed ten-task benchmark.
- **Upstream:** `harden-candidate-execution` (1) provides the per-check restricted execution used for hidden acceptance checks and limit outcomes; `add-bounded-agent-loop` (2) defines final submission, contract failures, and `no_submission`. `add-run-bundles-and-grading-replay` (3) stores the per-check grades this change defines.
- **Downstream:** The benchmark MUST be frozen before `run-prompt-comparison` (9). `add-deterministic-ci` (8) runs its fixtures; `add-local-html-work-log` (6) references its review record.
- **Out of scope / optional:** Larger suites (for example, the earlier thirty-task stretch), an implemented LLM judge, floating-point or exception tasks.

## Traceability

- Wayfinder [issue 03](../../../.scratch/revise-project-spec/issues/03-benchmark-and-graders.md): Q21 (scope), Q22 (grader validation), Q23 (success/diagnostics), Q24 (accounting/completeness).
- Experiment denominators (three trials, 240 outcomes) are owned by `run-prompt-comparison` per issue 04.
- Specification sections: "Benchmark, graders, and evaluator validation" and "Accounting and completion".
