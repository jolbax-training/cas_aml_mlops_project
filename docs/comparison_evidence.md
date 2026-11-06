# Comparison evidence: local bundles and MLflow identifiers

References only (recorded 2026-11-03, never fetched by the report). Metrics, trace explanations, limitations and the decision are in the [prompt comparison](prompt_comparison.md). Bundles are under `run_bundles/` (Git-ignored, retained on the machine that ran them); MLflow is the local service at `http://127.0.0.1:5001` (experiment 1), so the MLflow identifiers resolve only while that service and its store are available. CI runs are in the [CI evidence](ci_evidence.md).

| Variant | Run ID | Bundle | Bundle digest (sha256 of `manifest.json`) | MLflow run | Prompt |
| --- | --- | --- | --- | --- | --- |
| baseline | `20261103T053309Z-280182` | `run_bundles/20261103T053309Z-280182` | `1a2e964fce29acca6f8ab223dab1a56e260b3624955575f6297f2d8b0a9aced1` | `930a188254d34d279a88a7613ea55518` | `baseline_agent_v1` |
| revised | `20261103T095324Z-d25905` | `run_bundles/20261103T095324Z-d25905` | `210fb4bbba433c87ffd4e4918cc1c3f39e8d504e0a443f203b674b52f091ea39` | `bcddf5c9561c43129504555b020a7557` | `baseline_agent_v2` |

Both bundles verify as COMPLETE (30 of 30 planned trials with intact records). Shared versions: benchmark 1 (sha256 `d75c06ae3a8d8d98fbe2bdeb8ec36e4d80f6279c0040a394aee2247a20f556b6`), experiment `prompt_comparison_v1`, settings hash `4c3b3b351075142e9db945a7eacb64fe47fef689e83f212957dec72efe0d1c9e`, model config `openrouter_glm_v1`. The experiment configuration hash differs by design and is recorded per bundle: baseline `ceec6d991427dc8b375422e8caa1fcf534295aecbae33af7e22216fd6c576233` (revised prompt not yet set), revised `465c76e893ca6c14e31de0a082a3b9027e6bcb95c4b09389d2ba43dca7c255dd` (revised prompt set); the fields that must agree, and do, are the schedule sha256, settings hash and evaluator code hash. Retained smoke evidence for the settings freeze: [smoke_evidence.md](smoke_evidence.md).

Reproduce the numbers without any service: `PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect --bundles run_bundles verify <run ID>` and `PYTHONPATH=src .venv/bin/python -m codegen_eval.experiment_cli compare --baseline 20261103T053309Z-280182 --revised 20261103T095324Z-d25905` (flags as in the [README](../README.md) and [demo](demo.md)).

MLflow verification (2026-11-06, read-only client 3.17.2 against the 3.17.2 server image pinned in `scripts/mlflow_service.sh`): tags, parameters, metrics, artifacts, and the trace structure of both runs match the bundles and the `compare` numbers; 5 of the 60 traces (`numeric_logic_01-t2`, `-t3` of the baseline; `-t1`, `-t2`, `-t3` of the revised run) cannot be read back because the server fails to serialise integers above 64 bits that the model used in its `run_checks` arguments (HTTP 500). Details in the progress entry of 2026-11-06.
