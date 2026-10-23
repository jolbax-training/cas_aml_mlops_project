# Agent evaluation and MLOps project specification

Updated 2026-10-23 after the user-confirmed Wayfinder review (Q1–Q42). This is the authoritative scope and acceptance plan. [Progress](progress.md) records actual evidence; the [decision map](../.scratch/revise-project-spec/map.md) links the reasoning and confirmations. [Glossary](../GLOSSARY.md) defines task, trial, check, run, inspection, and grading replay.

## Purpose and constraints

The project has two goals:

1. Understand how to design, validate, inspect, and use agent evaluations, with a method transferable to other projects.
2. Demonstrate a complete reproducible MLOps workflow: version tasks/configuration, validate the evaluation harness, retain traces and outcomes, automate deterministic checks, track experiments, and make a reasoned comparison.

The concrete implemented system is a bounded Python-function-writing agent with a development-check tool. A second, design-only example transfers the method to a research-workflow orchestrator.

There are **four working days at eight hours per day: 32 hours total**, relative to implementation start. This replaces the October 16 four-week plan. There is no formal assignment rubric. Explanations and personal reflections support learning but do not block delivery; never invent the student's reflections.

Required deliverables are the versioned repository, runnable local agent/evaluator and grading replay, retained comparison evidence, deterministic CI, containerized local MLflow with agent traces, a continuously updated local HTML work-log, a reusable evaluation-design guide with the orchestrator example, and a rehearsed demo. Measured improvement is not required.

## Current implementation versus target

The current code is an offline pilot with three tasks and twelve cases. It validates task data and Python source, runs each case in a restricted Podman container, and scores outside that container. Python 3.12, uv, pytest, and a pinned Python image are already used.

The agent loop, OpenRouter client, spending ledger, durable run bundles, grading-replay commands, expanded/reviewed benchmark, MLflow integration, GitHub Actions, and HTML generator are **planned**. Revising this specification does not implement them. The current sandbox defaults to eight seconds; the target below is ten seconds. The shared-process worker's scoring integrity remains unverified. See progress for dated checks rather than assuming current environment readiness.

## System and local-first sequence

```text
Instruction + typed signature + versioned agent prompt
                         |
                         v
Trusted host CLI <--> OpenRouter model
     |                   |
     |      candidate + agent-authored examples
     v
Development-check controller --> fresh Podman container per check
     ^                              |
     +--------- bounded feedback ---+
                         |
                   final submission
                         |
              source-contract validation
                         |
Hidden acceptance inputs --> fresh Podman container per check
                                      |
                           external trusted scoring
                                      |
                   durable local bundle + comparison
                         |                       |
                 local MLflow              reviewed Markdown
                 (Podman)                         |
                                          report/index.html
```

Only instruction/signature and the versioned prompt enter the initial model request. The model subsequently sees its own outputs and development feedback. Hidden acceptance inputs, expected answers, labels, and grading feedback never enter the agent's conversation. Final comparison and expected answers stay outside candidate execution. Model credentials and container-control interfaces belong only to trusted orchestration.

Run the trusted CLI on the laptop in its uv environment. It launches disposable candidate containers. MLflow is a separate persistent Podman service with durable local storage and a localhost endpoint. No candidate can access tracking or container-control credentials. The model remains an external API; local-first describes orchestration, execution, persistence, and inspection.

First establish the local fixture/evaluation/persistence/regrading path, then the bounded live tool interaction and budget controls. Add CI and MLflow after that local milestone works. Build the small HTML foundation on day two and keep it current; it is not a prerequisite for execution. Personal explanations are encouraged throughout without becoming a milestone gate.

## Coding agent and trial contract

A coding task requests one function through a natural-language instruction and typed Python signature. A **trial** is one fresh conversation attempting that task, including development checks and revisions. Internal revisions are not new trials. Trials receive no earlier-trial results.

The agent has one optional tool, `run_checks`, accepting candidate source and structured example arguments/expected outputs authored by the agent. Checks are data, not arbitrary Python test programs. The trusted controller validates requests, executes each check separately, and returns per-check pass/fail, actual values, and bounded syntax/runtime diagnostics. Development expectations remain outside candidate execution. The agent may submit without tool use.

| Interaction limit | Required behavior |
| --- | --- |
| Model calls | At most four logical calls per trial; early submission allowed |
| Development-tool attempts | At most three per trial, including malformed requests |
| Checks per development-tool request | At most four; at most twelve executed development checks per trial |
| Fourth model call | Reserved for final submission, with tools disabled |
| Missing final submission | Record `no_submission`; preserve drafts and trace |
| Agent-code/tool-argument error | Consume the attempted tool call and return bounded recovery feedback |
| Final submission | Grade as returned; no repair or quality-based regeneration |

The final artifact is raw Python source with optional standard-library imports and exactly one synchronous function matching the requested name, arguments, and annotations. Markdown fences, prose, helper/nested functions, lambdas, classes, decorators, async functions, third-party/relative imports, and top-level executable statements are disallowed under the existing contract. Do not strip fences or otherwise repair responses. Final syntax and contract failures are candidate failures.

## Execution and scoring integrity

Treat candidate code as untrusted in a controlled course-project environment. Production security certification is outside scope, but demonstrated scoring bypasses must be resolved before live comparisons are trusted. Host isolation does not establish trustworthy worker reporting: the pilot executes candidate code and its reporting logic in one Python process.

Use the same restricted mechanism for development and acceptance checks, with a fresh disposable container for **every individual check**. Pass only source, function name, and that check's arguments. Expected answers, scoring, repository files, API credentials, tracking, and the Podman control socket remain outside. Disable network access; use a read-only root filesystem, unprivileged user, dropped capabilities, and restricted temporary writes.

| Execution resource | Target limit |
| --- | ---: |
| Wall-time deadline per check, including container startup/code loading | 10 seconds |
| Memory | 128 MiB |
| CPU allocation | 1 CPU |
| Processes | 32 |
| Writable temporary storage | 16 MiB |
| Source-and-arguments payload | 64 KiB |
| Captured print output | 32 KiB |
| Worker protocol output | 64 KiB |

Cleanup is handled separately from the execution deadline. Limits are configurable, tested in each execution environment, and fixed across compared variants. Oversized tool requests return argument-error feedback and consume an attempt; they do not execute excess checks.

Required probes cover host files, host environment, network, read-only paths, timeout, excessive output, and input mutation. Add targeted forged-worker-response and concealed-mutation probes, document the threat model and residual limitations, and resolve demonstrated bypasses before live comparison. Exact worker hardening is implementation work; passing ordinary correctness tests alone is insufficient exit evidence.

## Benchmark, graders, and evaluator validation

Freeze **ten independently reviewed tasks** before baseline: two each in strings, lists, dictionaries, numeric logic, and parsing/formatting. Each has two ordinary and two edge acceptance checks: forty checks and twenty edge cases for one trial of every task. Review the existing pilot again before inclusion.

Every task needs an unambiguous instruction/signature, a separately reasoned reference solution, and reviewed expected answers. Retain reviewer, date, derivation/reference, corrections, task/case IDs, and benchmark version/hash. An extra unreviewed model answer is not independent validation. Validate unique IDs, category distribution, argument/schema shape, and case counts. Version benchmark content and review evidence with each run; changing a frozen benchmark requires a new version and comparable reruns.

Use JSON-compatible strings, integers, booleans, lists, string-keyed dictionaries, and null only where a task requires it. Compare recursively with strict types; preserve list order and ignore dictionary key order. Inputs must remain unchanged. Invalid input types, floating-point tolerance, and expected-exception tasks are outside this benchmark.

A trial passes only if its final source satisfies the contract and all four hidden checks pass without mutation. Retain individual check results and multiple failure labels when applicable. Use deterministic graders and human inspection of selected traces. An implemented LLM judge is not required. Optional tool use or a particular tool-call sequence is not a success criterion.

Validate the harness with fixtures for correct candidates, ordinary/edge failures, syntax/signature/other contract errors, exceptions, mutation, timeouts, and excessive output. Interaction fixtures also exercise malformed tool arguments, recovery, optional tool use, fourth-call submission, missing submission, exhausted retries, spending limits, and infrastructure classification. These validate the evaluator and controller rather than measuring live model quality.

### Accounting and completion

| Outcome | Accounting |
| --- | --- |
| Wrong answer, mutation, candidate exception, timeout, excessive output | Candidate failure counted against planned scores |
| Final syntax/contract error or no submission | All four hidden checks unsuccessful and unexecuted |
| Interrupted by execution deadline | Unsuccessful and attempted |
| Container unavailable, broken worker protocol, exhausted API transport retries | Run incomplete; retain partial evidence |

Keep full planned denominators. Candidate failures can belong to a complete run when fully recorded. An infrastructure-incomplete run is excluded from headline comparisons; do not lower denominators. Verify every expected task/trial ID and required record, not merely aggregate totals. Report counts alongside rates.

## Experiment and model configuration

Compare one baseline agent prompt with **one revised prompt**, motivated by inspection of baseline traces/failures. Hold all other settings fixed. If the baseline has no failures, state that and motivate the revision from available trace/efficiency evidence; do not invent failures. Improvement is not a completion gate.

Run three independent trials per task per variant:

| Denominator | Per variant | Both variants |
| --- | ---: | ---: |
| Task trials | 30 | 60 |
| Hidden check outcomes | 120 | 240 |
| Edge-case outcomes | 60 | 120 |

Primary score: successful task trials / planned task trials. Diagnostics include task/category counts, tasks passing at least once and all three trials, check/edge-case rates, failure labels, tool calls, revisions, observed recovery, end-to-end latency, token usage, and reported/estimated cost. Use selected traces to explain gains, regressions, unchanged outcomes, and the keep/reject decision. Three repetitions do not establish precise reliability. Tuning against these tasks does not demonstrate generalization to unseen work.

| Model/request setting | Agreed value |
| --- | --- |
| API model | `z-ai/glm-5.3-flash` through OpenRouter |
| Provider endpoint | OpenInference `open-inference/fp4`, pinned with fallbacks disabled and required parameter support |
| Input limit | 12,000 tokens for the whole rendered request, including history/tool definitions |
| Output limit | 2,000 tokens per call, accounting for provider reasoning/output semantics |
| Temperature / top-p | 0.2 / 1 |
| Reasoning effort | Explicit `low` |
| API deadline | 60 seconds per physical attempt |

The [retained primary-source research](https://github.com/jolbax-training/cas_aml_mlops_project/blob/44d1fff8e7d5c947c56c50e4fec355f47991f08a/docs/research/openrouter-model-choice.md) verifies documented temperature/tool controls and provider differences. Its proposed settings were subsequently confirmed here. It is a dated research snapshot, not a live smoke result or permanent pricing guarantee. Temperature is configurable; GLM reasoning is mandatory and defaults to max when not explicitly controlled.

Before freezing, recheck endpoint capabilities/prices and retain a real tool-call/feedback/final-submission smoke trace, including final-only tool disabling, sampling parameter acceptance, usage/provider metadata, and room for code within the 2k reasoning/output allowance. Reject oversized requests before sending, using verified token accounting or a verified conservative bound. Preserve truncated responses as returned. Do not resample until a benchmark answer passes. Document any pre-freeze adjustment; model/provider/evaluator/benchmark changes after baseline require comparable reruns or rescoring as appropriate.

Record the requested model, available canonical identifier, actual provider/endpoint/precision metadata, settings, and dates. Fixed identifiers and routing do not guarantee immutable upstream weights; disclose changes and missing metadata. Freeze dependency/evaluator/image versions as well as prompt and benchmark versions.

### Transport retries and spending

Allow one retry per failed request and at most two transport retries per trial, outside the four logical model-call allowance. Use bounded backoff for transient/retryable API failures; record every physical attempt and disable unaccounted SDK retries. Refusals, malformed responses, source errors, failed checks, truncation, and poor answers do not trigger transport retries. Exhausted transport retries make the run incomplete.

The main comparison permits at most 240 logical calls plus 120 retries: 360 physical attempts. Development and smoke calls are additional but share the same budget. A timed-out or disconnected request may still be charged.

Use one durable project-wide ledger for all paid attempts. Reserve a conservative maximum cost before sending, based on verified endpoint prices, enforced token caps, a dated CHF conversion, applicable fees, and a safety margin. Keep uncertain-charge reservations until reconciled. Record reported costs separately from estimates/reservations; do not assume missing usage is free.

**CHF 10 is a checkpoint that records progress and continues automatically. CHF 15 is the ceiling:** do not send a request whose reservation would exceed it. Preserve the bundle and mark unfinished work incomplete when budget prevents completion. Smoke/development work has no separate entitlement outside the ceiling. Verify projected total cost before starting the main runs.

## Evidence, MLflow, CI, and replay

A durable local bundle is the primary evidence and is saved before MLflow recording. Retain run/trial IDs and timestamps; completion status; benchmark/review content and hashes; prompt versions/rendered requests; raw responses and candidate history; tool arguments/results; final source; per-check grades/failures; metrics; model/provider settings; retries/errors/usage/cost reservations; evaluator revision; Python/dependency versions; and container image digest. Keep credentials, authorization headers, and secret environment data out of artifacts and reports.

Record both required runs completely in local MLflow: parameters, metrics, artifacts, and traces of the agent/model/tool interactions, linked to grading evidence and local bundle identity. Persist MLflow data outside ephemeral service containers. A tracking outage must not lose results or cause new paid generation; support later recording of the same bundle.

Provide and document three distinct capabilities:

- **Trace inspection:** read retained interactions/results without APIs or Podman.
- **Grading replay:** execute saved final candidates against the retained benchmark with Podman and no model API/credentials. Keep original and replay grading evidence distinct.
- **Agent-loop verification:** deterministic recorded-response fixtures test controller/tool/stopping behavior without an API. They do not establish how a live model would respond to changed feedback.

GitHub Actions must require deterministic evaluator/benchmark/agent-loop checks and real Podman execution/isolation checks on a compatible Linux runner. Pin/document tested dependencies and images, retain CI evidence, and require no model secrets or paid generation. Candidate pass rates are experiment evidence, not CI thresholds. A GitHub origin exists; no Actions workflow is implemented yet.

Commit source, prompts, reviewed tasks, reference/review records, deterministic fixtures, dependencies, and editable report sources. Exclude secrets, local bundles, MLflow stores, and generated HTML. Exact CLI names, storage layout, supported runner image, and dependency/container versions are bounded implementation decisions, documented with tested commands before completion.

## Local HTML work-log

Generate one local `report/index.html` from explicitly selected authoritative Markdown and reviewed result summaries, using local assets and no viewing-time network/server requirement. Start with an architecture diagram showing implemented versus planned components, the agent's development loop, hidden final grading, execution trust boundaries, local bundles/regrading, CI, MLflow, comparison, and Markdown-to-report flow.

Include scope/status/milestones, dated decisions, benchmark/review evidence, results/comparison/limitations, local evidence references, MLflow identifiers/links, setup/replay/demo instructions, the transferable guide/example, and selected student-authored learning notes. Preserve dates and supersession context; unanswered personal prompts remain unanswered and non-blocking. Missing evidence is pending; no invented scores, CI URLs, or MLflow runs.

Provide one documented build command, validated internal links, legible navigation/diagram, escaped code, and explicit source selection. No candidate code runs during building/viewing. Exclude credentials, private files, raw bundles, and tracking stores from automatic inclusion; reviewed summaries link to local evidence without harvesting it. External evidence is a clickable reference, not a resource fetched on opening. Rebuild after meaningful milestones/runs; the evaluator and CLI do not depend on reporting.

The [HTML change](../openspec/changes/add-local-html-work-log/proposal.md) is revised to this smaller scope. Its earlier report-first sequence and extensive report-engine requirements are superseded by the four-day plan; the report remains required.

## Transferable evaluation-design guide and example

Deliver a reusable guide for defining success, selecting tasks/graders, validating graders, inspecting traces, interpreting variability, and deciding whether a change helps. Pair it with a design-only research-workflow example:

```text
Coordinator splits the research into items
  Item A: worker --> independent verifier
  Item B: worker --> independent verifier
  Item C: worker --> independent verifier
Final check across all items
```

Use the recent OpenRouter investigation as a concrete illustration: model controls, provider compatibility, and pricing/budget accounting. A verifier gets a fresh context with the item's requirement and worker output/citations, independently inspects supporting sources, and returns pass, needs revision, or unverifiable with evidence. It does not inherit the worker conversation or trust confidence as proof. A separate model is not required for independence. The final check assesses coverage, unresolved verification failures, and cross-item contradictions.

Specify six scenarios: normal completion, missing item, unsupported claim, conflicting item results, worker/verifier failure, and budget exhaustion. Include a case where individually passing items combine into an inconsistent answer. Each scenario needs inputs, capabilities, expected outcomes/failure handling, graders, and trace evidence. Distinguish observable checks from subjective-quality rubrics and describe validation where needed.

Existing research may supply evidence fixtures. Illustrative traces must be labelled; do not claim this orchestrator ran, that independent verification occurred, or that a proposed judge is calibrated. Building a second system is outside scope.

## Four-day delivery plan

These are eight-hour planning timeboxes, relative to implementation start, not claims of completed work.

| Day | Allocation | Exit evidence |
| --- | --- | --- |
| 1 | Boundary/probes 3h; agent/fixtures 3h; bundles/regrading 2h | Local known-candidate and fixture path; inspectable limits/failures/persistence/replay |
| 2 | Benchmark/reference review 3h; API/budget/smoke 3h; HTML foundation 2h | Reviewed ten-task benchmark; verified live tool interaction/accounting; first offline report |
| 3 | MLflow/traces 2h; CI 2h; baseline/inspection/revision/revised run 4h | Passing CI and two complete comparable runs retained locally and in MLflow |
| 4 | Comparison/report 2h; transfer guide/example 2h; setup/replay/demo 2h; buffer 2h | Finished evidence, transferable design, rehearsed demo |

Use buffer where needed and simplify presentation polish first. Required checks and run evidence remain required; unfinished work stays incomplete. Do not silently reduce benchmark/trials or waive scoring-integrity checks to claim completion. Personal reflection remains a learning opportunity rather than a delivery gate.

## Completion checklist

- [ ] Local agent/tool/contract/grading path, durable bundles, grading replay, and recorded-response fixtures work.
- [ ] Isolation, resource limits, and targeted scoring-integrity probes pass in every environment used; residual limitations are documented.
- [ ] Frozen ten-task benchmark has forty checks, reviewed answers, reference solutions, and retained review evidence.
- [ ] Selected GLM/provider controls and token/cost accounting pass a retained smoke test; shared ledger enforces checkpoint/ceiling and retry limits.
- [ ] Two complete comparable variants each contain thirty task trials, 120 check outcomes, and sixty edge-case outcomes.
- [ ] Both required runs and agent traces are retained locally and completely recorded in containerized local MLflow.
- [ ] Required deterministic and Podman CI checks pass with retained evidence and no model credentials.
- [ ] Comparison explains gains/regressions/unchanged results, failure traces, efficiency, limitations, and keep/reject decision.
- [ ] Selected Markdown generates the verified offline HTML work-log and its evidence/navigation remains readable when services are unavailable.
- [ ] Reusable evaluation-design guide and six-scenario orchestrator example are delivered with honest illustrative labels.
- [ ] Setup, inspection, grading replay, evidence/MLflow navigation, and the final demo are verified with exact tested commands.

## Exclusions and supersession

No production deployment/security certification, model training, hosted report, general shell/network/repository agent tools, second implemented orchestrator, second tracking platform, automatic paid CI, larger benchmark/model study, DVC, or Deepchecks is required. Larger suites, additional trials, and presentation enhancements are outside the 32-hour commitment.

This revision supersedes the four-week schedule, thirty-task stretch planning, single-response/no-internal-revision agent rule, one-trial-per-task experiment, reflection-as-gate wording, eight-second target deadline, earlier spending limits, report-first sequence, and Qwen model proposal. Preserve dated historical records; this specification governs where they differ. The existing pilot remains the starting implementation; the expanded agent workflow and report remain pending until evidence is recorded in progress.
