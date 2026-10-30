# Tasks

All tasks are unstarted planning items. Timebox: day 2, benchmark/reference review (3h). Requires `harden-candidate-execution` and `add-bounded-agent-loop` outcomes; must be frozen before `run-prompt-comparison`.

## 1. Benchmark structure and validation

- [x] 1.1 Define the versioned benchmark schema (task ID, category, instruction, function name, typed signature, four cases tagged ordinary/edge) and add validation for ten tasks, two per category, two ordinary plus two edge cases per task, unique IDs, and signature-matching arguments; test each failure diagnostic.
- [x] 1.2 Re-review the three pilot tasks' instructions and expected answers; record corrections or exclusions before reusing any.

## 2. Tasks, references, and review evidence

- [x] 2.1 Author the remaining tasks to reach ten, within the JSON-compatible scope and excluding floating-point tolerance and expected-exception tasks.
- [x] 2.2 Write a separately reasoned reference solution per task and run it against the cases as a consistency check; resolve any discrepancy.
- [x] 2.3 Retain review evidence per task (reviewer, date, derivation/reference, corrections, task/case IDs) without counting an unreviewed model answer as validation.

## 3. Grading and accounting

- [ ] 3.1 Verify and extend the existing pilot comparison (`_strict_equal`) and mutation detection in `src/codegen_eval/evaluate.py` against Q23 (type confusion, nested types, list order, dictionary key order, null), keeping them in trusted orchestration and shared with `run_checks`; add tests.
- [ ] 3.2 Record per-check results and multiple failure labels; implement trial success, unexecuted-check accounting for contract errors and `no_submission`, and attempted/unsuccessful deadline interruptions.
- [ ] 3.3 Implement fixed-denominator summaries with counts and rates, and incomplete-run classification for infrastructure, exhausted-transport, and failed-completeness outcomes, consuming the completeness check from `add-run-bundles-and-grading-replay` (task 2.3) rather than reimplementing it.

## 4. Fixtures, freeze, and evidence

- [ ] 4.1 Add deterministic evaluator fixtures for correct, ordinary/edge wrong, syntax/signature/contract errors, exceptions, mutation, timeouts, excessive output, an infrastructure failure, and (once the open decisions in design.md are confirmed) payload-too-large and `request_rejected` outcomes; assert labels and accounting.
- [ ] 4.2 Run the focused and offline test suites and record observed results.
- [ ] 4.3 Freeze the benchmark: record version and content hash over benchmark and review files; document the rerun rule for later changes.
- [ ] 4.4 Update `docs/progress.md` with the benchmark version/hash, review evidence location, and test results, and register the reviewed benchmark summary as a work-log source; claim no model results.
