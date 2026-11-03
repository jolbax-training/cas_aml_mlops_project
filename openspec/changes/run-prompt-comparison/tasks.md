# Tasks

The preconditions, the offline experiment tooling, and the baseline run (`20261103T053309Z-280182`, inspected, recorded in MLflow) are done; the revised run, the comparison, and every task that needs a paid run or the user's judgment stay open. Timeboxes: day 3 baseline/inspection/revision/revised run (4h); day 4 comparison write-up within the comparison/report slot (2h). Requires changes 1, 3, 4, 5, and 7 verified (and 2 transitively).

## 1. Preconditions

- [x] 1.1 Verify and record preconditions: isolation/scoring-integrity probes passing, benchmark version/hash frozen, model settings frozen with retained smoke trace, MLflow service verified or the later-upload path from retained bundles confirmed (a tracking outage does not block runs), and ledger projection within CHF 15. (Evidence in `docs/progress.md`, 2026-11-03: 67 probes passed, freeze check matches, settings frozen with smoke bundle `20261103T050806Z-30949f`, later upload confirmed, worst case CHF 0.295 for both variants.)
- [x] 1.2 Version the baseline prompt and an experiment configuration listing variant, benchmark version, settings hash, and the 10 × 3 schedule. (`experiments/prompt_comparison_v1.json`: baseline `baseline_agent_v1` with its hash, revised prompt deliberately unset until baseline failures are inspected, `build-config --check` guards drift. Tooling: `codegen_eval.experiment`, `experiment_cli`.)

## 2. Baseline

- [x] 2.1 Run the baseline schedule through the ledger, each trial a fresh conversation; verify completeness against every scheduled task/trial ID.
- [x] 2.2 Record the baseline in MLflow (or retain for later upload if tracking is down) and note ledger totals and any checkpoint. (MLflow run `930a188254d34d279a88a7613ea55518`; ledger CHF 0.001123954886 -> 0.003876933730; no CHF 10 checkpoint.)
- [x] 2.3 Inspect baseline failures and selected traces; document one intended prompt change and its motivation, stating plainly if there were no failures.

## 3. Revised run

- [ ] 3.1 Version the revised prompt, confirm all other settings unchanged, and run the identical schedule through the ledger.
- [ ] 3.2 Verify completeness, record in MLflow, and label any incomplete run without reducing denominators.

## 4. Comparison and decision

- [ ] 4.1 Compute the primary metric and diagnostics for both variants with counts and rates. (Tooling ready and tested offline: `experiment_cli compare`; stays open until it is run on two real, complete runs.)
- [ ] 4.2 Write the reviewed comparison Markdown: evidence references, metrics, trace-based explanations of gains/regressions/unchanged outcomes, efficiency, required limitations, and the keep/reject decision. Leave any student interpretation to the student.
- [ ] 4.3 Update `docs/progress.md` with run IDs, versions, observed results, ledger totals, and limitations; register the comparison summary as a work-log source and rebuild the report.
