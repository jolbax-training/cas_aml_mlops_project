# MLOps workflow with Python code generation

The goal is to demonstrate a complete MLOps workflow in a self-directed, course-related project over roughly four weeks. The Python function generator provides the evaluation use case. Final deliverables are a repository, a continuously updated local HTML report, and a runnable demo. Start by making the complete generation/evaluation loop work on the laptop with Podman; integrate GitHub Actions and MLflow after that local milestone passes.

The current implementation is an offline pilot: it loads three benchmark tasks, validates generated Python source, executes one case at a time in a restricted Podman container, and scores returned values outside that container. It does not call OpenRouter or MLflow yet.

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

For the learning journal, inspect one expected failure in `tests/test_evaluate.py` before running it. Predict its task score, case score, and failure label. Then compare your prediction with the test result. Useful questions: Why does a syntax error produce four unexecuted cases? Why does a correct return value still fail after input mutation? What does the container protect, and what remains uncertain?

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
- [Pilot benchmark](docs/pilot_tasks.md): the existing three-task dataset. The planned independently reviewed minimum is 10 tasks across five categories; 30 is a stretch target.
- [Personal learning journal](docs/learning_journal.md): student-authored expectations and reflections, preserved as report source material.
- [Historical brainstorming](docs/project_ideas.md): earlier ideas, superseded by the working specification where they differ.

The planned report entry point is `report/index.html`, generated locally from editable Markdown. The generator and HTML output are not implemented yet. The report will collect status, dated decisions, benchmark review and results, and links to CI/MLflow evidence without requiring hosting.

OpenSpec is initialized under `openspec/`, with Codex workflow skills in `.agents/skills/`. Its configuration records the scope constraints; the working specification is the authoritative project plan. No OpenSpec changes or capability specs have been authored yet.
