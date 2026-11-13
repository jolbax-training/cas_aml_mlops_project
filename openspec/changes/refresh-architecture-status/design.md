## Context

The paid phase finished after the diagrams were drawn (diagrams dated 2026-10-31 to 2026-11-01, base commit `078130a` or `37968d8`). Statuses use three labels with a text label on every box: `IMPLEMENTED`, `PARTIAL: NO LIVE RUN YET`, `PENDING`. The `.drawio.svg` files hold uncompressed draw.io XML in the root `content` attribute and a rendered SVG; existing tests already require the embedded labels to equal the rendered labels. `work_log_architecture.svg` is a hand-written SVG whose boxes carry class `arch-impl`, `arch-part` or `arch-plan`. `report/` is generated and Git-ignored.

## Decisions

### D1: Statuses follow cited evidence, with the vocabulary kept
Keep the three labels and the status key, since they will be needed again. Add one label, `EXTERNAL`, for OpenRouter only, which is not our code and cannot be "implemented"; its phase-2 marking stays because the existing spec requires it. Evidence mapping:

| Component(s) | Old | New | Evidence in repo |
| --- | --- | --- | --- |
| `openrouter_client.py`, `openrouter_config.py`, `model_configs/`, `openrouter_cli.py` | PARTIAL | IMPLEMENTED | `docs/smoke_evidence.md` (paid smokes, calibration, settings freeze) |
| `ledger.py`, `~/.codegen_eval/spend_ledger.jsonl` | PARTIAL | IMPLEMENTED | `docs/smoke_evidence.md` ("Ledger and projection"); `docs/prompt_comparison.md` (ledger rows of both runs) |
| `experiment.py`, `experiment_cli.py`, `run_recording.py` (box and lane) | PARTIAL | IMPLEMENTED | `docs/comparison_evidence.md` (both runs COMPLETE, 30 of 30) |
| `summary.py`, `comparison.py` | PARTIAL | IMPLEMENTED | `docs/prompt_comparison.md` (results from `compare`) |
| `mlflow_tracking.py`, MLflow tracking store, `mlflow_data/`, MLflow service container | PARTIAL | IMPLEMENTED | `docs/comparison_evidence.md` (live bundles recorded, read-only verification 2026-11-06) |
| reviewed result summaries | PENDING | IMPLEMENTED | `docs/prompt_comparison.md` (reviewed 2026-11-03, user decision recorded) |
| OpenRouter (external) | PENDING, "no live call" | EXTERNAL, phase 2, used | `docs/smoke_evidence.md`, `docs/comparison_evidence.md` |
| CI, required checks | IMPLEMENTED | unchanged | `docs/ci_evidence.md` |

Status stays honest about limits in the twins, not in the box (no numbers in figures): 5 of the 60 traces cannot be read back from MLflow (`docs/comparison_evidence.md`); the student interpretation in `docs/prompt_comparison.md` is intentionally empty and user-only, so it stays stated as open; the main-run evidence is a 30-trial pilot per variant and claims no improvement. A mismatch found while implementing (evidence missing for a row) leaves that row's status unchanged and is reported, not guessed.

### D2: Stale text inventory
Implementation re-greps and judges each hit; the list at proposal time:

- `work_log_architecture.svg`: `<desc>` ("tested offline only, with no live call yet"), 4 `PARTIAL` and 1 `PENDING` labels, lines "tested offline; no live call yet", "offline tooling done, no paid run", legend text "Pending: evidence does not exist yet (dashed)" (kept as key; no box uses it afterwards, so the key states it is the label for future use or is reworded).
- `work_log_architecture.md`: "as of 2026-10-31", the three-label explanation, steps 2, 6 to 8, the closing "sections ... labelled pending" sentence (check that against `work_log.toml` pending sections instead of removing blindly).
- `architecture_logical.md` and `.drawio.svg`: 16 `NO LIVE RUN YET` and 6 `PENDING` labels, "PHASE 2: no live call has been made", "not yet run", "only a fixture bundle recorded so far", "used by all tests today", section title "phase 2 pieces, built offline only", status key box and its twin line.
- `architecture_physical.md` and `.drawio.svg`: 6 `NO LIVE RUN YET`, "no live spend has happened", MLflow container text, "as of 2026-11-01 ... `078130a`".
- `run_flow_activity.md` and `.drawio.svg`: lane status table (host CLI, OpenRouter, disk and MLflow, human), `EXTERNAL, PHASE 2, PENDING`, "no live run has happened", the PENDING reviewed-summary node, the "verified at commit" line. Words such as "planned trials", "stop, later trials not run" are code semantics, not stale status, and stay.
- `run_flow_sequence.md` and `.drawio.svg`: participants `rr`, `oc`, `lg`, `ml` (PARTIAL), `or` (PENDING), "no live run has happened".
- Outside the listed files but found: `docs/demo.md:86` (describes yellow and dashed boxes in the walk-through) and `README.md:5` ("still an offline pilot"). They are not edited here; see Open questions.

### D3: Editing the `.drawio.svg` files
draw.io desktop is not needed. The files are plain XML and the existing test already compares embedded labels with rendered text, so a scripted edit of both parts is safe. One throwaway script (not committed, kept in the session scratchpad) does, per file and from an explicit table of (cell id, old status, new status, text changes):
1. Parse the embedded model; for each listed cell, replace the label text and, where the status class changes, the style (`fillColor=#FFF1B8` to `#E0EFFF`, `strokeWidth` 3; for pending boxes drop `dashed=1;dashPattern=...`, strokeWidth 3, fill `#E0EFFF`).
2. In the rendered SVG, edit the same text nodes and the `<rect>` found by the cell's geometry: `fill`, the `light-dark(...)` fill in `style`, `stroke-width`, and `stroke-dasharray`.
3. Assert that each replacement happens the expected number of times and that no `PARTIAL: NO LIVE RUN YET` remains where the table says it must go; otherwise exit non-zero without writing.
New labels are never longer than the old ones, so no layout change is needed; a label that would be longer is shortened instead of moved. The header comment "Do not edit with editors other than draw.io" remains true for later hand edits, and the files remain openable and editable in draw.io. Verification: the existing embedded-equals-rendered test, the new status test (D4), the existing sanitizer test (`tests/test_work_log_diagrams.py`), and a visual check of the rebuilt report in a browser by the coordinator (the implementer states that a visual check was not done by them if so). If the script cannot map a rendered rect uniquely, that file is reported rather than edited by guesswork.

### D4: The check
`docs/architecture_status_sources.toml` lists components with `status`, `evidence` (repo-relative file) and `phrase` (must occur in that file). New `tests/test_architecture_status.py`, offline, asserts: (1) every component's status in the logical diagram, the physical diagram, the sequence participants, the activity lane table and the work-log figure equals the TOML; (2) every evidence file exists and contains its phrase; (3) a fixed stale-phrase list (`NO LIVE RUN`, `no live call`, `no live run has happened`, `no live spend`, `no paid run`, `not yet run`, `only a fixture`, `PENDING` on a done component) does not occur in the nine current-status files, except inside an explicit allowlist (the status key defining the vocabulary), each entry with a reason; (4) a component marked `open` stays labelled as such. Existing tests that hard-code `STATUSES` or the three labels (`test_architecture_diagrams.py`, `test_run_flow_diagrams.py`, `test_work_log.py`) are adjusted to the vocabulary plus `EXTERNAL`; they keep their other assertions, including the unchanged work-log figure validation. The test lives in `tests/`, which the offline CI job already runs; no workflow change.

### D5: History and dates
Progress entries, archived changes, and `docs/progress.md` history stay. A twin keeps an "as of" line, now dated with the implementation date and commit; wording "as of ... status at that date" is allowed only where it is the current line. A short dated entry in `docs/progress.md` records this refresh (new entry, nothing rewritten); the coordinator may skip it if it prefers, see tasks.

### D6: Rebuild
After the edits, run `scripts/build_work_log.py` (with `--check`) and confirm in the output HTML that the opening figure and both diagrams contain no stale label. `report/` is Git-ignored, so nothing generated is committed.

## Risks / Trade-offs

- A box said IMPLEMENTED may look stronger than "30-trial pilot, no improvement claimed". Mitigation: the twins and the cited evidence carry the limits; the figures carry no results.
- Scripted XML edit could damage the draw.io payload. Mitigation: count assertions, whole-file round trip through the existing tests, and git diff review limited to the named cells.
- Adding `EXTERNAL` widens the vocabulary. Alternative: keep OpenRouter `IMPLEMENTED` with the phase-2 line; rejected because it claims we implemented OpenRouter.

## Open Questions

- Edit `docs/demo.md:86` and `README.md:5` in this change, or leave them to a follow-up? Proposed: leave, listed in the worker report.
- Add a dated line to `docs/progress.md`? Proposed yes, as a new entry only.
- Is the user-only student interpretation to appear in the figure as a separate open item? Proposed: twin only.
