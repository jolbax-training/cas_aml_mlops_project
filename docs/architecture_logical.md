Text equivalent of the logical architecture figure ([`architecture_logical.drawio.svg`](architecture_logical.drawio.svg), editable in draw.io), as of 2026-11-01 on the base commit `078130a` of `main`. It shows components and data flow independent of where they run; where they run is the [physical view](architecture_physical.md). Boxes name real files under `src/codegen_eval/` or `scripts/`. **IMPLEMENTED** means the code exists on `main` and its tests ran; **PARTIAL: NO LIVE RUN YET** means built and tested offline only (no live model call, no real comparison run has happened); **PENDING** means the evidence does not exist. Status comes from the [progress record](progress.md) and the [CI evidence](ci_evidence.md). No result, run identifier, URL, or spend appears here because none exists.

**Task and agent (left column, top rows)**

- **`tasks.py`** (IMPLEMENTED): frozen benchmark tasks and hidden cases from `data/benchmark_v1.json`. Arrow "task" to `trial.py`.
- **`agent_config.py + prompts/`** (IMPLEMENTED): the versioned baseline prompt. Arrow "prompt" to `trial.py`.
- **`trial.py`** (IMPLEMENTED): the bounded agent loop, with four model calls, three development-tool attempts, and at most four checks per request. Arrow "request" to the `ModelClient` interface; arrow "dev check request" to `run_checks.py`.
- **`model_client.py`** (IMPLEMENTED): the `ModelClient` interface and the offline, API-free `FixtureClient` that stands in for the model in every test today.

**Model access (phase 2 pieces, built offline only)**

- **`openrouter_client.py`** (with `openrouter_config.py` and the `model_configs/` directory; PARTIAL: NO LIVE RUN YET) implements the model client interface ("impl.") and reserves each attempt in the ledger before sending ("reserve"). Arrow "HTTPS" (dashed) to **OpenRouter (external model API)** (PENDING, PHASE 2: no live call has been made).
- **`openrouter_cli.py`** (PARTIAL: NO LIVE RUN YET): the live smoke command; with `experiment_cli.py` it is the only reader of `OPENROUTER_API_KEY`. Arrow "builds client" to `openrouter_client.py`. It has not been run live.
- **`ledger.py`** (PARTIAL: NO LIVE RUN YET): the spending ledger with a CHF 15 ceiling.

**Development checks, final grading, and the trust boundary**

- **`run_checks.py`** (IMPLEMENTED): runs the agent's own example checks using only the function name and signature, and returns bounded feedback, so feedback never contains hidden expected answers. Arrow "check run" to `sandbox.py`.
- **`evaluate.py + contract.py`** (IMPLEMENTED): the final submission is validated as source (`contract.py`, never executed) and graded against the hidden cases (`evaluate.py`, `grade_trial`). Expected answers and scoring stay on the trusted host. Arrow "per case" to `sandbox.py`.
- **`sandbox.py + limits.py`** (IMPLEMENTED): the host-side launcher that starts one fresh container per check with resource limits. Arrow "stdin / stdout" to `worker.py`.
- **TRUST BOUNDARY: candidate container** contains **`worker.py`** (IMPLEMENTED): the only code that runs inside a container is candidate source plus one case's arguments. No network, no credentials, no repository files, no MLflow, and no Podman control are available there. The [threat model](threat_model.md) records residual limitations.

**Evidence flow**

- **`run_recording.py + bundle.py`** (IMPLEMENTED): runs a trial (arrow "runs trial" back to `trial.py`), grades it through the injected grader (arrow "grade_trial" to `evaluate.py`), and writes the durable run bundle first, with partial calls and redaction. The bundle is read by `replay.py`, `trace_inspect.py`, `summary.py`, and recorded by `mlflow_tracking.py`.
- **`replay.py`** (IMPLEMENTED): re-grades saved final candidates from a bundle without any model generation; it still uses Podman (arrow "re-grade" to `evaluate.py`).
- **`trace_inspect.py`** (IMPLEMENTED): read-only inspection of bundles, with no service, model, or sandbox.
- **`mlflow_tracking.py`** (PARTIAL: NO LIVE RUN YET): records a bundle after it is written ("bundle then record"); it never reads MLflow back. Arrow "uploads" to **MLflow tracking store** (PARTIAL: NO LIVE RUN YET): a secondary record that has so far received only a fixture bundle.
- **`experiment.py + experiment_cli.py`** (PARTIAL: NO LIVE RUN YET): run the prompt variants through `run_recording.py` and inject the MLflow recorder. Arrow "runs two variants" to `comparison.py`.
- **`summary.py`** (PARTIAL: NO LIVE RUN YET): fixed-denominator run summaries read from bundles. Arrow "summaries" to `comparison.py`.
- **`comparison.py`** (PARTIAL: NO LIVE RUN YET): compares baseline and revised runs from bundles, not from MLflow; the comparison has not run. Dashed arrow "reviewed by a human" to the result summaries.
- **`reviewed result summaries`** (PENDING): reviewed Markdown summaries of results, run identifiers, and limitations. They need the comparison runs and are not invented here. Arrow "selected .md" to the work-log builder.

**Report and CI**

- **`scripts/build_work_log.py`** (IMPLEMENTED): turns the explicitly selected Markdown, including this page, into the local `report/index.html`.
- **CI gate (.github/workflows/ci.yml)** (IMPLEMENTED): the offline job runs tests, OpenSpec validation, the benchmark freeze check, and the work-log check (arrow "--check" to the builder); the podman job runs the sandbox tests and fails on any skip. CI uses fixtures and probes only and never calls a model API.
- **STATUS KEY (text label on every box)**: repeats the three status labels; every box carries its status as text, so meaning never depends on colour. Solid blue is implemented, solid yellow is partial, dashed is pending or external.

Maintenance: edit the diagram in draw.io, save it, then edit this page in the same change; `tests/test_architecture_diagrams.py` checks that the labels, names, and claims agree with each other and with the source tree.
