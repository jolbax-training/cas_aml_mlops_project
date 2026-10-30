# Design

## Context

See proposal.md. All mechanisms — execution, agent loop, bundles, grading, model client, ledger, MLflow — are delivered by upstream changes. This change is the experiment protocol and its analysis. No baseline or revised run exists, and no result is assumed.

## Goals / Non-Goals

**Goals:** A fair, fixed-settings comparison of two prompts; complete, retained evidence; honest metrics and trace-based explanations; a reasoned keep/reject decision.

**Non-Goals:** Demonstrating improvement, estimating precise reliability, generalizing beyond these ten tasks, tuning beyond one revision, changing model/provider/benchmark.

## Decisions

### 1. Protocol

1. Confirm preconditions: probes pass, benchmark frozen (version/hash recorded), settings frozen, ledger projection fits CHF 15, MLflow reachable (a tracking outage does not block local bundles; upload later).
2. Version the baseline prompt and run 10 tasks × 3 trials as a fresh conversation each, with trial order as an implementation choice recorded in the bundle.
3. Inspect baseline failures and selected traces. Document one intended prompt change and its motivation. If the baseline has no failures, state that and motivate the revision from available trace/efficiency evidence; do not invent failures.
4. Version the revised prompt and run the identical schedule.
5. Verify completeness of both runs, record them in MLflow, and write the comparison.

Any change to model/provider/evaluator/benchmark after baseline invalidates comparability and requires comparable reruns or rescoring as appropriate.

### 2. Metrics

Primary: successful task trials / 30 planned per variant. Diagnostics: per-task and per-category successes; tasks passing at least one trial and all three trials; hidden-check and edge-case pass rates over 120/60 planned outcomes; failure-label counts; tool calls, revisions, observed recovery; end-to-end latency; tokens; reported and estimated/reserved cost. All rates are shown with counts. Computation reuses the accounting from `add-reviewed-benchmark-and-graders`.

### 3. Incompleteness and budget

A run affected by unavailable containers, broken worker protocols, exhausted transport retries, or a ceiling refusal is incomplete: preserve its bundle, label it, and exclude it from headline comparison without shrinking denominators. Whether to rerun after an incomplete run depends on remaining budget and is recorded as a decision; no rerun may exceed the ceiling.

### 4. Write-up and decision

A reviewed Markdown comparison summarises both runs with run IDs, bundle references, MLflow IDs, benchmark/prompt/config versions, metrics, selected trace excerpts explaining gains/regressions/unchanged outcomes, efficiency, and limitations (three repetitions are not precise reliability; benchmark-informed tuning limits claims to these tasks; fixed identifiers do not guarantee immutable weights). It ends with a keep/reject decision and its reasoning. The student's own interpretation, if added, is in their words and never drafted for them.

## Risks / Trade-offs

- Budget exhausted mid-run → preserved incomplete evidence; honest reporting.
- Small sample → no strong claims; counts shown with rates.
- Revision overfits observed failures → acknowledged as a limitation.
- Day-3 time pressure → presentation polish of the write-up is simplified first; trial counts are not reduced.

## Migration Plan

Execute the protocol after all upstream changes are verified. Results enter `docs/progress.md` and a reviewed comparison file registered as a work-log source. Rollback is not applicable to evidence: bundles and ledger entries are retained even if the analysis is revised.
