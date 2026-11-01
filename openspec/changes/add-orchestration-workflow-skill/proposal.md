# Proposal

## Why

The project is delivered by a coordinator session that dispatches implementer and reviewer workers through Orca and manages OpenSpec changes end to end. That process lives only in one coordinator's scratchpad (worker briefs, wait/CI scripts, `STATE.md`) and in conversation history, so a new Claude Code session cannot reproduce it, and known pitfalls (for example unacked actionable deliveries being replayed) are rediscovered the hard way.

## What Changes

- Add a project skill at `.claude/skills/orchestration-workflow/SKILL.md`: a concise main workflow (roles, per-change lifecycle, guardrails) with a trigger-oriented frontmatter description, written following the `writing-for-agents` guidance and consistent with the existing `openspec-*` skills (which are not modified).
- Add reference files next to it, loaded only when needed: worker, fix-loop, and review brief templates; a merge-and-CI checklist; a recovery playbook (Orca restart, stalled reviewer, Fable safeguard block, missing CI logs, load-flaky sandbox tests, architecture-specific CI failure) based strictly on the coordinator's first-hand incident record; and a `STATE.md` handoff template. The live handoff file is a Git-ignored `STATE.md` at the root of the primary checkout.
- Move the coordinator's helper scripts into the repository under `scripts/orchestration/` as generalized, parameterized versions (no scratchpad paths, run IDs, or dispatch IDs): a single-batch wait, a wait loop, and a GitHub CI watcher, each with a dry-run or stub-based check.
- Add a short pointer to the skill in `README.md` (and in `CLAUDE.md` only if that file exists; it does not today).
- Amendment (2026-11-01, from the single-handover test of task 4.1): add command facts and sources, coordinator-own steps, the failed-paid-step rule, one Orca run per coordinator, a handover procedure, and concurrent-coordinator rules, with a new reference file `handover.md` and owner/run-id fields in `state-template.md` (design decisions 15 to 22).

The Codex skill mirror under `.agents/skills/` is intentionally not touched: the approved description names only `.claude/skills/`, so no copy is added there.

No runtime behavior of the evaluator, benchmark, agent loop, CI, or MLflow changes.

## Capabilities

### New Capabilities

- `orchestration-workflow`: The documented, loadable procedure for how the coordinator, implementers, and reviewers work on this project and how OpenSpec changes move from proposal to archive, including guardrails and recovery.
- `orchestration-helpers`: Parameterized, tested helper scripts the procedure relies on for waiting on workers and watching GitHub CI.

### Modified Capabilities

None. Existing capability specs are unchanged.

## Impact

Adds `.claude/skills/orchestration-workflow/` (SKILL.md plus reference files), `scripts/orchestration/` (shell scripts), a `/STATE.md` line in `.gitignore`, a `docs/progress.md` entry, tests under `tests/` for the scripts (stubbed `orca`/`curl`, no network, no Orca), and a README pointer. The 2026-11-01 amendment adds a reference file `handover.md` and owner/run-id fields in `state-template.md`, and edits `SKILL.md`, `briefs.md`, and `docs/progress.md`. No new Python runtime dependencies, secrets, paid API calls, or CI changes. Existing `openspec-*` skills, other changes, and the Wayfinder files are untouched.

## Dependencies and milestone

- **Milestone:** Supporting process work; not on the critical path of the four-day plan in [docs/project_spec.md](../../../docs/project_spec.md). It must not delay the paid comparison phase or the user-owned steps.
- **Upstream:** none. It documents the process already used for the merged changes (see `docs/progress.md` for evidence of those runs).
- **Downstream:** future sessions load the skill to coordinate; `prepare-reproducible-demo` may cite it as process evidence only after the skill exists.
- **Optional/excluded:** Building an automated orchestrator, a second system, or changing Orca itself is out of scope. The skill records the approved workflow; it does not invent extra process.

Completion evidence is the skill and reference files present and consistent with the approved workflow, script checks passing offline, `openspec validate --strict` passing, and a Fable review of the skill's accuracy and agent-readability. No claim is made that a fresh session has coordinated successfully from it until that is actually tried.

## Traceability

- User-approved description of the workflow (roles, lifecycle, mechanics, guardrails) given with this task on 2026-11-01; it is the source of truth and the design adds no process beyond it.
- Recovery playbook source: the coordinator's first-hand recovery incident record (`recovery-notes.md`, seven incidents, kept in the coordinator's scratchpad and supplied to the implementer through the dispatch). The playbook records only what that record says happened; nothing is invented.
- Specification: guardrails restate [docs/project_spec.md](../../../docs/project_spec.md) (no paid calls before approval, no invented evidence or reflections).
