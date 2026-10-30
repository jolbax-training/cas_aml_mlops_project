# Project progress and decisions

Updated 2026-10-30. [The specification](project_spec.md) defines the current acceptance plan. [The Wayfinder map](../.scratch/revise-project-spec/map.md) retains Q1–Q42 and their resolutions; personal reflections remain in the [learning journal](learning_journal.md).

## Current status

**Planning is consolidated; implementation remains the offline pilot.** The target is a bounded tool-using coding agent plus reproducible evaluation/MLOps evidence within 32 working hours. Start with the execution boundary, agent fixtures, local bundles, and grading replay; add the live smoke path and HTML foundation on day two, CI/MLflow/comparison on day three, then finish evidence, transfer design, and the demo. Personal explanations are encouraged and do not block delivery.

| Area | Observed state / provenance | Required next evidence |
| --- | --- | --- |
| Benchmark | Three tasks, twelve cases; re-counted during this review | Ten reviewed tasks, references/review records, forty checks; freeze before baseline |
| Evaluator | Dataset/source validation, per-check Podman execution, external scoring implemented | Agent loop, development tool, durable bundles, distinct inspection/regrading commands |
| Offline checks | Earlier in this conversation: `.venv/bin/pytest -q` gave 21 passed, eight skipped | New implementation checks and retained deterministic CI evidence |
| Podman | 2026-10-30: CLI 6.1.4, running libkrun VM, pinned image present; 8/8 baseline and 33/33 current sandbox tests passed (see entry below) | Re-run the probes on any other environment (Linux/CI) before trusting results there |
| Execution boundary | 2026-10-30: ten-second configurable limits, supervisor/executor split, 33 Podman probes/tests passing on the local macOS VM; [threat model](threat_model.md) records residual limitations | Probe run on each further environment (CI) before it is trusted; live comparison still needs its other prerequisites |
| Version control / CI | `origin` points to the project's GitHub repository; no Actions workflow | Required deterministic and Podman check groups on a verified compatible Linux runner |
| OpenSpec | One planned HTML change, revised to the smaller scope; main specs empty | Implement the revised tasks separately; planning completion is not implementation completion |
| Live generation / tracking | No OpenRouter client, budget ledger, agent traces, or MLflow integration | GLM/provider smoke; shared CHF controls; local bundles; containerized MLflow |
| Report / demo | HTML builder and architecture figure implemented 2026-10-30 (see entry below); evidence sections pending; no complete demo | Day-four evidence updates, browser layout inspection, offline/replay demo checks |
| Transfer design | Coordinator/worker/verifier/final-check scope agreed | Guide and six-scenario example drafted (design only, not executed); registered as work-log sources 2026-10-30 |

Runtime observations above are from the earlier read-only exploration in this conversation, not new live/container tests during this documentation update. Historical eight-test failures were recorded in October 16 planning; they have not been rerun or treated as a new result. No CI success, live experiment, MLflow run, generated report, or completed personal reflection is claimed.

## 2026-10-30 — Bounded agent loop with recorded-response fixtures (`add-bounded-agent-loop`)

- **Decisions recorded (task 2.0):** On 2026-10-30 the user accepted the proposed defaults in the change's design.md: (1) pre-send input-limit rejection ends the trial, consumes the rejected call, and is `no_submission` labelled `request_rejected`, a candidate-side outcome counted in planned denominators; (2) submission is a plain final assistant message, so a non-source message is a contract failure; (3) a response with several tool calls, or content plus a tool call, counts as one attempted tool call, only the first `run_checks` call runs, extras get argument-error feedback, and content beside a tool call is not a submission.
- **Implemented:** `model_client.py` (interface, normalised response/failure types, `FixtureClient`), `agent_config.py` (`AgentLimits` 4/3/4 with hash, versioned prompt `baseline_agent_v1.md`), `run_checks.py` (validation, per-check `execute_check`, strict comparison reused from `evaluate.py`, bounded feedback), `trial.py` (controller, drafts, trace, terminal states). `sandbox.py`, `evaluate.py`, and `contract.py` are unchanged; `_strict_equal` is imported from `evaluate.py` as is.
- **Fixture coverage:** `tests/fixtures/agent/trials.json` holds 17 recorded scenarios; `tests/test_agent_trial.py` covers early submission, tool use and revision, malformed arguments and recovery, oversized batch, fourth-call submission with tools disabled, tool request on call 4, empty final message, input-limit rejection, multiple tool calls, content plus tool call, fenced/prose/disallowed-construct finals, candidate exception, invalid tool source, container and protocol failure, configurable limits, and that hidden case data never reaches the model, tool schema, or trace. One test also runs a fixture trial through real Podman.
- **Observed (Python 3.12, Podman as in the entry below, no network or credentials needed for the fixtures):** `.venv/bin/pytest -q` gave 170 passed, 55 skipped; `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` gave 55 passed, 170 deselected (about 61 s) on the final run; no leftover `codegen-eval-*` containers.
- **Known flake (pre-existing):** `tests/test_isolation_probes.py::test_timeout_includes_container_startup_and_cleanup_is_separate` failed intermittently (a `codegen-eval-*` container still listed right after a 0.05 s timeout). It also failed and passed on an unmodified export of the base commit (1 of 3 runs failed there), so it is not caused by this change; it needs its own investigation.
- **Limits of this evidence:** The fixtures verify controller behaviour, not live model quality. There is no live client, cost ledger, transport retry, or MLflow trace mapping. Fixture trials use an in-process stand-in runner except the one Podman test.
- **Glossary:** The coordinator approved the infrastructure-incomplete-trial entry (design.md wording) on 2026-10-30; it is now in GLOSSARY.md.
- **Review follow-up (Fable review, same day):** a non-rejection `ModelFailure` (for example `transport_exhausted`) now ends the trial as `infrastructure_incomplete` with the trace kept instead of raising; truncation, usage, and failure detail are recorded in the trace; infrastructure-stopped drafts report `ok: false`; raw tool arguments over the payload limit are rejected before parsing; a blank final message is a contract failure (only a null message is `no_submission`, label `no_final_message`); wire translation is documented as the client's job.
- **Timeout-cleanup probe root cause:** with a 0.05 s deadline the Podman client is killed before the server has created the container; in the VM, creation can take several seconds, the container is then created, runs to completion, and stays (no `--rm`). The previous cleanup made three `rm` passes about two seconds in total, so a late container was listed afterwards (it flaked on an unmodified export of the base commit). `_remove_container` now retries up to eight passes and stops as soon as a pass removes something; the probe's assertion is unchanged. Cost: a sub-startup deadline now spends up to about eight seconds in cleanup, outside the deadline.

## 2026-10-30 — Candidate execution hardening (`harden-candidate-execution`)

**Environment (observed):** macOS 27.0 arm64 host; Podman CLI/server 6.1.4, libkrun VM `podman-machine-default` (7 CPUs, 3.7 GiB), VM kernel 7.2.5-200.fc44.aarch64; Python 3.12.12 via uv; image `docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5` (present locally, shown with `podman images --digests`). No paid API calls, credentials, GitHub push, or CI were used.

**Baseline before changes** (original pilot code): `.venv/bin/pytest -q` gave 21 passed, 8 skipped; `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` gave 8 passed (10.3 s).

**Demonstrated scoring bypass in the pilot** (scratch scripts, not committed; unique_in_order case `lists_01_a`): (1) a candidate that mutates its input, then writes a forged `{"status":"returned",...,"args_after":<original>}` to stdout and calls `os._exit(0)` was returned as `status=returned` with clean arguments; (2) a candidate that mutates its input and replaces `json.dumps` to substitute the original arguments was also returned with clean arguments. Both would have passed trusted scoring with no `mutated_input` failure. This blocked live comparison until fixed.

**Fix:** supervisor (PID 1, non-dumpable) plus separate executor with a per-check token, private report pipe, and pre-bound exact-type serialiser; rationale and limitations in the [threat model](threat_model.md). After the fix the same two candidates give `protocol_violation` and `returned` with `args_after=[[3,1,3,2,1,99]]` (recorded as `mutated_input`).

**Results after changes (same environment):**
- `.venv/bin/pytest -q`: 35 passed, 33 skipped.
- `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`: 33 passed, 35 deselected, about 60 s (32 passed in three consecutive runs before the cgroup probe was added; 33 passed in the final run), no failures and no leftover `codegen-eval-*` containers. An earlier run during development had one failure in the deadline/cleanup probe (container created after the client was killed); cleanup was changed to retry and the probe passed in all later runs.
- Measured per-check wall time for a trivial call: 0.66–0.82 s (five runs), so startup uses well under 10 % of the deadline here.
- No unresolved bypass is known in this environment. Deliberate introspection of the executor can still sign a false report, but under net-state mutation semantics that yields nothing unreachable honestly (accepted residual; see the threat model). Other environments (Linux/CI) have not been run.

**Review follow-up (same day, same environment):** an independent security review demonstrated two introspection-free ways to force an `infrastructure_error` (a candidate sending SIGINT to PID 1; a 30 000-deep return value crashing the supervisor's JSON parse) and two introspection-based ones (forged NaN and number-expanding reports). All four now end as candidate outcomes and each has a probe in `tests/test_isolation_probes.py`, plus probes for print overflow followed by an exception and an explicit trivial-correct-candidate self-test. Observed afterwards (before the rebase onto main, so without the 58 work-log tests): 35 passed, 51 skipped; sandbox 51 passed (see the re-review entry below for the current counts); `openspec validate harden-candidate-execution --strict` valid. The introspection-forged-report residual is accepted under net-state mutation semantics (see the threat model and delta spec).

**Re-review follow-up (2026-10-30, same environment):** a second independent review found that a candidate forking about 28 processes of 4.5 MB each makes the memory-cgroup OOM killer pick the PID 1 supervisor (container exit 137), which was recorded as `infrastructure_error`; resetting `oom_score_adj` to 0 from inside the candidate also defeats an executor-side adjustment. Fix: the host reads `State.OOMKilled` (container kept until inspected, then removed explicitly) and records an OOM-killed non-zero exit as `candidate_crash`; the executor also sets `oom_score_adj=1000` as defence in depth. Probes for both variants, a lone-surrogate probe, and unit tests for the cleanup edge cases (`_reap`) were added; the lone-surrogate persistence hazard is noted in the threat model. Observed at this commit on the rebased branch: `.venv/bin/pytest -q` 96 passed, 54 skipped; `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` 54 passed, 96 deselected (about 58 s); no leftover `codegen-eval-*` containers. The earlier count of 35 passed was measured before the rebase onto main and is superseded. No unresolved bypass is known in this environment.

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

## 2026-10-30 — Transfer guide and research-coordinator example drafted

- **Delivered:** [Evaluation design guide](evaluation_design_guide.md) and [research coordinator example](research_coordinator_example.md) (design only; six scenarios).
- **Status:** The orchestrator was not built or executed, no independent verification occurred, and no judge is calibrated. All traces are labelled illustrative and all graders/rubrics proposed. The OpenRouter research appears only as a provenance-labelled evidence fixture.
- **Pending:** The student's own review/reflection. (Work-log registration is recorded in the 2026-10-30 HTML work-log entry.)
- **Evidence:** The two documents and `openspec validate add-evaluation-design-guide --strict` (passed on 2026-10-30); documentation only, no code or runtime change.

## 2026-10-30 — Local HTML work-log foundation

- **Purpose:** Day-two foundation of the OpenSpec change `add-local-html-work-log`.
- **Implemented:** `scripts/build_work_log.py` (build and `--check`), the explicit source list `docs/work_log.toml`, a reviewed architecture SVG with a text equivalent, and `tests/test_work_log.py`. Commands are in the [README](../README.md).
- **Observed:** The builder reproduces byte-identical output for a fixed build time, passes `--check` on this repository, and the generated report is Git-ignored. Evidence (Python 3.12.12, markdown-it-py 4.2.0, after rebasing onto `main`): `.venv/bin/pytest -q` gave 79 passed, 8 skipped (the sandbox group); `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` gave 8 passed; `openspec validate add-local-html-work-log --strict` passed; `.venv/bin/python scripts/build_work_log.py` and `--check` succeeded with 8 sources and 4 pending sections.
- **Registered:** The [evaluation design guide](evaluation_design_guide.md) and [research coordinator example](research_coordinator_example.md) are now work-log sources (design only; the example is labelled planned).
- **Pending and not claimed:** Results, reviewed benchmark, CI/MLflow identifiers, and demo sections render as pending; no experiment, CI run, MLflow run, or reflection exists for them. Desktop, 375-pixel, and 200-percent-zoom inspection in a real browser is not yet recorded (a headless Chrome screenshot at desktop width was viewed only to fix diagram text overflow).

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
