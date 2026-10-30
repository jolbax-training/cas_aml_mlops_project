# Tasks

All tasks are unstarted planning items. Timeboxes: day 3 baseline/inspection/revision/revised run (4h); day 4 comparison write-up within the comparison/report slot (2h). Requires changes 1, 3, 4, 5, and 7 verified (and 2 transitively).

## 1. Preconditions

- [ ] 1.1 Verify and record preconditions: isolation/scoring-integrity probes passing, benchmark version/hash frozen, model settings frozen with retained smoke trace, MLflow service verified or the later-upload path from retained bundles confirmed (a tracking outage does not block runs), and ledger projection within CHF 15.
- [ ] 1.2 Version the baseline prompt and an experiment configuration listing variant, benchmark version, settings hash, and the 10 × 3 schedule.

## 2. Baseline

- [ ] 2.1 Run the baseline schedule through the ledger, each trial a fresh conversation; verify completeness against every scheduled task/trial ID.
- [ ] 2.2 Record the baseline in MLflow (or retain for later upload if tracking is down) and note ledger totals and any checkpoint.
- [ ] 2.3 Inspect baseline failures and selected traces; document one intended prompt change and its motivation, stating plainly if there were no failures.

## 3. Revised run

- [ ] 3.1 Version the revised prompt, confirm all other settings unchanged, and run the identical schedule through the ledger.
- [ ] 3.2 Verify completeness, record in MLflow, and label any incomplete run without reducing denominators.

## 4. Comparison and decision

- [ ] 4.1 Compute the primary metric and diagnostics for both variants with counts and rates.
- [ ] 4.2 Write the reviewed comparison Markdown: evidence references, metrics, trace-based explanations of gains/regressions/unchanged outcomes, efficiency, required limitations, and the keep/reject decision. Leave any student interpretation to the student.
- [ ] 4.3 Update `docs/progress.md` with run IDs, versions, observed results, ledger totals, and limitations; register the comparison summary as a work-log source and rebuild the report.
