# Tasks

All tasks are done: preconditions, offline tooling, the baseline run (`20261103T053309Z-280182`), the revised run (`20261103T095324Z-d25905`), the comparison write-up (`docs/prompt_comparison. md`) and the user's keep-v2 decision. The student's own interpretation is left to the student. Timeboxes: day 3 baseline/inspection/revision/revised run (4h); day 4 comparison write-up within the comparison/report slot (2h). Requires changes 1, 3, 4, 5, and 7 verified (and 2 transitively).

## 1. Preconditions

- [x] 1.1 Verify and record preconditions: isolation/scoring-integrity probes passing, benchmark version/hash frozen, model settings frozen with retained smoke trace, MLflow service verified or the later-upload path from retained bundles confirmed (a tracking outage does not block runs), and ledger projection within CHF 15. (Evidence in `docs/progress.md`, 2026-11-03: 67 probes passed, freeze check matches, settings frozen with smoke bundle `20261103T050806Z-30949f`, later upload confirmed, worst case CHF 0.295 for both variants.)
- [x] 1.2 Version the baseline prompt and an experiment configuration listing variant, benchmark version, settings hash, and the 10 × 3 schedule. (`experiments/prompt_comparison_v1.json`: baseline `baseline_agent_v1` with its hash, revised prompt deliberately unset until baseline failures are inspected, `build-config --check` guards drift. Tooling: `codegen_eval.experiment`, `experiment_cli`.)

## 2. Baseline

- [x] 2.1 Run the baseline schedule through the ledger, each trial a fresh conversation; verify completeness against every scheduled task/trial ID.
- [x] 2.2 Record the baseline in MLflow (or retain for later upload if tracking is down) and note ledger totals and any checkpoint. (MLflow run `930a188254d34d279a88a7613ea55518`; ledger CHF 0.001123954886 -> 0.003876933730; no CHF 10 checkpoint.)
- [x] 2.3 Inspect baseline failures and selected traces; document one intended prompt change and its motivation, stating plainly if there were no failures.

## 3. Revised run

- [x] 3.1 Version the revised prompt, confirm all other settings unchanged, and run the identical schedule through the ledger. (`baseline_agent_v2`; run `20261103T095324Z-d25905`, ledger CHF 0.003876933730 -> 0.0068475273497; `build-config --check` matched, `compare` reports evaluator code and prompt files otherwise identical.)
- [x] 3.2 Verify completeness, record in MLflow, and label any incomplete run without reducing denominators. (COMPLETE, 30 of 30 planned trials, digest `210fb4bb...91ea39`; MLflow run `bcddf5c9561c43129504555b020a7557`; no incomplete run.)

## 4. Comparison and decision

- [x] 4.1 Compute the primary metric and diagnostics for both variants with counts and rates. (`experiment_cli compare` on the two complete runs: 27/30 versus 29/30; output reproduced in `docs/prompt_comparison.md`.)
- [x] 4.2 Write the reviewed comparison Markdown: evidence references, metrics, trace-based explanations of gains/regressions/unchanged outcomes, efficiency, required limitations, and the keep/reject decision. Leave any student interpretation to the student. (`docs/prompt_comparison.md`; decision keep v2; the student-interpretation slot is left empty.)
- [x] 4.3 Update `docs/progress.md` with run IDs, versions, observed results, ledger totals, and limitations; register the comparison summary as a work-log source and rebuild the report.
