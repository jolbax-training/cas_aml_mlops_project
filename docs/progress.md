# Project progress and decisions

Updated 2026-10-23. [The specification](project_spec.md) defines the current acceptance plan. [The Wayfinder map](../.scratch/revise-project-spec/map.md) retains Q1–Q42 and their resolutions; personal reflections remain in the [learning journal](learning_journal.md).

## Current status

**Planning is consolidated; implementation remains the offline pilot.** The target is a bounded tool-using coding agent plus reproducible evaluation/MLOps evidence within 32 working hours. Start with the execution boundary, agent fixtures, local bundles, and grading replay; add the live smoke path and HTML foundation on day two, CI/MLflow/comparison on day three, then finish evidence, transfer design, and the demo. Personal explanations are encouraged and do not block delivery.

| Area | Observed state / provenance | Required next evidence |
| --- | --- | --- |
| Benchmark | Three tasks, twelve cases; re-counted during this review | Ten reviewed tasks, references/review records, forty checks; freeze before baseline |
| Evaluator | Dataset/source validation, per-check Podman execution, external scoring implemented | Agent loop, development tool, durable bundles, distinct inspection/regrading commands |
| Offline checks | Earlier in this conversation: `.venv/bin/pytest -q` gave 21 passed, eight skipped | New implementation checks and retained deterministic CI evidence |
| Podman | Earlier in this conversation: CLI 6.1.4, running VM; pinned Python image absent | Restore the pinned image and rerun probes; no successful current integration run claimed |
| Execution boundary | Current deadline eight seconds; worker and candidate share a Python process | Ten-second target; isolation plus forged-response/concealed-mutation probes and documented limitations |
| Version control / CI | `origin` points to the project's GitHub repository; no Actions workflow | Required deterministic and Podman check groups on a verified compatible Linux runner |
| OpenSpec | One planned HTML change, revised to the smaller scope; main specs empty | Implement the revised tasks separately; planning completion is not implementation completion |
| Live generation / tracking | No OpenRouter client, budget ledger, agent traces, or MLflow integration | GLM/provider smoke; shared CHF controls; local bundles; containerized MLflow |
| Report / demo | Markdown exists; no HTML builder/output or complete demo | Day-two HTML foundation, later evidence updates and offline/replay demo checks |
| Transfer design | Coordinator/worker/verifier/final-check scope agreed | Reusable guide and six worked evaluation scenarios; no second system required |

Runtime observations above are from the earlier read-only exploration in this conversation, not new live/container tests during this documentation update. Historical eight-test failures were recorded in October 16 planning; they have not been rerun or treated as a new result. No CI success, live experiment, MLflow run, generated report, or completed personal reflection is claimed.

## 2026-10-23 — Wayfinder scope and delivery revision

- **Evidence:** User confirmations Q1–Q42, retained in the [decision map](../.scratch/revise-project-spec/map.md) and its child tickets. The [specification](project_spec.md) is now authoritative.
- **Goals:** Learn transferable agent-evaluation design and demonstrate an end-to-end reproducible MLOps workflow.
- **Time:** Four eight-hour working days, replacing the earlier four-week plan. Relative day allocations and exit evidence are in the specification.
- **Agent:** Optional agent-authored development checks and internal revisions, four logical model calls, three tool attempts, four checks per request, final-only fourth call. Final source retains the existing strict function contract.
- **Execution:** Fresh restricted Podman containers for every development/acceptance check; ten-second target and mandatory isolation/scoring-integrity review before live comparison. The current worker has not been hardened by this planning revision.
- **Experiment:** Ten reviewed tasks across five categories, three trials per task for each of two prompts: sixty task trials and 240 check outcomes overall. Fixed denominators, infrastructure-incomplete runs excluded, honest keep/reject decision; improvement is not required.
- **Model:** User-selected `z-ai/glm-5.3-flash`, OpenInference `open-inference/fp4`, temperature 0.2/top-p 1/low reasoning, 12k-input/2k-output caps, 60-second API attempts. These are selected targets awaiting a functional smoke test.
- **Budget:** One ledger across all paid calls. CHF 10 checkpoint continues automatically; CHF 15 ceiling blocks over-budget reservations. One retry per failed request and at most two per trial; uncertain charges retain reservations.
- **Infrastructure/evidence:** Host CLI/uv, containerized local MLflow, durable bundles before upload, separate inspection/grading replay/interaction fixtures, and minimal deterministic CI including Podman checks.
- **Report:** Keep the smaller local HTML work-log, first foundation on day two, generated from selected Markdown/reviewed summaries. This supersedes the October 16 report-first proposal and its larger engine scope.
- **Transfer:** Design a research coordinator with one worker/fresh-context independent verifier per item and a final cross-item check. Include six scenarios and illustrative traces, never fabricated executed results.
- **Research provenance:** The Wayfinder research skill used a background agent and retained primary-source findings on throwaway branch `research/openrouter-model-choice`, commit `44d1fff8e7d5c947c56c50e4fec355f47991f08a`, [findings file](https://github.com/jolbax-training/cas_aml_mlops_project/blob/44d1fff8e7d5c947c56c50e4fec355f47991f08a/docs/research/openrouter-model-choice.md). No paid calls, PR, or research-branch merge. Research establishes documented controls and a dated price snapshot, not tested live compatibility.
- **Superseded:** Four-week schedule, larger benchmark stretch work, single-response/no-revision trials, single-trial comparisons, reflection-as-gate wording, earlier budgets/model proposals, and report-first sequencing. Earlier dated records below remain historical.
- **Changes:** Planning/documentation only; no source, test, dataset, dependency, container, workflow, or service implementation changed.

## 2026-10-23 — Planning validation

- `openspec validate add-local-html-work-log --strict`: passed.
- `openspec list --json`: the revised report change has zero of seven implementation tasks complete; its planning artifacts exist.
- `git diff --check`: passed.
- A local Python link check verified 55 local Markdown references across twenty documents, planning artifacts, glossary, and decision records. External research/source URLs were retained as references rather than fetched by this check.
- A comparison with `git show HEAD:docs/learning_journal.md` confirmed all original dated entries and reflection prompts are unchanged; only the current supersession notice was updated.
- `git diff --name-only -- src tests data pyproject.toml uv.lock` was empty. Application/container tests were not rerun for this documentation-only consolidation.

## Next implementation milestone

1. Restore the pinned image and verify the existing environment. Review/fix the execution and scoring boundary and add the required probes before live comparison.
2. Implement the bounded interaction loop and development tool with deterministic fixtures, then durable bundles and grading replay. Keep expected answers/credentials outside candidate execution.
3. Review/freeze the ten-task benchmark; implement the model interface, verified token/cost reservations, retry accounting, and retained functional smoke. Add the HTML foundation.
4. Integrate local containerized MLflow and deterministic CI, complete both comparison runs, and finish the report, transfer guide, and demo. Exact commands are documented as implemented, not invented in advance.

## Historical decisions

The following October 16 entries preserve their original context. Their four-week schedule, one-candidate-per-task experiment, reflection/understanding gate, and no-remote statements are superseded above; no dates or personal reflections have been rewritten.

## 2026-10-16 — Scope and delivery decisions

- **Context:** Self-directed course-related work, no formal assignment or rubric, roughly four weeks available. Exact demo date remains to be confirmed.
- **Goal:** Demonstrate the complete MLOps workflow using Python code generation as the evaluation use case.
- **Sequence:** The first major milestone is a working, understood laptop generation/evaluation loop using Podman and local saved results. Add GitHub Actions and MLflow only after this milestone passes. OpenRouter supplies live generation; replay and deterministic checks remain offline.
- **Benchmark:** Adopt 10 independently reviewed tasks as the planning minimum, two per category across five categories, each with four cases. Keep 30 tasks as a stretch target. Freeze the selected benchmark before the comparison.
- **Experiment:** One baseline and one revised-prompt complete run, with fixed model/settings/benchmark and one candidate per task. Record improvements, regressions, unchanged outcomes, and limits; improvement itself is not an acceptance requirement.
- **Deliverables:** Repository, continuously updated local HTML work log generated from Markdown, and a runnable final demo. No publishing or hosting requirement.
- **Report:** Planned single entry point `report/index.html`. Preserve editable sources and dated evidence; do not invent student reflections or missing run links.
- **Priority:** Reproducibility, isolated execution, independent benchmark review, CI evidence, and complete MLflow records come before larger datasets, automatic live CI, Deepchecks, or DVC.
- **Superseded:** Exactly 30 tasks as a completion gate; pending rubric/artifact questions; automatic paid CI as a required path; introducing CI/MLflow before the local breakthrough.
- **Evidence:** User scope decisions recorded in this task; [working specification](project_spec.md) and [OpenSpec configuration](../openspec/config.yaml). This entry records decisions, not personal learning claims.

## Historical 2026-10-16 next-milestone plan (superseded)

1. Restore the pinned image using the [setup instructions](../README.md) and rerun the container checks. Distinguish task-sandbox socket restrictions from actual Podman availability.
2. Review and document execution and scoring-integrity boundaries before live candidate execution.
3. Choose model/settings and a bounded API budget, then build the local request → generation → evaluation → saved-results path on the three-task pilot. Demonstrate offline replay and inspect a pass and a failure.
4. Record what each stage does and the student's interpretation of the evidence. Only then integrate CI/MLflow, expand/freeze the reviewed minimum benchmark, and build the report.

No implementation or runtime changes were made by this planning revision. Validation confirmed that local Markdown links resolve across all six Markdown documents, the documented pilot counts match the JSON dataset, and the OpenSpec YAML parses with its schema, context, and artifact rules. Application tests were not rerun for this documentation-only change. See the specification for the four-week sequence and remaining decisions.

## 2026-10-16 — Initial repository baseline

- **Action:** Establish the first local commit of source, tests, pilot data, editable documentation, dependency lockfile, and OpenSpec configuration/skills.
- **Exclusions:** Virtual environments, caches, local credentials, generated run bundles, MLflow storage, generated HTML, and machine/editor state are ignored. Curated fixtures and editable Markdown remain versioned.
- **Scope:** No remote configured or push performed. The local-first milestone and later CI/MLflow sequence remain unchanged.
- **Evidence:** The repository's initial commit and its file list; no commit hash is embedded in this entry because it is part of that commit.

## Future evidence entries

After each milestone or experiment, append the date, purpose, versions, exact commands, observed result, local artifacts and available CI/MLflow identifiers, limitations, decision, and next step. Update current status and rebuild the report once its generator exists. Label incomplete work explicitly and leave personal reflections in the student's own words.
