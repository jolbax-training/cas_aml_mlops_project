# Tasks

## 1. Experiment configuration and overwrite guards (offline)

- [ ] 1.1 Add `experiment_id` and `trials_per_task` parameters (defaults: the v1 constants) to `build_config` and `config_drift` in `src/codegen_eval/experiment.py`, and `--experiment-id` / `--trials-per-task` to `build-config` in `experiment_cli.py`. Verify: `tests/test_experiment.py` asserts `build_config()` without arguments equals the recorded v1 `settings`, `benchmark`, `variants` and `schedule`, and that `build-config --check` on `experiments/prompt_comparison_v1.json` still passes.
- [ ] 1.2 Make `write_config` refuse to overwrite a file for another experiment and `write_settings_freeze` refuse to overwrite a freeze record for another experiment. Verify: tests show each refusal names the path and both ids and leaves the target byte-identical, and that rewriting the same experiment's file still works.
- [ ] 1.3 Add `/run_bundles_v2/` and `/experiments/evidence_v2/` to `.gitignore`. Verify: `git check-ignore -v run_bundles_v2/x experiments/evidence_v2/x` names both rules, and `git check-ignore run_bundles/x experiments/evidence/x` still matches the old ones.
- [ ] 1.4 Generate `experiments/prompt_comparison_v2.json` with the command in design.md, Decision 1. Verify: `build-config --check --config experiments/prompt_comparison_v2.json` passes; a test loads it and asserts 100 schedule entries, ten trials per task, `task_major`, experiment id `prompt_comparison_v2`, and `settings`, `benchmark` and `variants` equal to v1's.
- [ ] 1.5 Prove v1 data is untouched. Verify: `git diff main --stat` lists no change to `experiments/prompt_comparison_v1.json`, `docs/prompt_comparison.md`, `docs/comparison_evidence.md`, `openspec/changes/archive/**` or `experiments/evidence/**`; the checksum listing of `$P/run_bundles` and `$P/experiments/evidence` taken before and after the whole change is identical (record both listings in the report).

## 2. Analysis (offline)

- [ ] 2.1 Implement `src/codegen_eval/scale_analysis.py` (design.md, Decision 5): Wilson interval, per-run metrics reused from `comparison.py`, per-task successes out of ten, baseline-vs-revised and baseline-vs-repeat with comparability rules, text and `--json` output. Verify: `tests/test_scale_analysis.py` covers the interval for 0/100, 50/100, 100/100 and 29/30 against the formula, fixture bundles for three runs (counts, per-task, differences, interval overlap), an incomplete run and a non-comparable pair, and byte-identical output on two calls.
- [ ] 2.2 Test that the analysis writes nothing and reads nothing outside the given bundle directory and configuration (no ledger path, no network): run it under a tmp directory with an unreadable-ledger sentinel and `socket` blocked. Verify: the test passes and the bundle directory listing is unchanged after the run.
- [ ] 2.3 Document the commands for the three-run workflow in `README.md` and `docs/demo.md` (one short section each, no existing text changed). Verify: the commands match `--help` of `experiment_cli`, `trace_inspect`, `mlflow_tracking` and `scale_analysis`.

## 3. Documents (written before and after the runs)

- [ ] 3.1 Write `docs/prompt_comparison_v2.md` as a protocol (design, A-B-A rationale, fixed settings, stop rules, claim limits including benchmark-informed tuning, correlated trials, one repeat, single model/provider) with result sections marked not yet recorded, and `docs/comparison_evidence_v2.md` as the identifier table with empty rows. Verify: neither contains an invented number; `.venv/bin/pytest -q` and `build_work_log.py --check` pass.
- [ ] 3.2 Update `docs/work_log.toml` and `docs/progress.md` for this change (planned, not results). Verify: `.venv/bin/python scripts/build_work_log.py --check` passes and v1 entries are not edited.

## 4. Checks on the implementation (offline)

- [ ] 4.1 Run `.venv/bin/pytest -q`, `.venv/bin/python scripts/build_work_log.py --check` and `openspec validate scale-prompt-comparison --strict`; run `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` in the foreground. Verify: all pass and the counts are recorded in `docs/progress.md`.

## 5. Paid runs (coordinator; needs the key, Podman, the ledger, the user's confirmation of the stop rules)

- [ ] 5.1 Confirm with the user before run 1: stop threshold interpretation (design.md, open question 1) and storage paths (open question 2). Reason unchecked: user judgment.
- [ ] 5.2 Once, at the final commit: `build-config --check`, `record-probes` and `freeze-settings` with `--evidence $EV` (design.md, Decision 8). Verify: `check` for the baseline prints `all preconditions hold`. Reason unchecked: needs the final commit and Podman on the coordinator's machine.
- [ ] 5.3 Run 1, baseline: `check`, `run --no-tracking`, `trace_inspect verify` (COMPLETE, 100 of 100). Stop and ask the user on an incomplete run, a non-zero exit or a reached ledger checkpoint. Reason unchecked: paid calls.
- [ ] 5.4 Run 2, revised: same sequence. Reason unchecked: paid calls.
- [ ] 5.5 Run 3, baseline repeat with `--allow-rerun`: same sequence. Reason unchecked: paid calls.
- [ ] 5.6 Record the three bundles in MLflow experiment `codegen-eval-prompt-comparison-v2` and read back counts. Reason unchecked: needs the MLflow service.
- [ ] 5.7 Run `experiment_cli compare` and `scale_analysis` (text and JSON) on the three runs and save the outputs for the document. Reason unchecked: needs the runs.

## 6. Results and review (after the runs)

- [ ] 6.1 Fill the result sections of `docs/prompt_comparison_v2.md` and the identifier table of `docs/comparison_evidence_v2.md` from the compare and analysis output, with the baseline-vs-repeat comparison next to baseline-vs-revised and no claim beyond the intervals. Verify: every number is traceable to the saved output; the student's interpretation slot is left empty. Reason unchecked: needs the runs.
- [ ] 6.2 Repeat the v1 data-safety listing of 1.5 after the runs. Verify: identical checksums for `$P/run_bundles` and `$P/experiments/evidence`; the ledger is only appended (line count grew, earlier lines unchanged, checked by the coordinator through the CLI's own output, not by a script of this change). Reason unchecked: needs the runs.
- [ ] 6.3 Decide, with the user, whether to merge, and how v2 reaches the presentation and report (a later change). Reason unchecked: user judgment.
