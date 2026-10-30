# Evaluation design guide

A reusable method for deciding whether a change to an agent system helps. It is written so that you can follow it for any agent, and each step cites how this repository's coding-agent project applied (or plans to apply) it. The [research coordinator example](research_coordinator_example.md) applies the same steps to a different kind of system.

## Status of the cited evidence

The coding-agent project is mostly **planned**: the [specification](project_spec.md) defines the design, and [progress](progress.md) records what exists. At the time of writing only the offline evaluator (dataset validation, per-check Podman execution, external scoring) is implemented. Where a step below says "the coding-agent project does X", read it as "its specification requires X" unless [progress](progress.md) records evidence. No comparison results, MLflow runs, or CI successes are claimed here.

Vocabulary follows [GLOSSARY.md](../GLOSSARY.md): coding task, task trial, acceptance check, evaluation run, and, for the orchestrator example, coordinator, work item, worker, independent verifier, and final check.

## The seven steps

For each step: what to decide, what evidence to retain, and the coding-agent application.

### 1. Define the outcome and success criteria

- **Decide:** What the agent must accomplish, for whom, and what counts as success or failure. Separate *outcome* (did the result satisfy the requirement) from *process* (did it stay within allowed behavior, budget, and tools). State what is out of scope.
- **Retain:** A written success definition, the allowed capabilities and limits, and the decision you will make with the result (keep or reject a change).
- **Coding agent:** Success is a final submission that satisfies hidden acceptance checks and the strict output contract; process limits are at most four logical model calls, three tool attempts, and four checks per tool request. The comparison decides keep/reject for a revised prompt; improvement is explicitly not required ([specification](project_spec.md)).

### 2. Select tasks and scenarios

- **Decide:** A set that is representative of the real use, covers named categories, and includes edge and failure cases, not just the happy path. Fix the set before you look at results so that you cannot tune it to the outcome. Have the tasks reviewed independently of whoever wrote the reference answers.
- **Retain:** The frozen task list, the category for each task, who or what reviewed it, and the freeze date.
- **Coding agent:** Ten independently reviewed tasks across five categories, four cases per task (two ordinary, two edge in the [pilot](pilot_tasks.md)), frozen before the baseline run. The generator sees only the instruction and signature; case inputs and expected outputs stay private until scoring.

### 3. Choose graders, deterministic first

- **Decide:** For each criterion pick the cheapest grader that can be trusted. Prefer, in order: deterministic checks on observable facts; human review for judgement you cannot yet automate; rubric-based or model-based judging only when its agreement with a trusted reference has been validated (step 4). Keep expected answers, scoring code, and secrets outside anything the agent can execute or read.
- **Retain:** For every criterion, the grader type, its inputs, and what it cannot detect.
- **Coding agent:** Hidden acceptance checks with strict type-aware equality and a no-mutation rule, executed in fresh restricted containers, scored outside the candidate. No LLM judge is used; a judge may be discussed only as a design.

### 4. Validate the graders

- **Decide:** Before trusting a grader, show it accepts known-good behavior and rejects known-bad behavior, including *tempting* wrong answers. For a rubric or judge, compare against human labels on a held-out set and record the agreement. Also check that the agent cannot tamper with the grader.
- **Retain:** The known-good and known-bad fixtures, their expected verdicts, the observed verdicts, and for any judge the labelled set and agreement statistic. An unvalidated grader must be labelled as such in every result that uses it.
- **Coding agent:** Reference solutions must pass and deliberately wrong or mutating solutions must fail each task's checks; isolation and scoring-integrity probes (forged responses, concealed mutation) are required before any live comparison. These are planned requirements, not recorded results, until [progress](progress.md) says otherwise.

### 5. Define trace evidence

- **Decide:** What must be recorded so that any verdict can be audited without re-running the agent: inputs, each model request and response, tool calls and results, budget used, and the grader's verdict with the evidence it used. Persist locally first; a tracking service is a convenience, not the source of truth.
- **Retain:** A per-trial bundle, plus enough to replay grading offline without any model call.
- **Coding agent:** Durable local bundles are written before upload to the containerized MLflow service; separate commands inspect a bundle, replay grading in Podman, and run API-free interaction fixtures.

### 6. Fix denominators and incompleteness rules

- **Decide:** The exact number of units you expect before running, and how each unit that did not finish is counted. Decide in advance whether infrastructure failures are excluded (and reported) or counted as failures; never drop units silently or change the denominator after seeing results. Set budget stop rules as well.
- **Retain:** Expected counts, actual counts, a list of every incomplete unit with its reason, and the budget ledger.
- **Coding agent:** Sixty task trials (ten tasks, three trials, two prompts) and 240 check outcomes; infrastructure-incomplete runs are excluded and listed; a single shared CHF ledger with a checkpoint and a ceiling covers all paid calls.

### 7. Interpret variability and decide keep or reject

- **Decide:** Report counts, not just percentages, per task and overall. With few trials, treat small differences as noise: say which tasks improved, regressed, or stayed unchanged, and state the limits (one model, one benchmark, few trials). Make the keep/reject decision against the criterion fixed in step 1 and write down the reason, including "inconclusive".
- **Retain:** Per-task paired outcomes, the decision, the reasoning, and the known limitations.
- **Coding agent:** Three trials per task per prompt, paired comparison of baseline and revised prompts, and an honest decision record; measured improvement is not required for the project to succeed.

## Applying the guide to a new agent: checklist

1. Write the success definition and the decision it feeds.
2. List tasks/scenarios by category; freeze them; record who reviewed them.
3. For each criterion choose a grader; mark each as deterministic, human, or judge.
4. List known-good and known-bad fixtures per grader; mark any grader not yet validated.
5. Specify the trace evidence each verdict needs.
6. Fix expected counts, incompleteness handling, and budget rules.
7. Plan how variability will be reported and what result would mean keep or reject.

## Labelling discipline

Keep three kinds of statement visibly separate in any evaluation document: **executed** (with evidence), **planned** (a requirement not yet met), and **illustrative** (an invented example showing the format). Never let an illustration read as a result.
