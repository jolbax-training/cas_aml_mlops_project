# Agent evaluation and MLOps with Python code generation

The goal is to understand transferable agent-evaluation methods and demonstrate a reproducible MLOps workflow in **four eight-hour working days (32 hours)**. The target is a bounded function-writing agent with its own development checks, hidden final grading, durable traces/results, and offline grading replay. Required deliverables include deterministic CI, local MLflow in Podman, an offline HTML work-log, an evaluation-design guide with a research-orchestrator example, and a runnable demo. [The specification](docs/project_spec.md) defines the agreed scope and acceptance criteria.

The current implementation is still an offline pilot: it loads three tasks and twelve cases, validates Python source, executes one case at a time in a restricted Podman container, and scores returned values outside that container. The agent loop, OpenRouter client, bundles/replay, expanded benchmark, CI, and MLflow are planned. The offline HTML work-log builder exists (see below). Local orchestration will run on the laptop with uv; MLflow and disposable candidate execution use Podman. Complete the local loop before CI/tracking integration.

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

The integration checks and isolation probes (`tests/test_sandbox_integration.py`, `tests/test_isolation_probes.py`) run hostile candidates through the real container path and assert the trusted-side classification: host files, a synthetic host environment variable, read-only paths, the network, capabilities and mounts, state leaking between checks, the deadline, print/report floods, memory, process and temporary-storage limits, input mutation, forged worker responses, tampering with the supervisor, and concealed mutation. They do not use real credentials. They take about a minute because every check starts a fresh container.

As an optional learning exercise (not a delivery gate), inspect one expected failure in `tests/test_evaluate.py` before running it. Predict its task score, case score, and failure label. Then compare your prediction with the test result. Useful questions: Why does a syntax error produce four unexecuted cases? Why does a correct return value still fail after input mutation? What does the container protect, and what remains uncertain?

## Bounded agent trial (API-free fixtures)

One trial is a fresh conversation (`src/codegen_eval/trial.py`) that starts from the task instruction, typed signature, and the versioned prompt `src/codegen_eval/prompts/baseline_agent_v1.md`. The agent has one optional tool, `run_checks` (`src/codegen_eval/run_checks.py`): candidate source plus up to four agent-authored checks (`arguments`, `expected`), each executed in a fresh container through `execute_check` and compared in trusted code with the pilot's strict comparison and mutation detection. Feedback is per-check pass/fail, a bounded actual value, and bounded diagnostics; hidden cases are never read.

Limits (`AgentLimits` in `agent_config.py`, hash recorded in each result): four logical model calls, three tool attempts, four checks per request. The fourth call is sent with tools disabled and must be final. The final assistant message is the submission: raw source validated by the existing contract and never repaired. Terminal states: `submitted` (a contract failure is recorded on the result), `no_submission` (labels `tool_request_when_disabled`, `no_final_message`, `request_rejected`), and `infrastructure_incomplete` (container or worker-protocol failure, or a model-client failure other than a rejection such as `transport_exhausted`). A blank final message is a contract failure; truncation and usage are recorded in the trace and never trigger a retry. A client owns translating messages to its provider's wire shape. One response counts as one tool attempt however many tool calls it holds; only the first `run_checks` call runs.

The controller talks to a `ModelClient` (`model_client.py`); `FixtureClient` replays the recorded responses in `tests/fixtures/agent/trials.json`. Run them offline, with no key or network:

```sh
.venv/bin/pytest -q tests/test_agent_trial.py tests/test_run_checks.py tests/test_model_client.py
```

These fixtures verify controller behaviour (tool handling, limits, stopping, classification). They do not measure live model quality; there is no live client yet.

## Run bundles, trace inspection, and grading replay

Every recorded run is saved as a directory under `run_bundles/` (Git-ignored) before anything else consumes it:

```
run_bundles/<run_id>/
  manifest.json          schema version, status, planned task/trial IDs, identity, record hashes
  trials/<trial_id>.json requests, raw responses, messages, tool interactions, candidate drafts,
                         final source, usage, grades, placeholders for reservations/attempts/latency
  trials/<trial_id>.calls.jsonl   each request and response, appended as it happens; replaced by
                         the record when the trial finishes, kept if the run stops mid-trial
  replays/<replay_id>.json   grading-replay evidence (separate; never overwrites the originals)
```

The manifest identity holds the prompt version and hash, benchmark version, file SHA-256 and the benchmark freeze `content_hash` (benchmark, references, and review; a run refuses to start if `data/benchmark_v1.freeze.json` no longer matches the files), agent and execution limits with hashes, the evaluator Git revision (`+dirty` if `src/` or `data/` has uncommitted or untracked changes) and a hash of the evaluator's own source files, Python and platform, the `uv.lock` hash, the pinned container image digest, and model settings. Records are written one trial at a time (temp file, then rename) and the manifest stores each record's SHA-256. A run that stops early keeps its finished records and an `incomplete` manifest. Request and response fields come from an allowlist, usage keeps numbers only, and no headers are stored. Environment values of variables whose names end in `_KEY`, `_TOKEN`, or `PASSWD` (or equal `KEY`/`API_KEY`/`TOKEN`) or contain `SECRET`, `PASSWORD`, or `CREDENTIAL` (8+ characters, not all digits) are replaced with `[REDACTED]` inside string values only, so records stay valid JSON; the manifest's `redactions` counts replacements. The name pattern is a heuristic, not a guarantee.

The code is not installed as a package, so run these from the repository root with `PYTHONPATH=src` (shown once):

```sh
# Fixture run (no model API). Add --grade to grade final sources in Podman.
PYTHONPATH=src .venv/bin/python -m codegen_eval.run_recording --scenario tool_use_and_revision --task strings_01 --trials 2 --grade

# Offline: needs no Podman, network, or credentials, and never executes code.
PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect list
PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect verify <run_id>
PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect show <run_id> [--trial <trial_id>]

# Grading replay: needs Podman, no model API and no credentials.
PYTHONPATH=src .venv/bin/python -m codegen_eval.replay <run_id> [--benchmark data/benchmark_v1.json]
```

(`--bundles <dir>` selects another storage directory: before the subcommand for `trace_inspect`, after the run for `replay`.)

**Grading replay is regrading, not reproduction.** It rebuilds each trial's status, label, final source, and contract verdict from its record and regrades it with `evaluate.grade_trial` and the recorded execution limits, so `no_submission`, contract failures, and infrastructure-incomplete trials are regraded the same way as the original. New evidence goes next to the original, linked to the manifest hash. It makes no model request and does not regenerate any conversation. It refuses a benchmark file whose hash (or recorded freeze `content_hash`) differs from the one recorded, refuses bundles with tampered, unrecorded, or unreadable records, copies the original bundle's problems into its evidence, reports (does not reconcile) any difference between replay and original grades, and lists `environment_differences` (container image, evaluator revision and source hash, limits hash) that could explain one.

**Completeness** (`bundle.verify_bundle`, shown by `trace_inspect verify`) compares recorded trial IDs with the manifest's planned IDs rather than counting, checks each record against its stored hash and identity, validates executed-check outcomes, and flags infrastructure stops. It reports `missing_record` (naming any partial calls retained), `tampered_record` (stored hash differs), `unrecorded_record` (the manifest never accepted the file, as after a crash between the two writes), `unexpected_record`, `infrastructure_stop`, `invalid_grade`, and similar problems; planned denominators are never reduced. Hashes detect edits and corruption, not someone who rewrites a record and the manifest together: record the printed bundle digest elsewhere to anchor it. This is the single owner of the record-level check; outcome classification and headline exclusion belong to the benchmark and grading change.

The grading side plugs in through `bundle.Grader`, which is exactly `evaluate.grade_trial`: `(Task, TrialResult) -> TrialGrade`, called for every trial including `no_submission` and `infrastructure_incomplete`. `bundle.grades_record` stores the `TrialGrade` (status `graded` or `incomplete`, trial `labels`, `success`, `infrastructure_status`, and per check `id`, `kind`, `executed`, `passed`, `failures`, `actual`); until a grader is given, grades are `{"status": "pending"}`. `replay.make_grader(runner)` binds `grade_trial` to a case runner.

## Pilot data and scoring boundary

- `data/pilot_tasks.json` contains three tasks and 12 cases. Only each task's instruction and signature are intended for the generator.
- `src/codegen_eval/tasks.py` validates dataset shape and category counts.
- `src/codegen_eval/contract.py` checks Python syntax and the one-function response contract without running code.
- `src/codegen_eval/sandbox.py` exposes `execute_check(source, function_name, args, limits)`, which runs one call in a fresh restricted container and returns a raw outcome. It never receives expected answers and passes no repository files or credentials. `src/codegen_eval/limits.py` holds the serialisable `ExecutionLimits` (10 s deadline including startup, 128 MiB, 1 CPU, 32 processes, 16 MiB tmp, 64 KiB payload, 32 KiB print, 64 KiB report; `config_hash()` identifies a configuration). `src/codegen_eval/worker.py` holds the in-container supervisor and executor.
- `src/codegen_eval/evaluate.py` compares the returned value and post-call arguments with trusted expectations outside the container, preserving each case's failure labels.

Outcomes are either candidate-attributable (`returned`, `exception`, `timeout`, `output_limit`, `serialization_error`, `payload_too_large`, `protocol_violation`, `candidate_crash`) or infrastructure (`infrastructure_error`, `protocol_error`, kept out of failure counts). A PID 1 supervisor, a separate executor, a per-check token, and a pre-bound serialiser stop a candidate from forging a result or hiding input mutation by writing to stdout, patching `json`/builtins, or exiting early; the [threat model](docs/threat_model.md) records the design, the evidence, and what is not defended. Candidate signals, deep nesting, and forged non-finite or expanding numbers end as candidate outcomes, never infrastructure ones. Candidate code that deliberately introspects its own executor can still sign a report, but only one reachable honestly (mutation is judged on net post-call state, and expected answers never enter the container); this accepted limitation stays documented, and this is an engineering control, not a security certification. Probe results per environment are recorded in [progress](docs/progress.md); the live comparison must not start while a bypass is unresolved.

## Deterministic CI (GitHub Actions)

`.github/workflows/ci.yml` runs on pushes and pull requests against `main` with two independent jobs. It defines no secrets, never calls a model API, and uses only fixtures, known candidates, and synthetic values; candidate pass rates are never gates. Tests are discovered automatically, so tests added by later changes run without editing the workflow.

| Job (check name) | What it runs | Reproduce locally |
| --- | --- | --- |
| `offline` | `uv sync --locked`, `pytest -q` (Podman tests skip here by design), `openspec validate --all --strict`, `scripts/freeze_benchmark.py --check`, `scripts/build_work_log.py --check` | the commands in [Setup](#setup) and [Verify](#verify-the-offline-evaluator), plus `openspec validate --all --strict` and the two `--check` scripts |
| `podman` | installs/verifies Podman, pulls the image by digest, runs `pytest -q -m sandbox` with `RUN_SANDBOX_TESTS=1` and a synthetic `CODEGEN_EVAL_TEST_SECRET`, then `scripts/ci_require_no_skips.py` fails the job on any skipped/errored test or an empty run | `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox -rs` (needs a running Podman) |

**Pinned environment:** runner `ubuntu-24.04` (GitHub-hosted; its Podman is used, installed with apt only if absent, and the job prints the version, rootless mode, cgroup version, and runtime); uv `0.9.3` (`setup-uv`, no cache); Python `3.12` (patch release is whatever uv provides; `requires-python` is `>=3.12,<3.13`) with dependencies from `uv.lock` (`--locked` fails on drift); OpenSpec CLI `1.14.2` with Node 22; candidate image `docker.io/library/python@sha256:950206c3…5cda5` read from `src/codegen_eval/sandbox.py`. Actions are pinned to commit SHAs: `actions/checkout` v4.2.2, `astral-sh/setup-uv` v6.8.0, `actions/setup-node` v4.4.0. Bump these deliberately and record the change in `docs/progress.md`.

**Required checks:** after the workflow has run once on GitHub, mark both as required: repository *Settings → Branches* (or *Rules → Rulesets*) → protect `main` → *Require status checks to pass* → add `offline` and `podman`. This is a repository setting, not something the workflow file can enforce; whether it has been done is recorded in `docs/progress.md`.

**Residual differences from the laptop:** the laptop runs Podman in a macOS VM (rootful, libkrun); the runner runs Podman natively on Linux, possibly rootless with a different version, cgroup setup, and kernel. The isolation, memory, process, and timeout probes must pass on the runner; any limit it cannot enforce fails the `podman` job rather than skipping. Observed runner differences are recorded in `docs/progress.md` once a real run exists.

## Local HTML work log

`scripts/build_work_log.py` builds the single offline entry point `report/index.html` (ignored by Git) from the Markdown files listed in `docs/work_log.toml`. It needs only `uv sync --python 3.12`; it uses no network, model API, Podman, MLflow, or JavaScript, and never runs candidate code.

```sh
.venv/bin/python scripts/build_work_log.py          # build report/index.html
.venv/bin/python scripts/build_work_log.py --check  # validate sources and output, write nothing
open report/index.html                              # macOS; or open the file in any browser
```

A failed build or check leaves the previous `report/index.html` untouched. Output is deterministic for the same sources and build time (`SOURCE_DATE_EPOCH` or `--build-time` fixes the stamp).

- **Sources:** only files named in `docs/work_log.toml` are read, in that order, with a `current`, `historical`, `personal`, or `reviewed` label. Missing, absolute, escaping, symlinked, or private-looking paths (secrets, `runs/`, `mlruns/`, and similar) fail the build; nothing is harvested from neighbours.
- **Pending evidence:** sections whose reviewed record does not exist yet are `kind = "pending"` and render as visibly pending. After a milestone, write or update the reviewed Markdown summary (results, run and MLflow identifiers, limitations), replace the pending entry with a `kind = "document"` entry, `label = "reviewed"` and that path, then rebuild. Link local evidence from that summary rather than embedding raw bundles; external CI/MLflow URLs are references that are never fetched.
- **Diagram:** edit `docs/work_log_architecture.svg` (plain SVG, reviewed: no scripts or external references) and its text equivalent `docs/work_log_architecture.md` together; solid outline means implemented, dashed means planned. Update both when a component is implemented.

## Plan and report sources

- [Working specification](docs/project_spec.md): scope, local-first milestones, completion evidence, and unresolved implementation decisions.
- [Progress and decisions](docs/progress.md): current status, dated evidence, and next steps.
- [Pilot benchmark](docs/pilot_tasks.md): the existing three-task dataset. The frozen target is ten reviewed tasks across five categories, with forty hidden checks; each prompt variant has three trials per task.
- [Personal learning journal](docs/learning_journal.md): student-authored expectations and reflections, preserved as report source material.
- [Historical brainstorming](docs/project_ideas.md): earlier ideas, superseded by the working specification where they differ.

## Agreed target configuration (execution limits implemented; the rest not implemented yet)

- Four logical model calls and three development-tool attempts per trial; at most four checks per tool request. The fourth model call is final-submission-only.
- Fresh restricted candidate containers per check; execution deadline **10 seconds** (configurable; implemented in `ExecutionLimits`).
- OpenRouter `z-ai/glm-5.3-flash`, pinned to OpenInference `open-inference/fp4`; temperature 0.2, top-p 1, low reasoning effort, 12k input / 2k output tokens, 60-second API attempts. Functional smoke verification is pending.
- Baseline and one revised prompt, three trials per task: sixty task trials and 240 hidden-check outcomes overall.
- Project-wide spending ledger: **CHF 10 checkpoint**, automatic continuation; **CHF 15 ceiling**, with conservative reservations including retries and uncertain charges.
- Trace inspection needs no execution service; grading replay re-executes saved final code in Podman without a model API. Deterministic response fixtures verify the agent loop separately.

The planned report entry point is `report/index.html`, generated locally from selected Markdown and reviewed summaries. The generator/output do not exist yet. The first foundation is scheduled on day two; it will collect architecture, status, decisions, benchmark review, comparison, evidence references, and reproduction instructions without hosting. Build/open commands will be documented after implementation.

OpenSpec is initialized under `openspec/`, with Codex workflow skills in `.agents/skills/`. The existing [local HTML work-log change](openspec/changes/add-local-html-work-log/proposal.md) has revised planning artifacts and no implemented tasks; main capability specs remain empty. The [Wayfinder map](.scratch/revise-project-spec/map.md) retains the user-confirmed decisions, and [glossary](GLOSSARY.md) defines evaluation terminology. A GitHub origin is configured; the CI workflow is written but has not yet run on GitHub (see [Deterministic CI](#deterministic-ci-github-actions)).
