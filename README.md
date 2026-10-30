# Agent evaluation and MLOps with Python code generation

The goal is to understand transferable agent-evaluation methods and demonstrate a reproducible MLOps workflow in **four eight-hour working days (32 hours)**. The target is a bounded function-writing agent with its own development checks, hidden final grading, durable traces/results, and offline grading replay. Required deliverables include deterministic CI, local MLflow in Podman, an offline HTML work-log, an evaluation-design guide with a research-orchestrator example, and a runnable demo. [The specification](docs/project_spec.md) defines the agreed scope and acceptance criteria.

The current implementation is still an offline pilot: it loads three tasks and twelve cases, validates Python source, executes one case at a time in a restricted Podman container, and scores returned values outside that container. The agent loop, OpenRouter client, bundles/replay, expanded benchmark, CI, and MLflow are planned. The offline HTML work-log builder exists (see below). Local orchestration will run on the laptop with uv; MLflow and disposable candidate execution use Podman. Complete the local loop before CI/tracking integration.

## Setup

Use Python 3.12 and a running Podman VM:

```sh
uv sync --python 3.12
podman pull docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5
```

The image digest is pinned per architecture in `src/codegen_eval/sandbox.py` (the `podman pull` above is the arm64 pin; on x86-64 pull the `IMAGE` printed by `PYTHONPATH=src .venv/bin/python -c 'from codegen_eval.sandbox import IMAGE; print(IMAGE)'`). The arm64 image was checked on macOS with a local Podman VM; other platforms need their own isolation check.

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

## Local MLflow tracking (Podman) and recording bundles

MLflow is a navigable *secondary* record. The run bundle stays the primary evidence, is written first, and the agent and evaluator never import or call MLflow, so a run completes with the service stopped. Only `src/codegen_eval/mlflow_tracking.py` uses the MLflow client. It is the lightweight `mlflow-skinny` package (3.17.2 in `uv.lock`, bounded `<4`) in the optional dependency group `tracking`, so a plain `uv sync` does not install it; the server only runs inside the pinned Podman image. Install it with `uv sync --python 3.12 --group tracking` (the offline MLflow tests skip with a message when it is missing; CI installs it and fails if it is absent). it reads one verified bundle and makes no model call and needs no credentials.

**Service** (`scripts/mlflow_service.sh`): image `ghcr.io/mlflow/mlflow@sha256:1a8e9dba1e19431f175f6d28aac94b0d5790e0c9a9d05d1205c6054bbd3085ac` (the v3.17.2 index digest), published only on `127.0.0.1:5000`, with the SQLite backend store and the artifact store under `./mlflow_data/` (Git-ignored, on the host, so it outlives the container). The server proxies artifacts, so clients upload over HTTP and need no filesystem access to that directory. `start` refuses to reuse an existing container whose image, port, or data directory differs from the current settings and tells you to run `down` first (data is kept). Override `MLFLOW_PORT`, `MLFLOW_DATA_DIR`, `MLFLOW_CONTAINER_NAME`, or `MLFLOW_IMAGE` (keep it pinned by digest) with environment variables.

```sh
podman pull ghcr.io/mlflow/mlflow@sha256:1a8e9dba1e19431f175f6d28aac94b0d5790e0c9a9d05d1205c6054bbd3085ac
scripts/mlflow_service.sh start      # create or start the container, wait for /health
scripts/mlflow_service.sh status     # exit 0 only if running and healthy
scripts/mlflow_service.sh stop       # stop; container and data kept
scripts/mlflow_service.sh restart
scripts/mlflow_service.sh logs
scripts/mlflow_service.sh down       # remove the container; data kept in ./mlflow_data
open http://127.0.0.1:5000           # the MLflow UI (macOS)
```

**Recording** (idempotent; run from the repository root):

```sh
PYTHONPATH=src .venv/bin/python -m codegen_eval.mlflow_tracking record <run_id> [--bundles run_bundles] [--tracking-uri http://127.0.0.1:5000] [--experiment codegen-eval-runs]
# --tracking-uri defaults to $MLFLOW_TRACKING_URI if that is set, else http://127.0.0.1:5000; the target is printed on success
PYTHONPATH=src .venv/bin/python -m codegen_eval.mlflow_tracking status      # recorded / not_recorded per bundle
```

What is written for one bundle: an MLflow run named after the run ID, tagged with the bundle identity (`codegen_eval.bundle_run_id`, `codegen_eval.bundle_digest` = SHA-256 of `manifest.json`), benchmark version/hash, prompt version/hash, evaluator revision, completion status, and `codegen_eval.headline_candidate` (true only for a complete, fully graded run, so an incomplete run is visible as incomplete and is not a headline comparison); the flattened manifest identity as parameters (model settings, limits, hashes, image digest); metrics with the full planned denominator (`success_rate` = successful trials / planned trials, check and edge-check counts, grades pending/incomplete, model calls, tool attempts, summed numeric usage, failure labels, and `trial/<id>/...` per trial); artifacts under `bundle/` (manifest, summary, every trial record, `grading/<trial_id>.json` grading evidence, `verification.json` listing every completeness problem (also summarised in the `codegen_eval.problems` tag), and any retained `trials/<id>.calls.jsonl` partial request/response entries of unfinished trials, redacted); and one trace per trial. A trial trace has an `AGENT` root with a `CHAT_MODEL` span per logical model call (request, response, usage, tools enabled), a `TOOL` span per `run_checks` attempt (arguments and the bounded feedback the model saw), `contract_failure` where one happened, and a final `submission` span (the final source or the `no_submission` outcome). Hidden case inputs, expected answers, and grades are not in the trace; they are separate artifacts. Spans carry upload-time timestamps because the bundle keeps no per-event times; their order is a `step` attribute. Physical attempts/retries become child spans only if the record's `attempts` entries carry an integer `call` field; the budget/client change has not defined that schema yet, so this is unexercised on real data.

**Grading replays** under `replays/` are recorded as separate runs nested under the original (`mlflow.parentRunId`), tagged `record_kind=grading_replay`, `agent_trial=false`, `headline_candidate=false`, with the replay's metrics and evidence as an artifact, and a tag stating whether its linked manifest hash matches the bundle. They never carry a trace and never alter the original run.

**Re-recording and outages.** Identity is run ID plus bundle digest. Recording the same identity again finds the finished run and changes nothing (`already recorded (unchanged)`); a bundle whose manifest changed (possible only before it is finalized) is a different identity with its own run. An upload that died part-way has no `codegen_eval.upload_complete` tag; the next attempt deletes that partial run and its traces and rebuilds from the bundle. Only connection and MLflow errors count as an outage; any other failure is a bug and propagates with a traceback. If the service is down, `record` exits 3 with `not yet recorded`, the bundle is untouched, and `<bundle>/tracking.json` (outside the hashed bundle) says `not_recorded`; rerun the same command later. Every uploaded value is passed through the bundle redaction again using the current environment's secret-named variables (the count is tagged `codegen_eval.redactions_at_upload`). If MLflow ever drops a trace, the upload fails instead of reporting success.

**Isolation.** Candidate containers run with `--network=none`, publish nothing, mount nothing, and receive only `HOME=/tmp`; the tracking endpoint is never passed to them. Tests assert those flags and, with Podman, that a container with the sandbox's flags cannot reach the running service while a control container with a network can.

Tests: `tests/test_mlflow_tracking.py` runs offline against a temporary SQLite store (needs `--group tracking`; SQLAlchemy and Alembic for the store are in the `dev` group). `tests/test_mlflow_service_integration.py` (marked `sandbox` and `mlflow_service`; run it locally, CI's `podman` job deselects it, needs Podman and the pinned image) starts the real service on a free port with temporary storage and checks persistence across `restart` and container removal, idempotent re-upload, outage then later upload, and candidate isolation.

## Pilot data and scoring boundary

- `data/pilot_tasks.json` contains three tasks and 12 cases. Only each task's instruction and signature are intended for the generator.
- `src/codegen_eval/tasks.py` validates dataset shape and category counts.
- `src/codegen_eval/contract.py` checks Python syntax and the one-function response contract without running code.
- `src/codegen_eval/sandbox.py` exposes `execute_check(source, function_name, args, limits)`, which runs one call in a fresh restricted container and returns a raw outcome. It never receives expected answers and passes no repository files or credentials. `src/codegen_eval/limits.py` holds the serialisable `ExecutionLimits` (10 s deadline including startup, 128 MiB, 1 CPU, 32 processes, 16 MiB tmp, 64 KiB payload, 32 KiB print, 64 KiB report; `config_hash()` identifies a configuration). `src/codegen_eval/worker.py` holds the in-container supervisor and executor.
- `src/codegen_eval/evaluate.py` compares the returned value and post-call arguments with trusted expectations outside the container, preserving each case's failure labels.

Outcomes are either candidate-attributable (`returned`, `exception`, `timeout`, `output_limit`, `serialization_error`, `payload_too_large`, `protocol_violation`, `candidate_crash`) or infrastructure (`infrastructure_error`, `protocol_error`, kept out of failure counts). A PID 1 supervisor, a separate executor, a per-check token, and a pre-bound serialiser stop a candidate from forging a result or hiding input mutation by writing to stdout, patching `json`/builtins, or exiting early; the [threat model](docs/threat_model.md) records the design, the evidence, and what is not defended. Candidate signals, deep nesting, and forged non-finite or expanding numbers end as candidate outcomes, never infrastructure ones. Candidate code that deliberately introspects its own executor can still sign a report, but only one reachable honestly (mutation is judged on net post-call state, and expected answers never enter the container); this accepted limitation stays documented, and this is an engineering control, not a security certification. Probe results per environment are recorded in [progress](docs/progress.md); the live comparison must not start while a bypass is unresolved.

## Deterministic CI (GitHub Actions)

`.github/workflows/ci.yml` runs on pushes to `main` and `ci/**` branches, pull requests against `main`, and manual dispatch, with two independent jobs. It defines no secrets, never calls a model API, and uses only fixtures, known candidates, and synthetic values; candidate pass rates are never gates. Tests are discovered automatically, so tests added by later changes run without editing the workflow. Runs for the same ref are cancelled by a newer push only on pull requests, never on `main`.

| Job (check name) | What it runs | Reproduce locally |
| --- | --- | --- |
| `offline` | `uv sync --locked --group tracking` (adds the MLflow client; `CODEGEN_EVAL_REQUIRE_TRACKING=1` makes a missing client fail instead of skip), `pytest -q` (Podman tests skip here by design), `scripts/ci_validate_openspec.sh` (strict validation of main specs and of every change that has delta specs; planning-only drafts without `specs/` are listed and skipped), `scripts/freeze_benchmark.py --check`, `scripts/build_work_log.py --check` | the commands in [Setup](#setup) and [Verify](#verify-the-offline-evaluator), plus `scripts/ci_validate_openspec.sh` and the two `--check` scripts |
| `podman` | installs Podman and runs it rootful, `scripts/ci_pull_pinned_image.sh` (pull by digest with retries and verification), `scripts/ci_verify_podman_limits.sh` (fails fast unless memory/pids/cpu controllers exist and a probe container's cgroup shows the limits), `pytest -q -m "sandbox and not mlflow_service"` with `RUN_SANDBOX_TESTS=1` and a synthetic `CODEGEN_EVAL_TEST_SECRET` (the MLflow service tests need the separate MLflow image and are local-only; CI does not run them), `scripts/ci_annotate_junit.py` turns each failed test into an `::error` annotation (plus Podman environment and leftover-container notices) so a failure is diagnosable without reading job logs, then `scripts/ci_require_no_skips.py` fails the job on any skipped/errored test or an empty run | `scripts/ci_verify_podman_limits.sh` and `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox -rs` (needs a running Podman) |

**Pinned environment:** runner `ubuntu-24.04` (GitHub-hosted, amd64; the image tag rolls weekly, so its Podman version, about 4.9 at the time of writing, is not pinned and is recorded from each run's log in `docs/progress.md`); uv `0.9.3`; Python `3.12` (patch release is whatever uv provides; `requires-python` is `>=3.12,<3.13`) with dependencies from `uv.lock` (`--locked` fails on drift); OpenSpec CLI `1.14.2` installed with `npm ci` from `.github/openspec/package-lock.json` (Node 22, scripts disabled; Node's own patch version floats). Candidate image: `python:3.12.14-slim-trixie` pinned per architecture by digest in `src/codegen_eval/sandbox.py`: `sha256:950206c3…` (arm64, laptop) and `sha256:44ff437b…` (amd64, runner). A digest names a single-platform manifest, so an arm64 digest cannot run on the amd64 runner. The CI pull configures `public.ecr.aws/docker/library` as a registry mirror for Docker Hub's official images (same digest, so identical content; a miss falls back to Docker Hub), retries four times, and fails unless the pulled digest equals the pin. Actions are pinned to commit SHAs: `actions/checkout` v4.2.2, `astral-sh/setup-uv` v6.8.0, `actions/setup-node` v4.4.0. Bump these deliberately and record the change in `docs/progress.md`.

**Why Podman runs rootful in CI:** rootless Podman can enforce memory, pids, and cpu limits only with a delegated cgroup from a logind user session, which hosted jobs do not have. The job therefore runs every Podman-using step as root (`sudo -E env "PATH=$PATH" …`, including pytest), so Podman uses the system cgroup tree like the laptop's rootful VM, and `scripts/ci_verify_podman_limits.sh` proves enforcement before any probe runs. A `sudo` shim for `podman` was tried first and abandoned: the sandbox kills a timed-out or flooding `podman run` client, and an unprivileged process cannot signal a root-owned `sudo` (EPERM), which would crash those probes. If a limit cannot be enforced the job fails with a diagnostic; it never skips.

**Container signalling:** `scripts/ci_ensure_container_signals.sh` first proves that processes inside a restricted container can signal each other (the supervisor kills an over-limit candidate that way). On the Ubuntu runner the default AppArmor container profile denies in-container signals (confirmed by an audit line in run 41128433037); if the probe fails, the job sets Podman's default AppArmor profile to `unconfined` and re-probes, failing otherwise. Whether that happened is shown by the job's `Container signals` annotation, and the trade-off is recorded in `docs/threat_model.md`.

**Required checks:** after the workflow has run once on GitHub, mark both as required: repository *Settings → Branches* (or *Rules → Rulesets*) → protect `main` → *Require status checks to pass* → add `offline` and `podman`. This is a repository setting, not something the workflow file can enforce; whether it has been done is recorded in `docs/progress.md`.

**Residual differences from the laptop:** the laptop runs Podman 6.1 in a macOS libkrun VM on arm64; the runner runs Podman 4.x natively on Linux amd64 with a different kernel and image build. The image is the same Python release but a different architecture. Observed runner differences are recorded in `docs/progress.md` and `docs/ci_evidence.md`. Planning-only OpenSpec drafts are not validated until they gain delta specs.

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
- OpenRouter `z-ai/glm-5.3-flash`, pinned to OpenInference `open-inference/fp4`; temperature 0.2, top-p 1, low reasoning effort, 12k input / 2k output tokens, 60-second API attempts. Client, ledger and CLI are implemented and tested offline ([details](docs/model_access.md)); the live smoke verification is pending.
- Baseline and one revised prompt, three trials per task: sixty task trials and 240 hidden-check outcomes overall.
- Project-wide spending ledger: **CHF 10 checkpoint**, automatic continuation; **CHF 15 ceiling**, with conservative reservations including retries and uncertain charges.
- Trace inspection needs no execution service; grading replay re-executes saved final code in Podman without a model API. Deterministic response fixtures verify the agent loop separately.

The planned report entry point is `report/index.html`, generated locally from selected Markdown and reviewed summaries. The generator/output do not exist yet. The first foundation is scheduled on day two; it will collect architecture, status, decisions, benchmark review, comparison, evidence references, and reproduction instructions without hosting. Build/open commands will be documented after implementation.

OpenSpec is initialized under `openspec/`, with Codex workflow skills in `.agents/skills/`. The existing [local HTML work-log change](openspec/changes/add-local-html-work-log/proposal.md) has revised planning artifacts and no implemented tasks; main capability specs remain empty. The [Wayfinder map](.scratch/revise-project-spec/map.md) retains the user-confirmed decisions, and [glossary](GLOSSARY.md) defines evaluation terminology. A GitHub origin is configured; the CI workflow passed on GitHub (run 41128433037; see [Deterministic CI](#deterministic-ci-github-actions)).
