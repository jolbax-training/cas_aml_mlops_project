# Prompt comparison: baseline versus revised (`run-prompt-comparison`)

Reviewed 2026-11-03 from the coordinator's own commands (Mac arm64, primary checkout) and from read-only inspection of the retained bundles. Bundles are under `run_bundles/` (Git-ignored, retained); the experiment configuration is `experiments/prompt_comparison_v1.json`; the spending ledger is outside Git. Numbers below are the output of `experiment_cli compare --baseline 20261103T053309Z-280182 --revised 20261103T095324Z-d25905` (text and JSON), and trace excerpts come from `trace_inspect show`. This is a comparison of two prompts on ten tasks with one model, not a general model-quality result.

## Evidence references

| | Baseline | Revised |
| --- | --- | --- |
| Run ID | `20261103T053309Z-280182` | `20261103T095324Z-d25905` |
| Bundle | `run_bundles/20261103T053309Z-280182` | `run_bundles/20261103T095324Z-d25905` |
| Bundle digest (sha256 of `manifest.json`) | `1a2e964fce29acca6f8ab223dab1a56e260b3624955575f6297f2d8b0a9aced1` | `210fb4bbba433c87ffd4e4918cc1c3f39e8d504e0a443f203b674b52f091ea39` |
| Completeness (`trace_inspect verify`) | COMPLETE, 30 of 30 planned trials with intact records | COMPLETE, 30 of 30 planned trials with intact records |
| MLflow run (http://127.0.0.1:5001, experiment 1) | `930a188254d34d279a88a7613ea55518` | `bcddf5c9561c43129504555b020a7557` |
| Prompt | `baseline_agent_v1`, sha256 `bcf5e70c8d951e53440e140bf971e72ed8769ce5ad4307668e9ac7cb82d31c51` | `baseline_agent_v2`, sha256 `f7f797ed4215ea63df4deddaa867a30c6d554467a3d641a0330efa7c26905c1b` |
| Ledger (CHF) | 0.001123954886 -> 0.003876933730 | 0.003876933730 -> 0.0068475273497 |

Both runs ran with `--no-tracking` and were recorded in MLflow afterwards from the retained bundles. The CHF 10 checkpoint was not reached in either run; both runs are complete, so both are headline-eligible and no denominator was reduced.

Fixed across both runs (from `experiments/prompt_comparison_v1.json` and the bundle manifests):

- Benchmark: `data/benchmark_v1.json`, version 1, sha256 `d75c06ae3a8d8d98fbe2bdeb8ec36e4d80f6279c0040a394aee2247a20f556b6`, freeze content hash `a001191f288d1140bd62c7f38932a1bd9900e230a9ad2f5a7d75a23ab33aafee`.
- Experiment `prompt_comparison_v1`: configuration sha256 `465c76e893ca6c14e31de0a082a3b9027e6bcb95c4b09389d2ba43dca7c255dd`, schedule sha256 `2321794e750983439ca52eb5d7980b1dac69fcfa5ea13ae46ca19de271a1274c`, ten tasks x three trials, `task_major` order.
- Settings hash `4c3b3b351075142e9db945a7eacb64fe47fef689e83f212957dec72efe0d1c9e`; model config `openrouter_glm_v1` (hash `4fe5bf3e6d9840e2ae7fdac2add3867698ac64022f962d56c30e49206e9e9908`): model `z-ai/glm-5.3-flash`, provider pin `open-inference/fp4` with fallbacks off, temperature 0.2, top_p 1.0, reasoning effort low, max 2000 output tokens; agent limits hash `e1359505d82677857d06b3b8220eb85e1a825593d7833bc1faaeaaa84366ca7e` (at most 4 model calls and 3 tool attempts); execution limits hash `dfa3cca881cfe5386d441633dd5aba11e9c67f47864118e3663a0fcbc94f4b30`; container image `docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5` (arm64).
- Settings unchanged except the prompt: `build-config --check` matched before the revised run. `compare` reports the evaluator code and prompt files as otherwise identical; the only differences it lists are `evaluator_revision` (`4f96e17ca2ab59a8172b7f2dea1412831671cf53` vs `afb19fc510b3613cf721816f8d426ab2047d2f93`) and `evaluator_source_sha256` (`4567eb9f...` vs `763ce009...`), which it attributes to the revised prompt file being added.

## The one intended change

`baseline_agent_v2.md` differs from `baseline_agent_v1.md` by one sentence, motivated by the baseline failures (see [progress.md](progress.md), 2026-11-03 entry on task 2.3): "If a check fails because your expected value was wrong, fix the check or ignore it, but do not mention it: even then, your final message starts directly with the function's `def` line or its imports." All three baseline failures were `lists_02`: a correct `rotate_left` was submitted together with an explanation of a wrong self-written check, which the grader rejected (`syntax_error` for prose before the code, `contract_error` for a Markdown fence).

## Results (primary metric and diagnostics)

Counts over the planned denominators; rates are shown with counts.

| Metric | Baseline | Revised | Difference |
| --- | --- | --- | --- |
| Successful task trials / 30 (primary) | 27/30 (90.0%) | 29/30 (96.7%) | +2 trials (+6.7 points) |
| Hidden checks passed / 120 | 108/120 (90.0%) | 119/120 (99.2%) | +11 |
| Edge cases passed / 60 | 54/60 (90.0%) | 59/60 (98.3%) | +5 |
| Tasks passing at least one trial / 10 | 9/10 (90.0%) | 10/10 (100.0%) | +1 task |
| Tasks passing every trial / 10 | 9/10 (90.0%) | 9/10 (90.0%) | 0 |
| Incomplete / ungraded trials | 0 / 0 | 0 / 0 | |
| Failure labels | `syntax_error` 2, `contract_error` 1 | `wrong_answer` 1 | |

Categories (successful trials of six): dictionaries 6/6 and 6/6; lists 3/6 (50.0%) and 6/6 (100.0%); numeric_logic 6/6 and 6/6; parsing_formatting 6/6 and 6/6; strings 6/6 and 5/6 (83.3%).

Per task: gained `lists_02` (0/3 -> 3/3); regressed `strings_01` (3/3 -> 2/3); unchanged and 3/3 in both runs: `dictionaries_01`, `dictionaries_02`, `lists_01`, `numeric_logic_01`, `numeric_logic_02`, `parsing_formatting_01`, `parsing_formatting_02`, `strings_02` (eight tasks).

## Efficiency

| Metric | Baseline | Revised |
| --- | --- | --- |
| Model calls (= physical attempts; 0 transport retries in both) | 65 | 60 |
| Tool attempts | 35 | 30 |
| Revisions | 1 | 0 |
| Trials with a failed development check | 4 (1 of them ended in success) | 0 |
| Prompt / completion / total tokens | 49,947 / 9,664 / 59,611 | 47,820 / 9,865 / 57,685 |
| Model latency, total (mean per trial) | 470,969 ms (15,699 ms) | 650,239 ms (21,675 ms) |
| Trial wall clock, total (mean per trial) | 574,000 ms (19,133 ms) | 750,000 ms (25,000 ms) |
| Reported cost (USD) | 0.00335852 | 0.003624001 |
| Charged (CHF) | 0.00275 | 0.00297 |
| Reserved before send (CHF) | 0.0532805 | 0.049182 |

The revised run used fewer model calls and tool attempts and slightly fewer tokens, but its charged cost and its measured latency are higher (charged CHF 0.00297 versus 0.00275; mean model latency per trial 21.7 s versus 15.7 s). Latency was measured once per variant, at different times, against a remote provider; the bundles give no basis for attributing the difference to the prompt, so no latency claim is made.

## Trace-based explanations

**Gain, `lists_02` (0/3 -> 3/3).** In the baseline each trial wrote a check with a wrong expected value, e.g. t1 expected `[1, 2, 3]` for rotating `[1, 2, 3]` by 7 (the actual result `[2, 3, 1]` is correct), the check failed, and the final message began "All checks pass (the one "failure" was my incorrect expectation ...)" followed by the code. The submitted source was that whole message, which graded `syntax_error` with all four checks "not executed" (t3 the same; t2 `contract_error` because of a ```python fence). In the revised run all three `lists_02` trials made one model call, no tool attempt, and submitted the bare function (`rotate_left` with `k %= len(items)`), passing all four hidden checks. Two things follow and are kept separate. (a) The failure label that disappeared is exactly the targeted one: the revised run has no `syntax_error` and no `contract_error`, and no trial of the revised run submitted explanation or fences. (b) The trace does not show the added sentence working on its trigger: in these three trials no check was written, so no self-inflicted check failure occurred for the sentence to apply to. The tasks passed because the model went straight to the submission. Why it did so (the extra sentence, sampling variation at temperature 0.2 without a fixed seed, or both) is not determined by this data.

**Regression, `strings_01` (3/3 -> 2/3).** `strings_01-t2` (revised) was `wrong_answer`: ordinary checks `strings_01_a`, `_b` and edge check `_c` passed, edge check `strings_01_d` failed (actual 0). The final source normalised the text with NFD and counted only characters in the lowercase string `'aeiou'` without case-folding, while the instruction says "without regard to case". The model's one development run used four lowercase checks (`café`, `über`, `æø`, `é`), all of which passed, so it never exercised an uppercase input. `strings_01-t1` and `-t3` succeeded. The failure is a case-handling mistake in the algorithm and has no connection to the added sentence, which concerns the final message format; there is no evidence in the trace that the v2 prompt caused it, and it is one trial out of three.

**Unchanged outcomes.** Eight tasks were 3/3 under both prompts, so the added sentence changed no pass/fail outcome there. The aggregate efficiency drop (65 -> 60 model calls, 35 -> 30 tool attempts) comes from fewer tool attempts and revisions after failed checks (four baseline trials had a failed development check; no revised trial did), consistent with, but not proof of, the prompt's effect.

## Limitations

- **Small n.** Three trials per task and 30 trials per variant do not establish precise reliability. The +2 difference (27 -> 29) is two trials; with these counts, a different draw of the same runs could shift or reverse it, and no confidence interval or significance claim is made.
- **Benchmark-informed tuning.** The one prompt change was written after reading the baseline failures on these same ten tasks, so any gain is limited to these tasks and may reflect fitting to the observed failure rather than a general improvement.
- **Single model and provider.** One model (`z-ai/glm-5.3-flash`) through one provider tag (`open-inference/fp4`, fallbacks off); nothing here transfers to other models.
- **Fixed sampling, no repeated runs.** Temperature 0.2, top_p 1.0, no seed; each variant was run once, so run-to-run variation of the whole schedule is unmeasured. Order was fixed (`task_major`, baseline first and revised later), so drift of the provider over the hours between the runs is not separable from the prompt.
- **Provider precision not returned.** The provider returned no precision or quantization field on any attempt (see [smoke_evidence.md](smoke_evidence.md)); precision is pinned only by the provider tag, and a fixed model identifier does not guarantee immutable upstream weights.
- **Evaluator revision differs.** The two runs record different evaluator revisions and source hashes; `compare` reports the evaluator code and prompt files as otherwise identical, and the difference is the added prompt file.
- **Benchmark reviewed by models only**, no human review (see [benchmark_review.md](benchmark_review.md)).

## Decision: keep `baseline_agent_v2`

Decision of the user, 2026-11-03: **keep v2**. Recorded reasons:

1. It removes exactly the failure mode it targeted: explanation or fences in the final message after a self-inflicted check failure. `lists_02` went from 0/3 to 3/3 and the revised run has no `syntax_error` or `contract_error` labels. (See the trace note above: in the revised `lists_02` trials no check was run at all, so the sentence's effect on its trigger was not observed directly.)
2. Nothing indicates that the single `strings_01` miss is caused by v2: it is a case-folding wrong answer unrelated to the added sentence.
3. With 30 trials per variant, a +2 difference (27 -> 29) cannot establish a reliable overall improvement. The decision is a reasoned keep on the targeted fix, not a claim of improvement.
4. Efficiency: model calls 65 -> 60, tool attempts 35 -> 30, charged CHF 0.00275 versus 0.00297 (reported as measured; the charged cost is slightly higher in the revised run, see the efficiency table).

## Student interpretation

(Left to the student: this slot is intentionally empty. It is for the student's own words and is not drafted here.)
