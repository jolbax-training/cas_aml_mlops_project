Text equivalent of the figure above, as of 2026-10-31. Boxes name the implemented modules under `src/codegen_eval/`. **Implemented** means code exists on `main` and its tests ran; **partial** means built and tested offline, but with no live model run yet; **pending** means the evidence does not exist. Status comes from the [progress record](progress.md) and the [CI evidence](ci_evidence.md), not from this page.

**Agent flow (implemented, offline-tested only for the model)**

1. A task instruction and signature (`tasks.py`) and the versioned baseline prompt (`prompts/baseline_agent_v1.md`, `agent_config.py`) go to the bounded agent in `trial.py`: four model calls, three development-tool attempts, at most four checks per request.
2. The agent calls the model through the OpenRouter client (`openrouter_client.py`) behind the `ModelClient` interface (`model_client.py`); every paid attempt is reserved in the spending ledger (`ledger.py`) first. **Partial:** this is tested with fixtures and fakes only. No live model call has been made.

**Development-check flow (implemented)**

3. The agent may write its own example checks. `run_checks` (`run_checks.py`) runs them, one per fresh container, and returns bounded feedback. It uses only the function name and signature, so feedback never contains hidden expected answers.

**Hidden-grading flow (implemented)**

4. An explicit final submission is validated as source (`contract.py`, never executed) and then graded against the hidden acceptance cases (`evaluate.py`, `grade_trial`) in fresh containers. Expected answers and scoring stay in the trusted host process.

**Trust boundary (implemented)**

5. The only code that runs inside a container (`sandbox.py`, with the in-container `worker.py`) is candidate source plus one case's arguments. Expected answers, scoring, credentials, repository files, network, tracking, and Podman controls stay outside. The [threat model](threat_model.md) records the residual limitations; the sandbox probes ran locally and on GitHub Actions.

**Evidence flow**

6. Implemented: every finished trial is written to a durable local run bundle first (`bundle.py`, `run_recording.py`). Grading replay (`replay.py`) re-runs hidden grading on saved final candidates without any model generation and still uses Podman. Deterministic CI (`.github/workflows/ci.yml`) covers fixtures and probes only; its green runs reach this report through the separate CI evidence section (`docs/ci_evidence.md`), not through the evidence flow above.
7. Partial: local MLflow recording (`mlflow_tracking.py`) is built from bundles and has so far recorded only a fixture bundle against the local service; no live model or comparison run has been recorded. MLflow is a secondary record and is never read back: comparison metrics come from the bundles. The comparison tooling (`comparison.py`, `experiment.py`, `experiment_cli.py`) and fixed-denominator summaries (`summary.py`) are built and tested offline; the baseline-versus-revised comparison itself has not run.
8. Pending: reviewed Markdown summaries of the comparison (results, evidence identifiers, limitations). They need the comparison runs and are not invented here.
9. Implemented: this report builder (`scripts/build_work_log.py`) turns the selected Markdown into `report/index.html`.

Sections of this report whose evidence does not exist yet are labelled pending. No result, URL, or reflection is invented to fill them.
