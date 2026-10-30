# Proposal

## Why

The project's evaluation goal is a reasoned decision about whether one agent change helps. The user confirmed a controlled baseline-versus-revised-prompt comparison with three independent trials per task (issue 04, Q25–Q27), run under frozen settings and the shared budget. No experiment has been run; this change plans how the two runs are executed, analysed, and reported without presupposing any outcome.

## What Changes

- Define a baseline agent prompt and, after inspecting baseline traces/failures, exactly one revised prompt with one documented intended change. Keep benchmark, evaluator, tools, interaction limits, model/provider, and generation settings fixed.
- Run three independent trials per task per variant: thirty task trials and 120 hidden check outcomes (sixty edge-case outcomes) per variant; sixty task trials and 240 hidden check outcomes overall. Each trial is a fresh conversation without earlier-trial results.
- Bound the main comparison to 240 logical model calls plus 120 transport retries (360 physical attempts), charged to the shared ledger together with development/smoke usage.
- Compute the primary metric (successful task trials / planned task trials) and the agreed diagnostics; inspect selected traces to explain gains, regressions, and unchanged outcomes.
- Produce a keep/reject decision for the revision with explicit limitations. Improvement is not a completion requirement.
- Retain both runs as durable local bundles and record them in local MLflow; exclude any incomplete run from headline comparison.

## Capabilities

### New Capabilities

- `prompt-comparison`: Controlled two-variant prompt experiment, repeated-trial schedule, metrics, trace-based explanation, incomplete-run handling, and the keep/reject decision record.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation adds versioned baseline and revised prompt files, an experiment configuration and run schedule, comparison/summary scripts, a reviewed comparison write-up (Markdown) registered for the work log, and progress entries. It consumes paid API budget through the ledger. It produces experiment evidence but adds no new execution, grading, or tracking mechanism.

Completion evidence: two complete comparable runs, each with thirty task-trial records, 120 check outcomes, and sixty edge-case outcomes, retained locally and in MLflow; a comparison write-up covering metrics, selected traces, efficiency, limitations, and the keep/reject decision; ledger totals within the CHF 15 ceiling. If a run cannot complete, the evidence is the preserved partial bundle labelled incomplete, not a reduced-denominator result.

## Dependencies and milestone

- **Milestone:** Day 3, baseline/inspection/revision/revised run (4h); day 4, comparison write-up within the comparison/report slot (2h), per [the specification](../../../docs/project_spec.md). Exit evidence: two complete comparable runs retained locally and in MLflow (day 3); finished comparison evidence (day 4).
- **Upstream (must be done first):** `harden-candidate-execution` (1) with all isolation and scoring-integrity probes passing and demonstrated bypasses resolved; `add-run-bundles-and-grading-replay` (3); `add-reviewed-benchmark-and-graders` (4) with the benchmark frozen; `add-openrouter-client-and-budget-ledger` (5) with smoke test retained and settings frozen; `add-local-mlflow-tracking` (7). `add-bounded-agent-loop` (2) is required transitively.
- **Downstream:** `add-local-html-work-log` (6) renders the reviewed comparison summary; `prepare-reproducible-demo` (11) demonstrates inspection and grading replay of these runs.
- **Optional / out of scope:** Additional variants, more trials, other models, generalization studies.

## Traceability

- Wayfinder [issue 04](../../../.scratch/revise-project-spec/issues/04-experiment-design.md): Q25 (comparison design), Q26 (repetitions), Q27 (metrics and claim limits), Q29 (incomplete handling under the ceiling), answer bullet on 360 physical attempts.
- Wayfinder [issue 03](../../../.scratch/revise-project-spec/issues/03-benchmark-and-graders.md) Q24 (fixed denominators, incomplete runs excluded) and [issue 08](../../../.scratch/revise-project-spec/issues/08-openrouter-model-research.md) (dated cost envelope informing preflight).
- Specification sections: "Experiment and model configuration" and the completion checklist items on two comparable variants and the comparison explanation.
