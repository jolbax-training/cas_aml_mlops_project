# Prompt comparison at scale: baseline, revised, baseline repeat (`prompt_comparison_v2`)

Status: protocol written 2026-11-19; the three runs are scheduled and **no result has been recorded**. Every section marked "to be recorded" is filled from the saved output of `experiment_cli compare` and `codegen_eval.scale_analysis` after the runs, and nothing in it may be written before then. This is the pipeline run at scale: a larger, repeated measurement with the same prompts as the [first comparison](prompt_comparison.md), not proof that the revised prompt improves anything. The first comparison's files are not changed by it.

## Why a second comparison

The first comparison ran ten tasks x 3 trials per prompt (27/30 against 29/30). Its own limitations say that n is small, that run-to-run variation of the same prompt is unmeasured, and that the order was fixed (baseline first, revised hours later), so drift of the provider cannot be separated from the prompt. The user approved a larger comparison to enrich the presentation with a measured spread.

## Design

- **Experiment** `prompt_comparison_v2` (`experiments/prompt_comparison_v2.json`, built with `build-config --experiment-id prompt_comparison_v2 --trials-per-task 10 --revised-prompt baseline_agent_v2 --container-platform arm64`). Only the experiment identity, the trials per task (10) and the schedule (ten tasks x 10 trials = 100 trials per run, `task_major` order, trial ids `<task>-t1` to `<task>-t10`) differ from `prompt_comparison_v1`. The benchmark (version 1, sha256 `d75c06ae3a8d8d98fbe2bdeb8ec36e4d80f6279c0040a394aee2247a20f556b6`), the settings hash `4c3b3b351075142e9db945a7eacb64fe47fef689e83f212957dec72efe0d1c9e` (model config `openrouter_glm_v1`: `z-ai/glm-5.3-flash`, provider pin `open-inference/fp4`, temperature 0.2, top_p 1.0, low reasoning effort, 2,000 output tokens; the agent limits of at most 4 model calls and 3 tool attempts; the execution limits; the pinned arm64 container image) and both prompts (`baseline_agent_v1` and `baseline_agent_v2`, same file hashes as in v1) are identical to the first comparison. The settings freeze reuses the first comparison's retained smoke bundle read-only; no new smoke was made.
- **Three runs in the order A-B-A**: baseline, revised, baseline repeat (about 300 trials in total). The repeat measures the run-to-run variation of one prompt; the order brackets provider drift (the repeat is made after the revised run, so a drift over the whole span shows up as a difference between the two baseline runs).
- **Not built:** trial-level interleaving of the two prompts. The experiment tooling writes one bundle per variant and verifies each against one prompt, so interleaving would need a new runner and verifier. It would cancel drift per task, but it would not measure run-to-run variation; A-B-A stays the design.
- **Storage:** bundles in `run_bundles_v2/` of the primary checkout, never in `run_bundles/`; evidence (probe record, settings freeze, analysis output) committed under `experiments/evidence_v2/`; MLflow experiment `codegen-eval-prompt-comparison-v2`. The commands, with every path flag spelled out, are in the OpenSpec change `scale-prompt-comparison` (`design.md`, Decision 8) and in the README section on the three-run workflow.
- **Data safety:** the first comparison's configuration, evidence, retained bundles, documents and MLflow runs are not modified; the configuration, freeze and probe writers refuse to replace any existing file whose content would differ. The spend ledger is appended to only by `check`/`run` through the normal budget path; the analysis never opens it.

## Analysis

Per run: the metrics of the first comparison, the successes out of 10 for each task, the charged CHF, and a Wilson 95% interval for the overall success rate (successful trials / 100 planned trials). Then baseline against revised and baseline against baseline repeat with the same metrics, the per-task differences and whether the two intervals overlap. The analysis is deterministic and offline (`PYTHONPATH=src .venv/bin/python -m codegen_eval.scale_analysis ...`). No significance test is computed.

## Stop rules for the paid runs

Stop and ask the user if the actual charged spend of the v2 runs (summed from the bundles) exceeds CHF 1, if any run ends incomplete, or if the ledger's CHF 10 checkpoint is reached. The worst-case reservation checked before a run (CHF 0.0008197 per attempt, at most 600 attempts per run; about CHF 1.4755 for all three runs) is accepted: it is below the checkpoint and the CHF 15 ceiling. The first comparison charged CHF 0.00275 and CHF 0.00297 for 30 trials each, so about CHF 0.03 is expected for 300 trials.

## Evidence references

To be recorded: run IDs, bundle digests, MLflow runs and the commit at which the runs were made are listed in [comparison_evidence_v2.md](comparison_evidence_v2.md).

## Results (primary metric and diagnostics)

To be recorded after the three runs.

## Run-to-run variation and the revised prompt

To be recorded after the three runs. The baseline-versus-repeat difference is the observed run-to-run variation of one prompt and the yardstick for the baseline-versus-revised difference. Interval overlap is a descriptive aid, not a test, and overlap does not mean that there is no difference.

## Efficiency

To be recorded after the three runs.

## Trace-based explanations

To be recorded after the three runs, from `trace_inspect show` of selected trials.

## Limitations

- **Benchmark-informed tuning.** The revised prompt was written after reading the baseline failures of the first comparison on these same ten tasks, so any difference is limited to these tasks and may reflect fitting to the observed failure rather than a general improvement.
- **Correlated trials.** The ten trials of one task are not independent, and the ten tasks are not a random sample. The Wilson intervals treat the 100 trials of a run as independent and are therefore narrower than the uncertainty about other tasks.
- **One repeat.** A single repeat of the baseline measures run-to-run variation only roughly.
- **Single model and provider.** One model (`z-ai/glm-5.3-flash`) through one provider tag with fallbacks off; nothing transfers to other models. A fixed model identifier does not guarantee immutable upstream weights, and the provider returned no precision field in the first comparison.
- **Sampling.** Temperature 0.2, top_p 1.0, no seed; the runs are sequential over hours, and provider drift remains possible within and between them.
- **Benchmark reviewed by models only**, no human review (see [benchmark_review.md](benchmark_review.md)).

## Decision

Not applicable until the results exist; the first comparison's decision (keep `baseline_agent_v2`) stands and is not changed by this document.

## Student interpretation

(Left to the student: this slot is intentionally empty. It is for the student's own words and is not drafted here.)
