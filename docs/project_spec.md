# MLOps project working specification

Updated 2026-10-16. This is the current scope and acceptance plan. [Progress and decisions](progress.md) records dated evidence; [original ideas](project_ideas.md) remain historical brainstorming.

## Goal and constraints

Demonstrate a complete, reproducible MLOps workflow: version an evaluation dataset and agent configuration, validate the evaluator, automate deterministic checks, track live experiments, compare results, and explain the resulting decision. An LLM that generates Python functions is the concrete system being evaluated.

This is a self-directed, course-related project with no formal assignment or rubric. The time available is roughly four weeks from this review; the exact final-demo date still needs confirmation. Prioritize a complete, reviewable workflow over benchmark size or extra tools. Work local-first: the first major milestone is a complete generation and evaluation loop running and understood on the laptop with Podman. GitHub Actions and MLflow integration begin only after that milestone passes.

The deliverables are a versioned repository, a continuously updated report, and a runnable system for a final demo. The report is a local-only HTML work log generated from editable Markdown, with one entry point. Publishing, hosting, production deployment, and model training are outside the required scope. Deepchecks and DVC remain optional after the core evidence is complete.

## Starting point

The implemented offline pilot loads three tasks and 12 cases, validates Python source, runs cases in separate restricted Podman containers, and scores results outside those containers. OpenSpec is initialized. The generator, experiment persistence and MLflow integration, GitHub Actions workflows, expanded benchmark, and HTML report generator are planned work. See [progress](progress.md) for dated checks and current blockers; a planned requirement below is not a claim that it already exists.

## Required workflow

1. Establish the laptop loop on the pilot: validate the execution boundary, generate candidates, evaluate them with Podman, and save inspectable results locally. Exercise fixtures first, then a real OpenRouter smoke run. Replay saved responses without API access.
2. Explain one successful and one failed candidate from request through score, including why failures occurred; a known fixture can supply the failure if live candidates all pass. This is the prerequisite for integrating GitHub Actions or MLflow.
3. Freeze the reviewed minimum benchmark and integrate deterministic CI and MLflow around the working local pipeline. Add the local HTML report without making it a dependency of the loop.
4. Run the baseline prompt on the frozen benchmark, retaining the complete run locally and tracking it in MLflow.
5. Inspect failures, document one prompt revision, and repeat with the same benchmark and model settings.
6. Compare gains, regressions, unchanged outcomes, and limitations; decide whether to keep the revision.
7. Update the Markdown report sources, regenerate the local HTML work log, and demonstrate replay and evidence inspection.

The laptop loop must run without GitHub Actions, an MLflow server, or report tooling. Live generation uses OpenRouter as its model API; all orchestration, Podman execution, scoring, and persistence remain local. Saved-response replay and deterministic fixtures require no external service. “Local-first” does not imply that the selected model runs on the laptop.

The iteration is human-guided. A measured improvement is not required; an honest, reproducible comparison is.

## Agent and execution contract

- Input: a natural-language instruction and requested typed Python function signature. Only those task fields, together with the versioned agent prompt, go to the generator. Test cases and expected answers stay private to the evaluator for every benchmark version.
- Output: raw Python source with optional standard-library imports and exactly one synchronous function matching the requested name and signature, including annotations. Markdown fences, prose, helper functions, decorators, classes, top-level executable statements, multi-file solutions, and third-party dependencies are disallowed. Validate the response as returned; do not silently strip fences or repair invalid candidates.
- Use one returned candidate per task and prompt version. Do not resample after a syntax, contract, or behavioral failure. Bounded retries for API transport failures are a separate mechanism and must be recorded.
- For the minimum benchmark, use JSON-compatible strings, integers, booleans, lists, dictionaries with string keys, and null only where explicitly required by a task. Use strict type-aware recursive equality, preserve list order, and ignore dictionary key order. Exclude floating-point tolerance and expected-exception tasks from the minimum scope.
- Inputs must remain unchanged. Invalid input types are outside each task's contract. Unexpected exceptions and serialization failures are candidate failures.
- Each case gets a fresh container. Keep expected answers, scoring code, repository files, API and MLflow credentials, and container-control interfaces outside it. Disable network access and restrict filesystem writes, privileges, child processes, memory, CPU, elapsed time, and output volume, covering both code loading and invocation.
- The pilot pins a Python 3.12 image and provides resource limits. Review those limits and verify isolation on each environment actually used for execution before running live candidates there. Include host-file, environment, network, filesystem, timeout, mutation, and output-limit probes.
- The current worker protocol shares a Python process with candidate code. Review how a candidate could forge results or hide mutation, record the threat model and residual limitations, and resolve unacceptable risks before enabling live evaluation. Container restrictions alone do not prove scoring integrity.

## Benchmark size and independent validation

The planning minimum is **10 tasks**, two each in strings, lists, dictionaries, numeric logic, and parsing/formatting. Each task has two ordinary and two task-appropriate edge cases: **40 cases and 20 edge cases** at the minimum. The existing three-task pilot is the starting point, not the completed benchmark.

Thirty tasks (six per category, 120 cases, 60 edge cases) are an adjustable stretch target. Expand only if independent review and the full workflow fit the time budget. Freeze the selected size before the baseline; never change it between compared runs. Reducing below the minimum requires an explicit scope decision recorded in the report.

Before freezing a version:

- Validate required fields, unique task and case IDs, the declared task count and category distribution, and two ordinary plus two edge cases per task.
- Review each instruction, signature, and case for ambiguity. Cover distinct behaviors instead of adding near-duplicate tasks merely to reach a count.
- Independently derive every expected answer from the written requirement, using a manual trace or a separately reasoned reference implementation. An extra LLM answer alone is not sufficient validation. This review can be done by the student; another reviewer is welcome but not a dependency.
- Record the task/case reviewed, derivation or reference, reviewer, date, and any correction in a retained review record. Check the pilot answers again when including them in the frozen benchmark.
- Retain benchmark content and a version/hash with every run. Changes after freezing create a new benchmark version and require comparable baseline and revised runs on that version.

This small benchmark demonstrates the process and exposes failure patterns. It does not support broad claims about code-generation performance.

## Evaluator validation and scoring

Trusted evaluator code validates the output contract, orchestrates isolated execution, and compares returned values and post-call arguments with expected values. Pytest verifies that evaluator using fixtures with independently specified scores and labels. Include correct code, ordinary-case and edge-case failures, syntax errors, wrong signatures, other contract violations, exceptions, input mutation, timeout, and excessive output. Keep per-case failure labels so one task can exhibit multiple failures.

For a frozen benchmark of N tasks, each complete run uses fixed denominators of N tasks, 4N cases, and 2N edge cases. The primary score is task pass rate: every case must pass for a task to pass. Report case and edge-case pass rates as diagnostics, plus counts overall and by category.

A syntax or contract failure makes all of that task's cases unsuccessful and unexecuted. A case interrupted by the execution timeout is unsuccessful and recorded as attempted, unlike a case never started. Candidate failures count against the score. Exhausted API failures, unavailable containers, and invalid worker protocols make the run incomplete; retain observed counts and partial diagnostics but exclude it from headline prompt comparisons. Do not substitute smaller denominators to make an incomplete run look complete. The future live orchestrator must check all expected task IDs and completed generation/evaluation records, beyond the pilot's aggregate count helper.

## Experiment tracking and comparison

Use OpenRouter through its OpenAI-compatible API. Before the baseline, select and record one model identifier, provider/routing configuration where controllable, generation settings, prompt versions, request timeout, bounded retry policy, and spending limit. Keep them fixed across prompt comparisons except for the intended prompt change. Record actual provider metadata when available and disclose any provider drift.

The required experiment is one complete baseline run and one complete revised-prompt run. Keep Python, dependencies, evaluator, and benchmark fixed. If scoring changes, rescore both saved response sets with the same evaluator. More repetitions are optional; with one run per prompt, explicitly state that run-to-run variation was not measured. Because the revision uses benchmark failures, any gains are improvements on these tasks and are not evidence of generalization to unseen tasks.

For every run retain:

- Run ID, timestamps, completion status, prompt and benchmark versions/hashes, evaluator revision, Python/dependency versions, and container image digest.
- Exact rendered requests, raw responses, candidate source, model settings and available provider metadata, retry/error records, and usage/cost when supplied.
- Per-task and per-case results, failure labels, aggregate counts/rates, and references to the corresponding benchmark and independent review evidence.
- MLflow parameters, metrics, and artifacts sufficient to inspect the experiment, with run IDs linked from the report.

Save a durable local run bundle before attempting MLflow upload. A tracking outage must not lose evidence or trigger new paid generations; support uploading the same bundle later. The local bundle is the primary replay evidence from the first milestone onward; both required comparison runs must ultimately also be tracked completely in MLflow to meet completion criteria. Keep credentials out of all saved requests, logs, artifacts, and report output.

Add tracking only after the local-loop milestone passes. Use local MLflow storage for the minimum workflow; decide the concrete storage path and artifact layout before implementation. Remote tracking is optional. Compare task-level gains and regressions, category counts, case/edge diagnostics, and failure types; document the rationale and resulting keep/reject decision.

## CI and reproducibility

Local Git versioning can be added early without blocking the laptop milestone. Create the GitHub remote and Actions integration after the local-loop milestone passes; this project now has a local Git repository; no remote is configured. The initial commit captures the pilot and planning baseline. Commit source, planning documents, benchmark, prompts, and deterministic fixtures. Define local-only generated artifacts and secret exclusions before adding files.

GitHub Actions must run deterministic benchmark, contract, and scoring checks on pushes and pull requests without model credentials or API calls. Include sandbox integration checks on the chosen compatible CI runner, or a clearly separate automated job on that runner, and retain evidence of its isolation probes. Required deterministic checks gate changes; candidate pass rates are initially report-only. Do not set a performance threshold before measuring a baseline and variation.

Live generation is manually initiated for the minimum scope, using the same documented pipeline locally. Automatic paid runs on prompt changes are optional. If manual or automatic live execution is later added to GitHub Actions, limit it to trusted events, separate secrets from generated code, and bound retries, requests, concurrency, and cost; do not expose credentials to fork pull requests.

Document environment setup, image acquisition, offline tests, live generation/evaluation, replay from saved outputs without API access, MLflow inspection, and report generation. Record exact commands and tested environments as they become available. An unavailable API on demo day can be handled by replaying retained runs, provided the required real live runs were completed and clearly labeled beforehand.

## Continuously updated local report

The report is a local-only HTML work log generated from editable Markdown documents. The intended single entry point is `report/index.html`, opened locally; the generator and output do not exist yet. No publishing, hosting account, public URL, or external service is required to read the generated report.

Use the existing Markdown documentation as source material: this specification for scope, [progress](progress.md) for current status and dated decisions/evidence, [pilot tasks](pilot_tasks.md) for pilot context, and selected student-authored material from the [learning journal](learning_journal.md). Add benchmark-review and experiment-result Markdown records when that evidence exists. Markdown remains authoritative; regenerate HTML instead of editing it by hand.

The entry point must provide navigation to:

- Current goal, scope, implementation status, blockers, and next milestone.
- Dated progress, decisions, changes of plan, and evidence provenance.
- Benchmark version, category counts, independent review record, evaluation results, and baseline/revised comparison with limitations.
- Local saved run artifacts and MLflow run identifiers/links, plus GitHub Actions evidence links when available. Local summaries must remain readable when external links or the MLflow UI are unavailable.
- Reproduction/demo instructions and student-authored learning reflections where selected for inclusion.

Generate static HTML with local assets and relative internal links, show the build date, and label missing evidence as pending rather than inventing results or URLs. Render candidate code as escaped text; never execute generated code while building or viewing the report. Define a documented build command, check source/internal links, and verify opening the entry point locally. Generated output, raw run bundles, and private reflection material must not be published automatically.

Update the editable progress and result records after each meaningful milestone or run, and regenerate the report once its generator exists. Preserve dated historical decisions with explicit supersession notes. Personal expectations and reflections belong to the student; leave unanswered journal prompts unanswered.

## Four-week delivery plan

Weeks are relative to this 2026-10-16 scope review; the exact deadline remains to be confirmed.

| Window | Priority | Exit evidence |
| --- | --- | --- |
| Week 1 | Make the laptop loop work and explain its behavior: restore the image, review isolation, connect generation, and save/replay local results on the pilot | Passing offline/container checks; a real OpenRouter pilot smoke run; complete local request/response/result bundle; offline replay; student explanation of one pass and one failure. No CI or MLflow dependency |
| Week 2 | After the local milestone passes, freeze the independently reviewed minimum benchmark, integrate GitHub Actions and MLflow, and build the first HTML report | Reviewed 10-task benchmark; deterministic CI evidence; the existing local bundle logged to MLflow without regeneration; locally readable report |
| Week 3 | Complete the baseline, inspect failures, revise one prompt, and complete the comparison run | Two complete comparable runs in MLflow and local storage; documented gains, regressions, and decision |
| Week 4 | Resolve failures, finish report, verify replay, and rehearse the demo | Fresh setup/replay instructions checked; report evidence links checked; runnable demo with retained-run fallback |

Keep the report current throughout. If time slips, defer expansion toward 30 tasks, repetitions, automatic live CI, model comparisons, Deepchecks, and DVC before cutting required workflow evidence. Never trade away independent benchmark validation or the execution-boundary review for additional features.

## Completion checklist

- [ ] Local generation/evaluation/persistence/replay milestone passed and explained before CI and MLflow integration.
- [ ] Versioned repository with reproducible setup and reviewed dependency/container versions.
- [ ] Frozen benchmark meeting the 10-task minimum, with independent expected-answer evidence.
- [ ] Evaluator fixtures and isolation probes pass in the environments used; limitations are documented.
- [ ] Deterministic GitHub Actions checks and retained run evidence are available.
- [ ] Baseline and one revised-prompt live run through OpenRouter are complete, retained locally, and tracked in MLflow.
- [ ] Comparison records gains, regressions, unchanged outcomes, variation/generalization limits, and a reasoned decision.
- [ ] Continuously maintained Markdown report sources generate a local HTML work log with a single verified entry point.
- [ ] Runnable final demo supports evaluation replay, MLflow/evidence inspection, and report navigation.

## Decisions still needed

- Confirm the exact final-demo date within the roughly four-week window.
- Choose the OpenRouter model/provider configuration, generation settings, API budget, and bounded retry limits before live work.
- Select the GitHub repository location and compatible CI runner; document its actual isolation evidence.
- Review and resolve the worker protocol's scoring-integrity risks and choose final resource limits before executing live candidates.
- Freeze the actual tasks, independent review record, and selected benchmark size; ten is the planning minimum.
- Choose durable local run/MLflow storage paths, artifact retention/exclusions, and the report build implementation.

These are bounded implementation decisions. There is no outstanding rubric, hosting, production deployment, or mandatory 30-task requirement.
