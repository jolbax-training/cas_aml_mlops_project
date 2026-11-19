# Prompt comparison at scale: baseline, revised, baseline repeat (`prompt_comparison_v2`)

Status: the three runs were made on 2026-11-19 and are recorded below, from the saved output in `experiments/evidence_v2/analysis/`. This is the pipeline run at scale: a larger, repeated measurement with the same prompts as the [first comparison](prompt_comparison.md), not proof that the revised prompt improves anything. The first comparison's files are not changed by it. The student's interpretation is not written here (see the last section).

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

Stop and ask the user if the actual charged spend of the v2 runs (summed from the bundles) exceeds CHF 1, if any run ends incomplete, or if the ledger's CHF 10 checkpoint is reached. The worst-case reservation checked before a run (CHF 0.0008197 per attempt, at most 600 attempts per run; about CHF 1.4755 for all three runs) is accepted: it is below the checkpoint and the CHF 15 ceiling. The first comparison charged CHF 0.00275 and CHF 0.00297 for 30 trials each, so about CHF 0.03 was expected for 300 trials. The actual charge was CHF 0.0513362 for the 300 trials (about CHF 0.000171 per trial, against about CHF 0.0000953 per trial in the first comparison, roughly 1.8 times): above the expectation made before the runs and far below the CHF 1 limit. The bundles do not separate pricing, token counts and provider, so no cause is stated.

## Evidence references

Run IDs, bundle digests, MLflow runs and the ledger lines are in [comparison_evidence_v2.md](comparison_evidence_v2.md). All three bundles verify COMPLETE, 100 of 100 planned trials with intact records (`experiments/evidence_v2/analysis/verify.txt`). The runs were made at commit `207e09e8fcb0b16d03f2950f9a4dd52bfa6a5b57`, one run after the other, in the order baseline, revised, baseline repeat; the charged spend of the three runs is CHF 0.0513362 against the stop limit of CHF 1, and the CHF 10 checkpoint was not reached in any run.

## Results (primary metric and diagnostics)

Output of `scale_analysis` and `experiment_cli compare` for the three runs (`experiments/evidence_v2/analysis/scale_analysis.txt`, `scale_analysis.json`, `compare.txt`, `compare.json`). Counts are over the planned denominators (100 trials, 400 hidden checks and 200 edge cases per run); all three runs are complete and headline-eligible, so no denominator was reduced. The Wilson intervals treat the 100 trials of a run as independent.

| Metric | Baseline (run 1) | Revised (run 2) | Baseline repeat (run 3) |
| --- | --- | --- | --- |
| Run ID | `20261119T203431Z-380dc9` | `20261119T204755Z-60994f` | `20261119T210148Z-43a702` |
| Prompt | `baseline_agent_v1` | `baseline_agent_v2` | `baseline_agent_v1` |
| Successful task trials / 100 (primary) | 99/100 (99.0%) | 99/100 (99.0%) | 97/100 (97.0%) |
| Wilson 95% interval of the primary rate | [0.9455, 0.9982] | [0.9455, 0.9982] | [0.9155, 0.9897] |
| Hidden checks passed / 400 | 396/400 (99.0%) | 399/400 (99.8%) | 388/400 (97.0%) |
| Edge cases passed / 200 | 198/200 (99.0%) | 199/200 (99.5%) | 194/200 (97.0%) |
| Tasks passing at least one trial / 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| Tasks passing every trial / 10 | 9/10 (90.0%) | 9/10 (90.0%) | 7/10 (70.0%) |
| Incomplete / ungraded trials | 0 / 0 | 0 / 0 | 0 / 0 |
| Failure labels | `syntax_error` 1 | `wrong_answer` 1 | `contract_error` 1, `syntax_error` 2 |

Per task (successful trials of 10):

| Task | Baseline | Revised | Baseline repeat |
| --- | --- | --- | --- |
| `dictionaries_01` | 10/10 | 10/10 | 10/10 |
| `dictionaries_02` | 10/10 | 10/10 | 10/10 |
| `lists_01` | 10/10 | 10/10 | 10/10 |
| `lists_02` | 9/10 | 10/10 | 9/10 |
| `numeric_logic_01` | 10/10 | 10/10 | 9/10 |
| `numeric_logic_02` | 10/10 | 10/10 | 10/10 |
| `parsing_formatting_01` | 10/10 | 10/10 | 10/10 |
| `parsing_formatting_02` | 10/10 | 10/10 | 10/10 |
| `strings_01` | 10/10 | 9/10 | 9/10 |
| `strings_02` | 10/10 | 10/10 | 10/10 |

| Category (successful trials of 20) | Baseline | Revised | Baseline repeat |
| --- | --- | --- | --- |
| dictionaries | 20/20 (100.0%) | 20/20 (100.0%) | 20/20 (100.0%) |
| lists | 19/20 (95.0%) | 20/20 (100.0%) | 19/20 (95.0%) |
| numeric_logic | 20/20 (100.0%) | 20/20 (100.0%) | 19/20 (95.0%) |
| parsing_formatting | 20/20 (100.0%) | 20/20 (100.0%) | 20/20 (100.0%) |
| strings | 20/20 (100.0%) | 19/20 (95.0%) | 19/20 (95.0%) |

Differences, as reported by `scale_analysis` (second run minus first run):

- **Revised - baseline:** +0 successful trials (+0.0%); gained tasks ['lists_02'], regressed tasks ['strings_01'], 8 tasks unchanged; the two intervals overlap: True (descriptive aid, not a test).
- **Baseline repeat - baseline:** -2 successful trials (-2.0%); gained tasks none, regressed tasks ['numeric_logic_01', 'strings_01'], 8 tasks unchanged; the two intervals overlap: True (descriptive aid, not a test).

Charged CHF summed over the three runs: 0.05133620 (stop limit CHF 1: not exceeded).

## Run-to-run variation and the revised prompt

The baseline-versus-repeat difference is the observed run-to-run variation of one prompt and the yardstick for the baseline-versus-revised difference. Interval overlap is a descriptive aid, not a test, and overlap does not mean that there is no difference.

What the counts show, and nothing beyond them:

- At 10 trials per task, both prompts reached 99 of 100 successful trials, with the same Wilson interval ([0.9455, 0.9982]).
- The repeat of the same baseline prompt reached 97 of 100 (interval [0.9155, 0.9897]), two trials fewer than the first baseline run. Of the ten tasks, 9 passed every trial in the first baseline run and in the revised run, and 7 in the repeat.
- The baseline-versus-revised difference is 0 successful trials; the baseline-versus-repeat difference, between two runs of the same prompt, is -2. The first is smaller in absolute size than the second, so the run-to-run variation observed for one prompt is larger than the difference between the two prompts in this data.
- The first comparison's baseline result (27/30, with `lists_02` at 0/3) is not reproduced at this scale: `lists_02` is 9/10 in both baseline runs. `lists_02` is 10/10 in the revised run; `strings_01`, 3/3 for the baseline and 2/3 for the revised prompt in the first comparison, is 10/10 in the first baseline run and 9/10 in the revised run and in the repeat. The single failed trial of the first baseline run is in `lists_02` and the run has one failure label, `syntax_error`; the first comparison's baseline had three `lists_02` failures (two `syntax_error`, one `contract_error`).

What cannot be concluded:

- No significance claim is made and none is computed. Interval overlap is a descriptive aid, not a test.
- The intervals treat the 100 trials of a run as independent, although the ten trials of one task are correlated; they are narrower than the uncertainty about other tasks.
- One repeat measures run-to-run variation only roughly: two baseline runs are two draws.
- One model through one provider and ten benchmark-informed tasks (the revised prompt was written after reading the baseline failures on these same tasks); nothing here transfers to other models or tasks.
- These runs were made on 2026-11-19 and the first comparison on 2026-11-03, so a change of the provider over time is not separable from a change in the prompt or from sampling.
- The failure labels were not traced to trial-level explanations in this document (see below).

## Efficiency

| Metric | Baseline (run 1) | Revised (run 2) | Baseline repeat (run 3) |
| --- | --- | --- | --- |
| Model calls (= physical attempts; transport retries) | 218 (0) | 217 (0) | 222 (0) |
| Tool attempts | 118 | 117 | 122 |
| Revisions | 1 | 7 | 3 |
| Trials with a failed development check (of them ending in success) | 5 (4) | 8 (7) | 8 (5) |
| Prompt / completion / total tokens | 166,594 / 36,704 / 203,298 | 178,725 / 27,855 / 206,580 | 171,236 / 39,809 / 211,045 |
| Model latency, total (mean per trial), ms | 411,405 (4,114) | 441,089 (4,411) | 426,701 (4,267) |
| Trial wall clock, total (mean per trial), ms | 793,000 (7,930) | 817,000 (8,170) | 805,000 (8,050) |
| Reported cost (USD) | 0.021677 | 0.017932 | 0.023019 |
| Charged (CHF) | 0.01776853 | 0.01469861 | 0.01886906 |
| Reserved before send (CHF) | 0.1787 | 0.1779 | 0.1820 |

Latency and wall clock were measured once per run against a remote provider at different times; the bundles give no basis for attributing differences between runs to the prompt, so no latency claim is made.

## Trace-based explanations

Not examined for this document: the failed trials were not inspected with `trace_inspect show`, so no explanation of any failure, gain or regression is offered; failures are reported by label and task count only. The bundles in `run_bundles_v2/` of the primary checkout allow that inspection later.

## Limitations

- **Benchmark-informed tuning.** The revised prompt was written after reading the baseline failures of the first comparison on these same ten tasks, so any difference is limited to these tasks and may reflect fitting to the observed failure rather than a general improvement.
- **Correlated trials.** The ten trials of one task are not independent, and the ten tasks are not a random sample. The Wilson intervals treat the 100 trials of a run as independent and are therefore narrower than the uncertainty about other tasks.
- **One repeat.** A single repeat of the baseline measures run-to-run variation only roughly.
- **Single model and provider.** One model (`z-ai/glm-5.3-flash`) through one provider tag with fallbacks off; nothing transfers to other models. A fixed model identifier does not guarantee immutable upstream weights, and the provider returned no precision field in the first comparison.
- **Sampling.** Temperature 0.2, top_p 1.0, no seed; the three runs were sequential over about 41 minutes (20:34 to 21:15 UTC on 2026-11-19), and provider drift remains possible within and between them.
- **Benchmark reviewed by models only**, no human review (see [benchmark_review.md](benchmark_review.md)).

## Decision

No decision is recorded here. The first comparison's decision (keep `baseline_agent_v2`, a reasoned keep on the targeted fix and not a claim of improvement) stands and is not changed by this document.

## Student interpretation

**EMPTY, to be written by the student.** This slot is intentionally empty. It is for the student's own words and is not drafted here.
