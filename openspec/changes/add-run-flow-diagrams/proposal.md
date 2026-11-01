# Proposal

## Why

The accepted physical and logical diagrams (`docs/architecture_physical.drawio.svg`, `docs/architecture_logical.drawio.svg`; capability `architecture-diagrams`) show where things run and which components exist. Neither shows the **sequence** of one experiment run: when it starts, which gates it must pass, what repeats, in which order a trial calls the model, the ledger, the sandbox and the bundle, and every way it can end. That is the question a reader and a reviewer need answered before the first paid call (phase 2): "what exactly happens after I type the run command, and what do I find on disk when it stops halfway?"

## What Changes

- Add two draw.io-editable diagrams, each with a Markdown text twin, and leave the two accepted diagrams, their twins, and the existing requirements untouched:
  1. **Main: a UML activity diagram with swimlanes** of one experiment run end to end (`docs/run_flow_activity.drawio.svg`, twin `docs/run_flow_activity.md`). It starts at the experiment CLI `run` command, passes the precondition checks (frozen benchmark, settings and platform, probe evidence, budget), runs the schedule loop over tasks and trials, inside each trial the bounded agent loop (ledger reservation before every send, tool attempts and development checks within limits, stop conditions), the final submission or `no_submission`, hidden grading of each case in a fresh container, the run bundle written first, then the MLflow recording with its outage marker. After the loop come the schedule verification, then, as separate commands, the comparison of the two variants (which reads bundles and summaries), human review, and the work-log rebuild. Every way a run ends is an explicit final node.
  2. **Supplement: a UML sequence diagram of one trial** (`docs/run_flow_sequence.drawio.svg`, twin `docs/run_flow_sequence.md`) with the exact call order between the real modules, `loop` and `alt` fragments for the agent loop and per-case grading, and the trust boundary.
- Every node, decision, message, and ordering is traced to a function in `src/codegen_eval/` and recorded in the twins; the diagram box names are cross-referenced to the logical diagram's boxes.
- Register both in `docs/work_log.toml` through the existing `[[diagram]]` mechanism, reusing `sanitize_drawio_svg` unchanged. The allowlist is extended only if the real draw.io export of an activity or sequence shape needs it, through a reviewed, tested addition.
- Add `tests/test_run_flow_diagrams.py`, in the style of `tests/test_architecture_diagrams.py`: labels equal embedded XML, module and function names exist, flow claims are checked against the source.
- Status honesty: no live run has happened. The diagrams show control flow, never results, run identifiers, or spend.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `architecture-diagrams`: ADDED requirements only (a run-flow activity diagram, a one-trial sequence diagram, explicit run endings, and consistent trust-boundary and phase marking); no existing requirement is modified or removed.

## Impact

- New files: two `docs/run_flow_*.drawio.svg`, two `docs/run_flow_*.md`, `tests/test_run_flow_diagrams.py`.
- Edited files: `docs/work_log.toml` (two `[[diagram]]` entries), `README.md` (pointer and regeneration line), `docs/progress.md` (evidence entry). `scripts/build_work_log.py` changes only if the export needs a reviewed allowlist addition.
- No runtime code, CI workflow, existing diagram, or other OpenSpec change is edited. No paid call, API key, or push is needed.
- Dependencies: the accepted `architecture-diagrams` capability and the draw.io desktop CLI (authoring only, as before). Milestone: documentation for the phase-2 gate; it does not change the 32-hour scope's code deliverables.
- Completion evidence: both diagrams and twins checked in, tests green, `build_work_log.py --check` green, a Fable review addressed, and the user's confirmation after opening both files in draw.io.
