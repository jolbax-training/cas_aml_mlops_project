# Agent evaluation and MLOps with Python code generation

The goal is to understand transferable agent-evaluation methods and demonstrate a reproducible MLOps workflow in **four eight-hour working days (32 hours)**. The target is a bounded function-writing agent with its own development checks, hidden final grading, durable traces/results, and offline grading replay. Required deliverables include deterministic CI, local MLflow in Podman, an offline HTML work-log, an evaluation-design guide with a research-orchestrator example, and a runnable demo. [The specification](docs/project_spec.md) defines the agreed scope and acceptance criteria.

The current implementation is still an offline pilot: it loads three tasks and twelve cases, validates Python source, executes one case at a time in a restricted Podman container, and scores returned values outside that container. The agent loop, OpenRouter client, bundles/replay, expanded benchmark, CI, MLflow, and HTML builder are planned. Local orchestration will run on the laptop with uv; MLflow and disposable candidate execution use Podman. Complete the local loop before CI/tracking integration.

## Setup

Use Python 3.12 and a running Podman VM:

```sh
uv sync --python 3.12
podman pull docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5
```

The image digest is pinned in `src/codegen_eval/sandbox.py`. This image was checked on macOS with a local Podman VM; other platforms need their own isolation check.

## Verify the offline evaluator

Run the dataset, contract, and scoring checks without Podman:

```sh
.venv/bin/pytest -q
```

Run the separate container integration checks after Podman is available:

```sh
CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox
```

The integration checks exercise correct and wrong functions, input mutation, a timeout, excessive output, and attempted access to a host file, a synthetic host environment variable, a read-only system path, and the network. They do not use real credentials.

As an optional learning exercise (not a delivery gate), inspect one expected failure in `tests/test_evaluate.py` before running it. Predict its task score, case score, and failure label. Then compare your prediction with the test result. Useful questions: Why does a syntax error produce four unexecuted cases? Why does a correct return value still fail after input mutation? What does the container protect, and what remains uncertain?

## Pilot data and scoring boundary

- `data/pilot_tasks.json` contains three tasks and 12 cases. Only each task's instruction and signature are intended for the generator.
- `src/codegen_eval/tasks.py` validates dataset shape and category counts.
- `src/codegen_eval/contract.py` checks Python syntax and the one-function response contract without running code.
- `src/codegen_eval/sandbox.py` passes source and one case's arguments to a disposable container. It never passes expected answers, repository files, or credentials.
- `src/codegen_eval/evaluate.py` compares the returned value and post-call arguments with trusted expectations outside the container, preserving each case's failure labels.

The container restrictions and integration checks limit accidental or hostile code behavior. They are not a formal proof against a candidate deliberately manipulating the worker protocol inside its own Python process. The live model benchmark remains disabled until this execution boundary is reviewed against the project's execution and scoring-integrity requirements.

## Plan and report sources

- [Working specification](docs/project_spec.md): scope, local-first milestones, completion evidence, and unresolved implementation decisions.
- [Progress and decisions](docs/progress.md): current status, dated evidence, and next steps.
- [Pilot benchmark](docs/pilot_tasks.md): the existing three-task dataset. The frozen target is ten reviewed tasks across five categories, with forty hidden checks; each prompt variant has three trials per task.
- [Personal learning journal](docs/learning_journal.md): student-authored expectations and reflections, preserved as report source material.
- [Historical brainstorming](docs/project_ideas.md): earlier ideas, superseded by the working specification where they differ.

## Agreed target configuration (not implemented yet)

- Four logical model calls and three development-tool attempts per trial; at most four checks per tool request. The fourth model call is final-submission-only.
- Fresh restricted candidate containers per check; target execution deadline **10 seconds**. The current code still defaults to eight seconds and requires scoring-integrity review before live comparisons.
- OpenRouter `z-ai/glm-5.3-flash`, pinned to OpenInference `open-inference/fp4`; temperature 0.2, top-p 1, low reasoning effort, 12k input / 2k output tokens, 60-second API attempts. Functional smoke verification is pending.
- Baseline and one revised prompt, three trials per task: sixty task trials and 240 hidden-check outcomes overall.
- Project-wide spending ledger: **CHF 10 checkpoint**, automatic continuation; **CHF 15 ceiling**, with conservative reservations including retries and uncertain charges.
- Trace inspection needs no execution service; grading replay re-executes saved final code in Podman without a model API. Deterministic response fixtures verify the agent loop separately.

The planned report entry point is `report/index.html`, generated locally from selected Markdown and reviewed summaries. The generator/output do not exist yet. The first foundation is scheduled on day two; it will collect architecture, status, decisions, benchmark review, comparison, evidence references, and reproduction instructions without hosting. Build/open commands will be documented after implementation.

OpenSpec is initialized under `openspec/`, with Codex workflow skills in `.agents/skills/`. The existing [local HTML work-log change](openspec/changes/add-local-html-work-log/proposal.md) has revised planning artifacts and no implemented tasks; main capability specs remain empty. The [Wayfinder map](.scratch/revise-project-spec/map.md) retains the user-confirmed decisions, and [glossary](GLOSSARY.md) defines evaluation terminology. A GitHub origin is configured; no Actions workflow exists yet.
