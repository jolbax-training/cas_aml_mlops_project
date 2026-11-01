# Tasks

Tasks needing a push, a live GitHub run, a live Orca dispatch, or user judgment stay unchecked with their reason.

## 1. Skill rule

- [ ] 1.1 Re-read `orca orchestration check --help`, `scripts/orchestration/wait.sh`, and `waitloop.sh` and confirm each claim in `design.md` (same run, whole FIFO batch, heartbeat batches acked by the loop, repeated `--ack` a no-op, actionable delivery left unacked). Verify: every claim in the new bullet traces to one of those three sources; any mismatch is recorded in `design.md` before writing the bullet.
- [ ] 1.2 Add one Mechanics bullet to `.claude/skills/orchestration-workflow/SKILL.md` covering the notice: same-run check, heartbeat-only batch acked and wait continues, actionable batch processed like a waitloop delivery then acked, then keep waiting or restart the wait, never a second wait loop on the run. Verify: `wc -l` of `SKILL.md` is under 150; the bullet contains no run IDs, handles, or paths; `git diff main -- .claude/skills/openspec-*` is empty.
- [ ] 1.3 Confirm no helper script needs to change. Verify: `git diff main -- scripts src` is empty; if a helper had to change, add a stub-based test in `tests/` for it and record why here.

## 2. Documentation

- [ ] 2.1 Add a short `docs/progress.md` entry (date, change name, what the rule says, that it rests on `check --help` and the script source, that no live actionable-notice test was run). Keep README.md and `docs/work_log.toml` edits to the minimum needed. Verify: `.venv/bin/python scripts/build_work_log.py --check` passes; the entry claims no result that was not run.

## 3. Validation

- [ ] 3.1 Run `.venv/bin/pytest -q`, the sandbox group (`CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`), and `openspec validate clarify-orchestration-notices --strict`. Verify: counts reported, output grepped for `failed`, `git status` clean.

## 4. Left open (not implementable by the worker)

- [ ] 4.1 Observe the rule on a live notice that carries an actionable message. Reason: needs a live Orca dispatch and the coordinator's session.
- [ ] 4.2 Merge to `main`, push, and archive. Reason: coordinator-owned; archive after acceptance.
