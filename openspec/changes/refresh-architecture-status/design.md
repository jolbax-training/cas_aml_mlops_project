## Context

The paid phase finished after the diagrams were drawn (diagrams dated 2026-10-31 to 2026-11-01, base commit `078130a` or `37968d8`). Statuses use three labels with a text label on every box: `IMPLEMENTED`, `PARTIAL: NO LIVE RUN YET`, `PENDING`. The `.drawio.svg` files hold uncompressed draw.io XML in the root `content` attribute and a rendered SVG; every rendered group carries `data-cell-id`, and existing tests already require the embedded labels to equal the rendered labels. `work_log_architecture.svg` is a hand-written SVG whose boxes carry class `arch-impl`, `arch-part` or `arch-plan`. `report/` is generated and Git-ignored.

## Decisions

### D1: Statuses follow cited evidence, with the vocabulary kept
Keep the three labels and the status key, since they will be needed again. Add one label, `EXTERNAL`, for OpenRouter only: it is a third-party service and cannot be "implemented"; its phase-2 marking and dashed outline stay. Evidence mapping (a row whose phrase cannot be found keeps its status and is reported, not guessed):

| Component(s) | Old | New | Evidence file and phrase |
| --- | --- | --- | --- |
| `openrouter_client.py`, `openrouter_config.py`, `model_configs/`, `openrouter_cli.py` | PARTIAL | IMPLEMENTED | `docs/smoke_evidence.md`: "Calibration and settings freeze" |
| `ledger.py`, `~/.codegen_eval/spend_ledger.jsonl` | PARTIAL | IMPLEMENTED | `docs/smoke_evidence.md`: "Ledger and projection"; `docs/prompt_comparison.md`: "Ledger (CHF)" |
| `experiment.py`, `experiment_cli.py`, `run_recording.py` | PARTIAL | IMPLEMENTED | `docs/comparison_evidence.md`: "Both bundles verify as COMPLETE" |
| `summary.py`, `comparison.py` | PARTIAL | IMPLEMENTED | `docs/prompt_comparison.md`: "Results (primary metric and diagnostics)" |
| `mlflow_tracking.py`, MLflow tracking store, `mlflow_data/`, MLflow service container | PARTIAL | IMPLEMENTED | `docs/progress.md`: "60 of 60 traces read back after `--retrace`" (checklist row 6). The sources entry must not use the "read-only verification" wording of `docs/comparison_evidence.md:14`, which that note supersedes (D7). |
| reviewed result summaries | PENDING | IMPLEMENTED | `docs/prompt_comparison.md`: "Decision of the user, 2026-11-03" |
| OpenRouter (external) | PENDING, "no live call" | EXTERNAL, phase 2, used | `docs/smoke_evidence.md`, `docs/prompt_comparison.md` |
| CI, required checks | IMPLEMENTED | unchanged | `docs/ci_evidence.md` |

Limits stay in the twins, not in the boxes, and carry no numbers beyond those the evidence files hold: the main-run evidence is a 30-trial pilot per variant and claims no improvement (`docs/prompt_comparison.md` decision, point 3); the student interpretation in `docs/prompt_comparison.md` is intentionally empty and user-only, so it stays stated as open in the twin. No figure or twin says that any trace is unreadable: all 60 of 60 traces read back after the fix `044c8d4`..`6deb36c` and `record --retrace` (`docs/progress.md` checklist row 6 and the 2026-11-06 fix entry).

### D2: Stale text inventory
Task 1.1 re-greps (case-insensitive) and judges each hit; counts in this list are indicative only. Judgement categories: stale status (fix), code semantics (keep), history (keep).

- `docs/work_log_architecture.svg`: `<desc>` ("tested offline only, with no live call yet"), the `PARTIAL` and `PENDING` labels, "tested offline; no live call yet", "offline tooling done, no paid run", and the legend text (lines near 164-166: "built, no live model run yet", "Pending: evidence does not exist yet (dashed)"). The legend keeps the three swatches as the reserved vocabulary and is reworded so it no longer says any box is currently in that state.
- `docs/work_log_architecture.md`: "as of 2026-10-31"; the three-label explanation (line 1); step 2 ("No live model call has been made"); step 6 and the MLflow step ("no live model or comparison run has been recorded", "the baseline-versus-revised comparison itself has not run"); the reviewed-summaries step ("Pending ... not invented here"); the closing sentence about "sections ... labelled pending", checked against `docs/work_log.toml` (it has zero pending sections) instead of removed blindly.
- `docs/architecture_logical.md` and `.drawio.svg`: every `NO LIVE RUN YET` and `PENDING` label in the twin and the model; "PHASE 2: no live call has been made"; "It has not been run live" (`openrouter_cli.py`); "the comparison has not run"; "not yet run"; "only a fixture bundle recorded so far"; the section title "phase 2 pieces, built offline only"; the status-key box and its twin line. Kept as code semantics: "FixtureClient used by all tests today" (the fixture client still stands in for the model in every test).
- `docs/architecture_physical.md` and `.drawio.svg`: the three `PARTIAL` labels in the model and the matching twin items plus the status-key line; line 1 ("Phase 1 is everything implemented today", "No live model call, comparison run, or spend exists"); line 21 ("No live call has been made yet"); "no live spend has happened"; the "as of 2026-11-01 ... `078130a`" line.
- `docs/run_flow_activity.md` and `.drawio.svg`: line 5 ("The revised prompt is unset in `experiments/prompt_comparison_v1.json` today, so a `revised` run is refused by the `variant_prompt` check until the human writes it"; false now, the revised prompt is set; reword to the current state and keep the statement that the check refuses a variant whose prompt is unset); the lane status table; `EXTERNAL, PHASE 2, PENDING`; node `l4o` ("no live call has been made", twin line 35); node `l16` ("reviewed result summary (PENDING)", a purple action node: text-only change); the title text "no live run has happened"; the "verified against ... at commit" line only if it is still stale. Kept: "planned trials", "stop, later trials not run" (code semantics).
- `docs/run_flow_sequence.md` and `.drawio.svg`: participants `rr`, `oc`, `lg`, `ml` (PARTIAL) and `or` (PENDING); the title text "no live run has happened"; the "verified against ... at commit" line.
- Outside the nine files, same class, minimal edits: `docs/demo.md:86`; `README.md:5` ("no live model run or comparison result exists yet"), `:48` ("there is no live client yet"), `:124` (heading "the baseline has run, the revised run has not"), `:193` (legend description; keep the yellow swatch sentence only as "reserved for components built offline with no live run yet"); the "Current status" section of `docs/progress.md` (D8); `docs/comparison_evidence.md:14` (D7).
- Not edited: `docs/project_spec.md` (the specification and plan, not a status report; its "planned" wording is the plan as agreed); dated `docs/progress.md` entries; archived changes; `docs/learning_journal.md`.

### D3: Editing the `.drawio.svg` files
draw.io desktop is not needed. The files are plain XML, the rendered nodes carry `data-cell-id`, and the existing tests compare embedded labels with rendered text, so a scripted edit of both parts is safe. One throwaway script (not committed, kept in the session scratchpad) works from an explicit per-file, per-cell table, and locates rendered nodes by `data-cell-id`, not by geometry:

| File | Cells (embedded and rendered) |
| --- | --- |
| logical | `c5` (OpenRouter: text and tag only, keeps `dashed=1`), `c6`, `c9`, `c10`, `c18`, `c20`, `c21`, `c22`, `c23` (text and fill), `c25` (text, fill, drops the dash), `c26` (status key text) |
| physical | `c7`, `c8`, `c14`, `c17` (text, fill; the status key included) |
| sequence | title, `p_rr`, `p_oc`, `p_lg`, `p_or` (keeps `dashed=1` and its tags), `p_ml` (text only: their fills are `#E0EFFF` or `#EEF2F6` with stroke width 2) |
| activity | title, `lane_H`, `lane_O` and `l4o` (keep the dash and tags), `lane_D`, `l16` (text only) |

The cell ids are the proposal-time reading; the script asserts that every id exists and aborts otherwise. Style rules: the colour and stroke change applies only to cells whose style has `fillColor=#FFF1B8` (to `#E0EFFF`, matching the rendered `fill` and the `light-dark(...)` fill in `style`) and to logical `c25` (it loses `dashed=1;dashPattern=...` and takes the implemented stroke width and fill). Every OpenRouter cell keeps `dashed=1`: that dash is the external/phase-2 marking the main spec and `tests/test_run_flow_diagrams.py` (line near 246) require. Run-flow lanes and lifelines carry status by text only, so no colour rule is applied to them. The script asserts each replacement count and aborts without writing on a mismatch. New labels are never longer than the old ones, so no layout changes; a label that would be longer is shortened. The header comment "Do not edit this file with editors other than draw.io" stays true for later hand edits, and the files remain editable in draw.io. Verification: the existing embedded-equals-rendered tests, the new status test (D4), the sanitizer tests in `tests/test_work_log_diagrams.py` (which strip `data-cell-id` for the report), and a browser look at the rebuilt report by the coordinator.

### D4: The check
`docs/architecture_status_sources.toml` lists components with `status`, `evidence` (repo-relative file) and `phrase` (must occur in that file), plus the sentence each twin must carry about the completed runs. New `tests/test_architecture_status.py`, offline, asserts:
1. each component's status in the logical diagram, the physical diagram, the sequence participants, the activity lane table and the work-log figure equals the TOML;
2. every evidence file exists and contains its phrase;
3. a stale-phrase list, matched case-insensitively, does not occur in the nine files, the `README.md`, `docs/demo.md` lines under check, and the "Current status" section of `docs/progress.md`. List: `NO LIVE RUN`, `no live call`, `no live model`, `no live run`, `no live or real run`, `no live spend`, `has not been run live`, `has not run`, `built offline only`, `no paid`, `not yet run`, `does not exist yet`, `only a fixture`, `no live client`, `unset`, `until the human writes`, and `PENDING` on a component the TOML marks done. An explicit allowlist, each entry with a reason, covers the status-key definitions, the legend swatch text kept as reserved vocabulary, and the activity sentence that describes the `variant_prompt` refusal for an unset prompt;
4. a positive assertion per file that the TOML's completed-run sentence is present, so the test is not grep-only;
5. a component marked `open` stays labelled as such.
Existing assertions that pin the stale sentences are replaced by the inverse assertion (the new sentence is present, the stale one absent): `tests/test_architecture_diagrams.py:160-161` ("No live", "no live" in the physical twin), `tests/test_run_flow_diagrams.py:257` and `:548` ("no live run has happened" in both run-flow twins and both rendered work-log sections); and every assertion that hard-codes `STATUSES` or the three labels (`test_architecture_diagrams.py`, `test_run_flow_diagrams.py`, `tests/test_work_log.py:329-331`) accepts the three labels plus `EXTERNAL`. All other assertions, including the unchanged work-log figure validation, stay. The test lives in `tests/`, which the offline CI job already runs; no workflow change.

### D5: History and dates
Dated progress entries, archived changes and the learning journal stay. A twin keeps an "as of" line, now dated with the implementation date and commit. One new dated entry in `docs/progress.md` (mandatory; coordinator decision) records this refresh with the commands run and their results; older entries are never edited.

### D6: Rebuild
After the edits, run `scripts/build_work_log.py` and its `--check`. Confirm that the opening figure and the four diagram sections (ids `architecture-logical`, `architecture-physical`, `run-flow-activity`, `run-flow-sequence`) of `report/index.html` contain none of the stale phrases of D4. The whole page is not grepped: it embeds dated history such as `docs/progress.md` entries, which legitimately say so. `report/` is Git-ignored, so nothing generated is committed.

### D7: `docs/comparison_evidence.md:14`
The sentence says 5 of the 60 traces cannot be read back (HTTP 500). It was true on 2026-11-06 before the fix and is superseded the same day: after `044c8d4`..`6deb36c` and `record --retrace`, 60 of 60 traces read back (`docs/progress.md` checklist row 6 and the fix entry). The original sentence is not deleted or rewritten; a dated note is appended as a new line after it, citing those two places in `docs/progress.md`. `presentation/evidence/summary.json` does not quote that file: its quotes come from `docs/prompt_comparison.md`, `docs/progress.md`, `docs/ci_evidence.md` and `docs/threat_model.md`, and the constant `CE` in `scripts/presentation_evidence.py` is defined but not used. The change therefore does not touch `summary.json` or the script. Its `check` is still run after the edit (`.venv/bin/python scripts/presentation_evidence.py check`) and must pass. The `docs/progress.md` edits (D8, D5) only add or change the "Current status" section and one new entry; the quoted lines of `docs/progress.md` (the cut-order, budget, first-run and observed-tests lines) stay byte-identical. If `check` fails, the summary is regenerated by its own script, never by hand.

### D8: `docs/progress.md` "Current status" and `docs/project_spec.md`
The "Current status" section (header line "Updated 2026-11-06", the bold sentence "Planning is consolidated; implementation remains the offline pilot", and its table) is a present-tense claim, not a dated entry, and contradicts the checklist below it. It is brought to the evidenced state: edit only rows whose text is contradicted by a cited committed source (for example the live generation, tracking and report rows, and the OpenSpec row if its change list is out of date), update the "Updated" date, and keep the "Required next evidence" column honest about what is still open (student interpretation, user-only items). Rows that are still correct are not touched. `docs/project_spec.md` stays unchanged: it is the specification and plan, not a status report.

## Risks / Trade-offs

- A box said IMPLEMENTED may look stronger than "30-trial pilot, no improvement claimed". Mitigation: the twins and the cited evidence carry the limits; the figures carry no results.
- Scripted XML edit could damage the draw.io payload. Mitigation: per-cell table, count assertions, whole-file round trip through the existing tests, and a diff review limited to the named cells.
- A longer stale-phrase list can flag a legitimate sentence. Mitigation: the allowlist with a reason per entry; the list is scoped to current-status files only.
- Adding `EXTERNAL` widens the vocabulary. Alternative: keep OpenRouter `IMPLEMENTED` with the phase-2 line; rejected because it claims we implemented OpenRouter.

## Decisions taken (coordinator, 2026-11-13)

- Q1: OpenRouter is labelled `EXTERNAL`, with live-use evidence cited from `docs/smoke_evidence.md` and `docs/prompt_comparison.md`.
- Q2: `docs/demo.md:86` and `README.md:5` are in this change with minimal edits; the further README lines of the same class (48, 124, 193) are included on the same basis.
- Q3: one new dated `docs/progress.md` entry is added; older entries are never edited.
- Q4: the empty student interpretation stays open (user-only) wherever it is mentioned.
- Q5: all 60 of 60 MLflow traces read back after `--retrace`; no figure or twin says any trace is unreadable; the dated 2026-11-03 history entry stays as history.
- Q6: the coordinator does the browser visual check of the rebuilt figures; the task stays unticked for the coordinator.
- C1: `docs/comparison_evidence.md:14` is in scope as an appended dated note (D7).
- C2: the "Current status" section of `docs/progress.md` is in scope; `docs/project_spec.md` is not (D8).
