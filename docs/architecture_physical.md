Text equivalent of the physical architecture figure ([`architecture_physical.drawio.svg`](architecture_physical.drawio.svg), editable in draw.io), as of 2026-11-01 on the base commit `078130a` of `main`. It shows where each part runs and which trust boundaries separate them; components and data flow are in the [logical view](architecture_logical.md). **Phase 1** is everything implemented today: local and offline on one macOS laptop. **Phase 2** is the paid, live phase: the same system once it calls OpenRouter live, plus GitHub, GitHub Actions CI, and the image registries. Phase-2 elements are drawn dashed with an orange outline on their own draw.io layer and are labelled `PHASE 2` or `EXTERNAL` in text. **IMPLEMENTED** means the code exists on `main` and its tests ran; **PARTIAL: NO LIVE RUN YET** means built and tested offline only. No live model call, comparison run, or spend exists, and no result or run identifier appears here.

## Phase 1: the laptop (trusted host, local and offline)

- **LAPTOP: macOS arm64, trusted host. PHASE 1: everything inside this box runs locally and offline.** It contains the host CLI, the files on disk, and a local Podman VM.
- **uv / Python CLI (trusted host process)** (IMPLEMENTED): `run_recording.py`, `replay.py`, `experiment_cli.py`, `trace_inspect.py`, `openrouter_cli.py`, and `build_work_log.py`. It holds the expected answers, the scoring, and the ledger. Arrow "writes and reads" to the disk area.
- **ON DISK (host filesystem, outside every container)**:
  - **`run_bundles/ (Git-ignored)`** (IMPLEMENTED): durable run bundles, written before MLflow and read by replay, summary, and comparison.
  - **`~/.codegen_eval/spend_ledger.jsonl`** (PARTIAL: NO LIVE RUN YET): the budget ledger of reservations and settlements, with a CHF 10 checkpoint and a CHF 15 ceiling; no live spend has happened.
  - **`report/index.html (Git-ignored)`** (IMPLEMENTED): the generated offline HTML work log.
  - **`mlflow_data/ (durable local storage)`** (PARTIAL: NO LIVE RUN YET): the SQLite backend store and artifact store; they survive container stop and removal.
- **PODMAN (local rootful VM): container control stays with the host CLI.** Only the host CLI can create, start, or remove containers.
  - **TRUST BOUNDARY: CANDIDATE CONTAINERS**, disposable, one per check. **`worker.py + candidate source + one case`** (IMPLEMENTED) receives its input on stdin only and returns a bounded stdout (arrow "stdin / stdout" from the CLI). The container runs with `--network=none`, a read-only root, `--cap-drop=ALL`, `no-new-privileges`, user 65534, memory/pids/cpu limits, no mounts, and a `noexec` tmpfs `/tmp`. It has no network, no credentials, no repository files, no MLflow, and no Podman access. No arrow leaves a candidate container except that stdout to the host.
  - **`pinned candidate image (local store)`** (IMPLEMENTED): `python:3.12.14-slim-trixie` by digest, one digest per architecture, pulled once.
  - **`MLflow service container (separate, durable)`** (PARTIAL: NO LIVE RUN YET): started by `scripts/mlflow_service.sh` from a pinned `ghcr.io` digest, published on `127.0.0.1:5000` only, with `mlflow_data/` as its only mount (arrow "mounts"). The host CLI reaches it over HTTP on `127.0.0.1` (arrow "HTTP, 127.0.0.1"). No candidate container can reach it. So far it has recorded only a fixture bundle.

## Phase 2: external subsystems (paid / live phase)

- **EXTERNAL SUBSYSTEMS: PHASE 2 (paid / live phase)** contains everything below.
- **`OPENROUTER_API_KEY (environment variable)`** (PHASE 2 only): set in the host environment; read only by `openrouter_cli.py` and `experiment_cli.py`; never written to bundles, the ledger, or any container (dashed arrow "env var read at start").
- **OpenRouter API (EXTERNAL)** (PHASE 2): `https://openrouter.ai/api/v1/chat/completions`, called over HTTPS from the host process only, with the key in a header and each attempt reserved in the ledger first (dashed arrow "HTTPS + key"). No live call has been made yet.
- **IMAGE REGISTRIES (EXTERNAL)** (PHASE 2): `docker.io/library/python` for the candidate image (by digest, with a `public.ecr.aws` mirror used in CI) and `ghcr.io/mlflow/mlflow` for the MLflow image (by digest); images flow from the registries to the local store (dashed arrow "podman pull") and to the CI runner.
- **GitHub repository (EXTERNAL)** (PHASE 2): a push triggers CI (dashed arrow "triggers").
- **GitHub Actions hosted runner** (`ubuntu-24.04`, amd64; EXTERNAL; PHASE 2) with two jobs. **job offline: no Podman needed**: locked uv environment, tests, OpenSpec validation, benchmark freeze check, and the work-log check; Podman tests skip there by design. **job podman: rootful Podman on the runner**: pulls the pinned amd64 digest with retries and a mirror, runs the sandbox tests, treats a skip as a failure, and checks that a synthetic secret is never visible in a container. Both jobs have run green, as recorded in [CI evidence](ci_evidence.md); CI never calls a model API.

## What changes from phase 1 to phase 2

The new arrows are the HTTPS call to OpenRouter and the key it needs, the pulls from registries, and the GitHub and Actions pipeline. The trust boundary does not move: the key, the expected answers, the ledger, and the scoring stay in the host process, and candidate containers still have no network, no credentials, no MLflow, and no Podman access.

Maintenance: edit the diagram in draw.io, save it, then edit this page in the same change; `tests/test_architecture_diagrams.py` checks that the labels, names, and claims agree with each other and with the source tree.
