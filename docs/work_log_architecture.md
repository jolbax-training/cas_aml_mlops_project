Text equivalent of the figure above, as of 2026-11-13, statuses refreshed from the committed evidence. Boxes name the implemented modules under `src/codegen_eval/`. **Implemented** means code exists on `main` and its tests ran; **partial** (no box uses it now) means built and tested offline, but with no live model run; **pending** (no box uses it now) means the evidence does not exist. The baseline and revised comparison runs have completed (evidence: [comparison evidence](comparison_evidence.md), [prompt comparison](prompt_comparison.md)). The evidence is a 30-trial pilot per variant and draws no general conclusion; the student's own interpretation in the prompt comparison is still open. Status comes from the [progress record](progress.md) and the [CI evidence](ci_evidence.md), not from this page.

**Agent flow (implemented; live use in the smoke evidence and the prompt comparison)**

1. A task instruction and signature (`tasks.py`) and the versioned baseline prompt (`prompts/baseline_agent_v1.md`, `agent_config.py`) go to the bounded agent in `trial.py`: four model calls, three development-tool attempts, at most four checks per request.
2. The agent calls the model through the OpenRouter client (`openrouter_client.py`) behind the `ModelClient` interface (`model_client.py`); every paid attempt is reserved in the spending ledger (`ledger.py`) first. Live use is documented in the [smoke evidence](smoke_evidence.md) and the [prompt comparison](prompt_comparison.md); the model and provider are fixed there, and the offline tests still use fixtures and fakes.

**Development-check flow (implemented)**

3. The agent may write its own example checks. `run_checks` (`run_checks.py`) runs them, one per fresh container, and returns bounded feedback. It uses only the function name and signature, so feedback never contains hidden expected answers.

**Hidden-grading flow (implemented)**

4. An explicit final submission is validated as source (`contract.py`, never executed) and then graded against the hidden acceptance cases (`evaluate.py`, `grade_trial`) in fresh containers. Expected answers and scoring stay in the trusted host process.

**Trust boundary (implemented)**

5. The only code that runs inside a container (`sandbox.py`, with the in-container `worker.py`) is candidate source plus one case's arguments. Expected answers, scoring, credentials, repository files, network, tracking, and Podman controls stay outside. The [threat model](threat_model.md) records the residual limitations; the sandbox probes ran locally and on GitHub Actions.

**Evidence flow**

6. Implemented: every finished trial is written to a durable local run bundle first (`bundle.py`, `run_recording.py`). Grading replay (`replay.py`) re-runs hidden grading on saved final candidates without any model generation and still uses Podman. Deterministic CI (`.github/workflows/ci.yml`) covers fixtures and probes only; its green runs reach this report through the separate CI evidence section (`docs/ci_evidence.md`), not through the evidence flow above.
7. Implemented: local MLflow recording (`mlflow_tracking.py`) is built from bundles and has recorded both live comparison runs against the local service; all 60 of 60 traces read back after `--retrace` ([progress record](progress.md)). MLflow is a secondary record and is never read back: comparison metrics come from the bundles. The comparison tooling (`comparison.py`, `experiment.py`, `experiment_cli.py`) and fixed-denominator summaries (`summary.py`) are implemented, and the baseline-versus-revised comparison has run on the bundles ([prompt comparison](prompt_comparison.md)).
8. Implemented: the reviewed Markdown summary of the comparison (results, evidence identifiers, limitations, the user's decision) is [prompt comparison](prompt_comparison.md). The student's own interpretation there stays open.
9. Implemented: this report builder (`scripts/build_work_log.py`) turns the selected Markdown into `report/index.html`.

A section whose evidence does not exist is labelled pending in the report; none is pending now. No result, URL, or reflection is invented to fill one.

The detailed, editable [logical](architecture_logical.md) and [physical](architecture_physical.md) views follow this figure in the report.
