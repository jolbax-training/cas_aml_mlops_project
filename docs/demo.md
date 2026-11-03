# Replay and demo path

This is the walk-through for the final demo, ordered so that everything before the comparison needs no model credentials and no new paid generation. Run every command from the repository root. The shell prefix used for the credential-free checks is `env -i HOME=$HOME PATH=/opt/podman/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`, which starts the command with no inherited environment (no API keys, no `OPENROUTER_*`); the commands below omit it for readability.

## Status

| Part | State |
| --- | --- |
| Setup, inspection, replay, MLflow navigation, offline report, local CI commands | Commands re-executed 2026-10-30/31 on the laptop; see [Verified commands](#verified-commands) |
| Comparison and keep/reject decision | Two complete runs recorded 2026-11-03: baseline 27/30, revised 29/30 successful task trials; decision keep v2 ([section 6](#6-the-comparison-and-keep-or-reject-decision)); the student's interpretation is not filled in |
| Full rehearsal with no model credentials | Not done (task 2.2 of `prepare-reproducible-demo`, after the comparison) |

The demo path below uses a **fixture-client bundle** (scripted model responses). It demonstrates the tooling, not model quality, and any numbers it shows are not results of the project's experiment.

## Verified commands

Recorded from a re-execution on 2026-10-30 (UTC 23:55 onward) on macOS arm64, `main` at `0c8b0ff` plus this change: uv 0.9.3, Python 3.12.12, Podman 6.1.4 (libkrun VM running), pinned image `python@sha256:950206c3…` (arm64), MLflow image v3.17.2 (`sha256:1a8e9dba…`), mlflow-skinny 3.17.2, OpenSpec CLI 1.14.2.

| Step | Command | Observed |
| --- | --- | --- |
| Environment | `uv sync --python 3.12` (add `--group tracking` for MLflow) | succeeded |
| Restore candidate image | `podman pull docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5` | succeeded; image id `8630ab77c5ad` |
| Offline tests (no credentials) | `.venv/bin/pytest -q` | 490 passed, 90 skipped (Podman tests skip unless `RUN_SANDBOX_TESTS=1`; MLflow tests skip without `--group tracking`); with `--group tracking`: 513 passed, 67 skipped |
| Fixture bundle | `PYTHONPATH=src .venv/bin/python -m codegen_eval.run_recording --scenario tool_use_and_revision --task strings_01 --trials 2 --grade` | bundle `run_bundles/20261030T235533Z-3dba0d`, 2 of 2 trials, complete |
| Inspect, no Podman, no API | `PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect list` / `verify <run_id>` / `show <run_id>` | run with `PATH=/usr/bin:/bin` (Podman not findable) and an empty environment: `complete`, "2 of 2 planned trials have intact records", bundle digest `785069e0…ae94f` |
| Grading replay | `PYTHONPATH=src .venv/bin/python -m codegen_eval.replay <run_id>` | empty environment; evidence `run_bundles/20261030T235533Z-3dba0d/replays/replay-20261030T235558Z-079d7d.json`; `regraded 2, compared 2, mismatched 0, incomplete 0` |
| MLflow service | `scripts/mlflow_service.sh start` then `status` | "running and healthy at http://127.0.0.1:5000" |
| Record to MLflow | `PYTHONPATH=src .venv/bin/python -m codegen_eval.mlflow_tracking record <run_id>` (then `status`) | recorded as MLflow run `c89b068e…` plus the replay run; a second `record` printed `already recorded (unchanged)` |
| Report | `.venv/bin/python scripts/build_work_log.py --check`, then build, then `open report/index.html` | check passed (11 sources, 3 pending sections before this change; 12 sources, 2 pending after registering this document); built; opened |
| Local CI equivalents | `scripts/ci_validate_openspec.sh`; `.venv/bin/python scripts/freeze_benchmark.py --check`; `.venv/bin/python scripts/build_work_log.py --check` | all exit 0 (`benchmark freeze matches`) |
| Podman suite | `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox -rf --durations=25 --junitxml=<scratch>/sandbox-junit.xml` (the extra flags name every failure, as CI does; see [Sandbox suite under load](#sandbox-suite-under-load)) | second run: 67 passed, 513 deselected (254 s). A first run under load from parallel workers on the same Podman VM had 4 failures (three in `tests/test_mlflow_service_integration.py` and `tests/test_run_bundle.py::test_replay_regrades_known_candidates_in_podman`; the fourth was not captured); the replay test passed alone and the whole suite passed on the rerun, so the cause is unconfirmed and presumed contention, not a fix |

The run ID and MLflow run IDs above belong to the **fixture** bundle created for this verification. `run_bundles/` and `mlflow_data/` are Git-ignored, so a fresh checkout has to create its own bundle with the fixture command; use the IDs it prints. They are not comparison evidence.

## The demo path

### 1. Setup (about 2 minutes)

```sh
uv sync --python 3.12 --group tracking
podman pull docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5   # arm64 pin
.venv/bin/pytest -q
```

On x86-64, pull the `IMAGE` that `PYTHONPATH=src .venv/bin/python -c 'from codegen_eval.sandbox import IMAGE; print(IMAGE)'` prints.

### 2. Trace inspection: no API, no Podman

```sh
PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect list
PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect verify <run_id>
PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect show <run_id> --trial <trial_id>
```

Show: completeness against the planned trial IDs, the manifest identity (prompt/benchmark/limits hashes, image digest, evaluator revision), and one trial's requests, tool interactions, drafts and final source. Inspection never executes code.

### 3. Grading replay: Podman, no model API

```sh
PYTHONPATH=src .venv/bin/python -m codegen_eval.replay <run_id>
```

Say it plainly: this **regrades saved final candidates**; it is not a fresh agent trial and calls no model. The evidence is a separate file at `run_bundles/<run_id>/replays/<replay_id>.json`; the original grades are never overwritten, and any mismatch or environment difference is reported rather than reconciled. In particular an `environment differs (evaluator_revision): original … replay …` line is expected whenever the replaying checkout is a different commit from the one that recorded the bundle (for the fixture bundle above, recorded at `0c8b0ff`, any later commit); it is information, not a failure.

### 4. MLflow navigation

```sh
scripts/mlflow_service.sh start
PYTHONPATH=src .venv/bin/python -m codegen_eval.mlflow_tracking record <run_id>
open http://127.0.0.1:5000
```

In the UI: experiment `codegen-eval-runs` → the run named after the run ID. Show tags (`codegen_eval.headline_candidate`, bundle digest), parameters (identity, limits, hashes), metrics (`success_rate` over the planned denominator, `trial/<id>/…`), the **Traces** tab (one trace per trial: `AGENT` root, `CHAT_MODEL` per model call, `TOOL` per `run_checks`, final `submission`), and artifacts under `bundle/`. The replay appears as a nested run tagged `grading_replay`, `headline_candidate=false`. MLflow is a secondary record; the bundle is the primary evidence and everything above works with the service stopped. If the service is down, `record` exits 3 and can be rerun later.

### 5. Offline report

```sh
.venv/bin/python scripts/build_work_log.py
open report/index.html
```

Needs no network, Podman, MLflow, or JavaScript. Walk the architecture figure (solid blue = implemented, solid yellow = built offline with no live run yet, dashed = pending), then the status, benchmark review, CI evidence, setup, and this demo section. Sections without a reviewed record are shown as pending or incomplete; say so rather than skipping them.

### 6. The comparison and keep-or-reject decision

Open [the prompt comparison](prompt_comparison.md) (report section "Results, comparison, and limitations") and [the evidence references](comparison_evidence.md) (report section "Local evidence and MLflow identifiers"). Recorded 2026-11-03 (no new paid call): baseline run `20261103T053309Z-280182` (`baseline_agent_v1`) 27 of 30 successful task trials, revised run `20261103T095324Z-d25905` (`baseline_agent_v2`) 29 of 30, both COMPLETE (30 of 30 planned trials), MLflow runs `930a188254d34d279a88a7613ea55518` and `bcddf5c9561c43129504555b020a7557`, decision: keep v2, because the targeted failure mode did not recur (0 of 30 revised trials submitted prose or fences; no revised trial had a failed self-written check, so the added sentence's trigger was never exercised).

Walk the gain (`lists_02`, 0/3 to 3/3: the baseline traces submit explanation text after a wrong self-written check; the revised traces submit the bare function with no tool attempt), the regression (`strings_01-t2`, a case-folding wrong answer), and the limits (30 trials per variant, one model and provider, fixed sampling, no repeated runs, precision not returned by the provider). Replaying the bundles needs Podman and no credentials; `compare` and `trace_inspect` need neither. Inspection commands are in sections 2 and 3. The student's interpretation slot in the write-up is empty on purpose.

### 7. Transfer guide

Open the [evaluation design guide](evaluation_design_guide.md) (seven steps, each tied to what this project retained) and the [research-coordinator example](research_coordinator_example.md) (design only: six scenarios, not executed). Point out which parts carry over to a different agent: outcome definition, frozen tasks, deterministic graders first, bounded trials, trace review, replay, keep/reject rule.

## Credential-free expectations

Inspection, replay, the offline report, and navigation of already-recorded evidence need no model credentials; sections 2 and 3 were executed above with an empty environment (section 5's build was run from the normal shell; it reads no credentials), and section 7 is reading only. A live call, if one is ever shown, is charged to the shared ledger under the CHF 15 ceiling and is not part of this path. Personal reflections in the [learning journal](learning_journal.md) are not required and are not filled in by this document.

## Sandbox suite under load

The production deadline (10 s) includes container creation and start, so a slow start on a loaded shared Podman VM is a candidate `timeout`. That stays. The Podman test session therefore (all in `tests/conftest.py` and `tests/sandbox_support.py`, active only with `RUN_SANDBOX_TESTS=1`): takes a cross-worktree file lock (`~/.cache/codegen-eval/sandbox.lock`, or under `$XDG_CACHE_HOME`; `CODEGEN_EVAL_SANDBOX_LOCK=0` disables it) so parallel sessions queue; removes `codegen-eval-<pid>-…` containers whose process is gone; measures the slowest of three trivial container checks (printed in the pytest header) and aborts if it exceeds 5 s (`CODEGEN_EVAL_STARTUP_CAP`); and runs tests that expect a non-timeout outcome with a deadline of 10x that measurement (never below 10 s). Tests that assert `timeout` keep their explicit short deadline. `MLFLOW_HEALTH_TIMEOUT` (default 60 s, 240 s in the MLflow service tests) sets the health wait of `scripts/mlflow_service.sh`.
