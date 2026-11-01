---
name: orchestration-workflow
description: Coordinate this project's multi-agent work in Orca. Load when you dispatch or supervise implementer or reviewer workers, review or fix an OpenSpec change, merge to main and watch CI, recover a stalled run, or hand a session over.
compatibility: Requires the orca CLI, git, and the uv-managed test environment.
metadata:
  author: cas_aml_mlops_project
  version: "1.0"
---

Run the project's change workflow as the **coordinator**: you plan, dispatch, monitor, merge, and verify; workers implement and review. Propose, apply, and archive steps live in the `openspec-*` skills; this skill adds who does what, in which order, and the guardrails. Read `STATE.md` at the root of the primary checkout first (the `main` checkout you run from, not a child worktree; Git-ignored, never committed); create it from [state-template.md](state-template.md) when absent.

## Roles

- **User** decides scope, formats, models, and cost gates, and owns human-only steps: branch protection, browser checks, learning-journal reflections.
- **Coordinator** (Claude Opus 5.5, this session) runs one Orca orchestration run, chooses worktree-per-change and parallel versus queued, and alone merges, pushes, archives, and verifies CI. You may do small mechanical steps yourself: tick tasks with evidence, archive, resolve documentation merge conflicts, a no-code research step such as a price recheck, and a one-line script fix with a regression test. Every other code or spec change goes to a worker.
- **Implementer** (Claude Sonnet 5.5) works in its own child worktree on `barahjos/<change>`, commits with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`, and leaves push, merge, and archive to you.
- **Reviewer** (Claude Fable 5.1) is read-only and writes one report file. A security-sensitive review blocked by Fable safeguards goes to Opus 5.5 only after the user approves.

## Lifecycle of one change

One change per finding or need. Fill the templates in [briefs.md](briefs.md) for every dispatch.

1. **Propose.** Implementer runs `openspec-propose`: proposal, design, delta specs, tasks; `openspec validate <change> --strict` passes. Fable reviews the proposal; fold every finding into the artifacts before implementation.
2. **Implement.** Same worker runs `openspec-apply-change` under the worker brief. Done means tasks ticked only when evidenced, tests and strict validation green, `git status` clean, and `worker_done` carrying branch, commit hash, tasks done and left, and test counts.
3. **Review.** Fable reads artifacts and code against `main`, reruns the tests, and reports findings as blocker, major, or minor.
4. **Fix loop.** Send the report path back to the **same worker terminal** (fix brief). Each finding ends fixed or declined with a reason. Review again until no blocker or major remains; minors may follow after merge.
5. **Merge.** Follow [merge-and-ci.md](merge-and-ci.md): fast-forward `main`, run unit and sandbox tests, grep their output for `failed`, push, watch CI. Every merge to main ends in green CI before the next step.
6. **CI red.** A worker reproduces the failure and fixes the root cause, then verifies on a `ci/**` branch before `main`. Skips and weakened guards are not fixes.
7. **Archive** with `openspec-archive-change` when all tasks are done. Tasks that need a human or paid step stay open with the reason written beside them.

## Commands

The code is not installed as a package: run module CLIs from the repository root with `PYTHONPATH=src` (`.venv/bin/pytest -q` needs no prefix; `pyproject.toml` sets `pythonpath = ["src"]`). Take commands from `README.md` and `docs/demo.md`, which hold the verified ones, and do not guess module names: `python -m codegen_eval.experiment` is a library module without a `__main__` block and exits 0 silently; the CLI is `codegen_eval.experiment_cli`. Put the same `PYTHONPATH=src` and README/demo rule into worker briefs.

## Mechanics

Check `orca orchestration worker-start --help` for current flags.

- **One run per coordinator session:** create it with `orca orchestration run-create --objective <text>` before your first `worker-start`, then pass `--run <run_id>` on every later dispatch and check. Never wait, ack, or dispatch in another coordinator's run: per `check --help`, all listeners on one run inbox get the same delivery and `--ack` acknowledges it for the run, so the other coordinator would lose the batch.
- **Start:** `worker-start --spec <brief> --task-title <t> --worktree new-child --agent claude --model <id>` for a fresh worker; `--worktree path:<dir>` to join an existing worktree (reviewers).
- **Follow-up:** reuse the worker with `--terminal <handle> --worktree path:<dir>`. A reused terminal keeps its model, so `--model` is rejected.
- **After an Orca restart** the old terminals are dead: restart each affected task with `worker-start --task <task_id> --retry-of <dispatch_id>` and repeat the placement and agent choices; the branch and worktree survive ([recovery.md](recovery.md)).
- **Wait** in the background with `scripts/orchestration/waitloop.sh` (`--help` lists options). `--types` only chooses what wakes the wait; every delivery is the whole FIFO batch.
- **Ack every delivery** by passing its id to the next check. Actionable deliveries (`worker_done`, question, escalation) included: an unacked delivery replays and hides newer mail.
- **Watch CI** with `scripts/orchestration/ciwatch.sh <run_id>`: the unauthenticated GitHub API allows 60 requests an hour, so poll gently (default 150 s) and read check-run annotations instead of logs.
- **Hand off** by updating `STATE.md` after every merge, review, or restart. To give the coordinator role to a new session, or to run two coordinators at once, follow [handover.md](handover.md).

## Guardrails

- Paid OpenRouter calls wait for the user's approval of the paid phase; then you run them yourself (never a worker) with `--i-accept-cost` (flag of the OpenRouter and experiment CLIs in the README) and the budget ledger. `OPENROUTER_API_KEY` (and any API key) never goes into a worker brief.
- A paid step or gate that fails stops all spending: report the evidence and the options, each with a cost cap, and let the user decide. A retry needs explicit approval with a cap (for example at most 5 tries or CHF 0.02).
- Evidence comes from commands you ran: quote real run IDs, hashes, and counts only.
- The user's reflections and learning-journal entries stay the user's words.
- The user's email address stays out of every external service.
- After each milestone rebuild the work log with `scripts/build_work_log.py` and confirm `--check`; unfinished sections stay visibly pending.

When something breaks, open [recovery.md](recovery.md).
