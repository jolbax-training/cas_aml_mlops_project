# Prompt Comparison Spec Delta

## Purpose

Define a controlled baseline-versus-revised-prompt experiment for the bounded coding agent and how its evidence is analysed and reported.

## ADDED Requirements

### Requirement: Single controlled intervention
The experiment SHALL compare one baseline agent prompt with one revised prompt, holding the benchmark, evaluator, tools, interaction limits, model/provider, and generation settings fixed. The revision MUST document one intended change motivated by inspection of baseline traces/failures.

Source: issue 04 / Q25.

#### Scenario: Baseline has no failures
- **WHEN** baseline inspection finds no failed trials
- **THEN** the write-up states that and motivates the revision from available trace or efficiency evidence without inventing failures

#### Scenario: Setting changed after baseline
- **WHEN** model, provider, evaluator, or benchmark changes after the baseline run
- **THEN** the two runs are not presented as comparable until comparable reruns or rescoring are performed

### Requirement: Preconditions before main runs
The main runs SHALL start only after isolation and scoring-integrity probes pass with demonstrated bypasses resolved, the benchmark is frozen with a recorded version/hash, model settings are frozen after a retained smoke test, and projected total cost fits the CHF 15 ceiling.

Source: issue 04 / answer; issue 02 / Q18; issue 03 / Q21.

#### Scenario: Benchmark not frozen
- **WHEN** a main run is requested before the benchmark freeze is recorded
- **THEN** the run does not start

### Requirement: Repeated independent trials
Each variant SHALL run three independent trials of each of the ten tasks: thirty task trials, 120 hidden check outcomes, and sixty edge-case outcomes per variant, sixty task trials and 240 hidden check outcomes overall. Each trial MUST start a fresh conversation and receive no earlier-trial results.

Source: issue 04 / Q26.

#### Scenario: Verify schedule
- **WHEN** a run's records are checked
- **THEN** every scheduled task/trial ID for that variant is present with its four check outcomes

### Requirement: Bounded paid attempts
The main comparison SHALL use at most 240 logical model calls plus 120 transport retries, 360 physical attempts, all charged to the shared ledger together with development and smoke usage. Unfinished work blocked by the ceiling MUST be preserved and marked incomplete.

Source: issue 04 / Q28, Q29, answer.

#### Scenario: Ceiling reached during revised run
- **WHEN** the ledger refuses an attempt during the revised run
- **THEN** the partial bundle is preserved, the run is labelled incomplete, and it is excluded from headline comparison

### Requirement: Primary metric and diagnostics
The comparison SHALL report successful task trials / planned task trials as the primary metric, with counts. It MUST also report task/category results, tasks passing at least once and all three times, hidden-check and edge-case pass rates, failure labels, tool calls, revisions, observed recovery, end-to-end latency, token usage, and reported/estimated cost.

Source: issue 04 / Q27.

#### Scenario: Report a variant's score
- **WHEN** a complete variant's results are summarised
- **THEN** the primary rate is shown with its count over thirty planned trials alongside the diagnostics

### Requirement: Incomplete runs excluded from headline comparison
An incomplete run SHALL be preserved and labelled but MUST be excluded from headline comparison, and denominators MUST NOT be reduced to accommodate missing records.

Source: issue 03 / Q24; issue 04 / Q29.

#### Scenario: Exhausted transport retries
- **WHEN** a trial exhausts its transport retries
- **THEN** the run is incomplete, its observed results remain inspectable, and no headline comparison uses it

### Requirement: Trace-based explanation and claim limits
The comparison SHALL use selected traces to explain gains, regressions, and unchanged outcomes. It MUST state that three repetitions do not establish precise reliability, that benchmark-informed tuning limits claims to these tasks, and that fixed model identifiers do not guarantee immutable upstream weights.

Source: issue 04 / Q27, Q31.

#### Scenario: Write the limitations
- **WHEN** the comparison write-up is reviewed
- **THEN** it contains trace-referenced explanations and the required limitation statements

### Requirement: Keep/reject decision without required improvement
The comparison SHALL end with a reasoned keep/reject decision for the revised prompt. Measured improvement MUST NOT be a completion requirement, and no result, failure, or student reflection may be invented.

Source: issue 04 / Q25.

#### Scenario: Revision does not help
- **WHEN** the revised prompt shows no gain or a regression
- **THEN** the experiment is still complete if both runs are complete, and the decision records rejection or a reasoned keep with evidence

### Requirement: Retained and tracked evidence
Both runs SHALL be retained as durable local bundles and recorded in local MLflow, with the write-up referencing run IDs, bundle locations, MLflow IDs, and benchmark/prompt/configuration versions.

Source: issue 04 / answer; issue 05 / Q35.

#### Scenario: Locate evidence for a result
- **WHEN** a reader follows a metric in the write-up
- **THEN** they can identify the bundle and MLflow run that produced it
