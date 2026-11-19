# Comparison evidence at scale: local bundles and MLflow identifiers

References only. The protocol is in the [at-scale prompt comparison](prompt_comparison_v2.md); the identifiers below are to be recorded after each run and are not known yet. Bundles are under `run_bundles_v2/` of the primary checkout (Git-ignored locally, retained); MLflow is the local service (experiment `codegen-eval-prompt-comparison-v2`). The first comparison's identifiers are in [comparison_evidence.md](comparison_evidence.md) and are unchanged.

| Run | Variant | Run ID | Bundle | Bundle digest (sha256 of `manifest.json`) | MLflow run | Prompt |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | baseline | to be recorded | to be recorded | to be recorded | to be recorded | `baseline_agent_v1` |
| 2 | revised | to be recorded | to be recorded | to be recorded | to be recorded | `baseline_agent_v2` |
| 3 | baseline repeat | to be recorded | to be recorded | to be recorded | to be recorded | `baseline_agent_v1` |

Committed evidence: `experiments/evidence_v2/settings_freeze.json` (settings freeze for `prompt_comparison_v2`, recorded read-only against the first comparison's retained smoke bundle; the record stores that bundle's absolute path on the machine that recorded it), and to be recorded: `experiments/evidence_v2/probes.json` with its junit report, and `experiments/evidence_v2/analysis/` (outputs of `experiment_cli compare` and `scale_analysis`).

Shared versions (identical to the first comparison; from `experiments/prompt_comparison_v2.json`): benchmark 1 (sha256 `d75c06ae3a8d8d98fbe2bdeb8ec36e4d80f6279c0040a394aee2247a20f556b6`), settings hash `4c3b3b351075142e9db945a7eacb64fe47fef689e83f212957dec72efe0d1c9e`, model config `openrouter_glm_v1`. The commit at which the three runs were made, the evaluator code hash and the schedule sha256 are to be recorded.
