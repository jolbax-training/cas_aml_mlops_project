# Tasks

Tasks needing a push, a live GitHub run, a live Orca dispatch, or user judgment stay unchecked with their reason.

## 1. Skill rule

- [x] 1.1 Re-read `orca orchestration check --help`, `scripts/orchestration/wait.sh`, and `waitloop.sh` and confirm each claim in `design.md` (whole FIFO batch, heartbeat batches acked by the loop, repeated `--ack` a no-op, actionable delivery left unacked). Verify: every claim in the new bullet traces to one of those three sources; "same run" traces to `SKILL.md` "One run per coordinator session" instead; any mismatch is recorded in `design.md` before writing the bullet.
- [x] 1.2 Add one Mechanics bullet to `.claude/skills/orchestration-workflow/SKILL.md` covering the notice: same-run check, heartbeat-only batch acked and wait continues, actionable batch processed like a waitloop delivery then acked, then keep waiting or restart the wait, never a second wait loop on the run. Verify: `wc -l` of `SKILL.md` is under 150; the bullet states the exited-versus-blocked rule for the background job; it contains no run IDs, handles, or paths; `git diff main -- .claude/skills/openspec-*` is empty.
- [x] 1.3 Confirm no helper script needs to change. Verify: `git diff main -- scripts src` is empty; if a helper had to change, add a stub-based test in `tests/` for it and record why here.

## 2. Documentation

- [x] 2.1 Add a short `docs/progress.md` entry (date, change name, what the rule says, that it rests on `check --help` and the script source, that no live actionable-notice test was run). No README.md or `docs/work_log.toml` edit unless `build_work_log.py --check` fails without one; say so in worker_done if it does. Verify: `.venv/bin/python scripts/build_work_log.py --check` passes; the entry claims no result that was not run.

## 3. Validation

- [x] 3.1 Run `.venv/bin/pytest -q`, the sandbox group (`CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`), and `openspec validate clarify-orchestration-notices --strict`. Verify: counts reported, output grepped for `failed`, `git status` clean.

## 4. Left open (not implementable by the worker)

- [x] 4.1 Observe the rule on a live notice that carries an actionable message. Reason: needs a live Orca dispatch and the coordinator's session. Outcome 2026-11-06: not observed. The coordinator session received 6 host notices (1 after the merge of `ca7b9a1`); every batch held only a worker heartbeat and was handled per the rule (check, ack, background wait left running; each later `worker_done` was caught by `waitloop.sh`). The actionable case never arose because the background loop wakes on `worker_done` first. Since Orca 1.4.246 (2026-11-02) `check --json` returns no `deliveryId`, so the bullet's ack steps cannot be executed as written; re-verifying the actionable branch moves to the queued helper-script change. Accepted by the user as the trial.
- [x] 4.2 Merge to `main`, push, and archive. Reason: coordinator-owned; archive after acceptance. Done: merged as `ca7b9a1` (CI run 41312377700 success); archived 2026-11-06 after the user accepted 4.1.
