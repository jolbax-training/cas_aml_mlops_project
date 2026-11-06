## Why

The coordinator saw a gap on 2026-11-01, right after the handover test. While `scripts/orchestration/waitloop.sh` ran in the background, the Orca host also injected a prompt into the coordinator session: "You have 1 orchestration message. Run `orca orchestration check --run <run_id>`." It fired twice during one review. Both batches held only a reviewer heartbeat ("alive"). The coordinator ran the check, acked the delivery, and kept waiting. The background wait then caught the reviewer's `worker_done` normally. The `orchestration-workflow` skill says nothing about these notices, so a coordinator without that experience could start a second wait loop, ignore the notice, or lose an actionable message.

## What Changes

- Add one short Mechanics bullet to `.claude/skills/orchestration-workflow/SKILL.md` (file stays under ~150 lines) covering the host's "You have N orchestration message(s)" notice: run the check it names, on the same run; ack heartbeat-only batches and keep the background wait running; process an actionable batch (`worker_done`, question, escalation) like a `waitloop.sh` delivery and ack it after processing, then account for the background wait; never start a second wait loop on the same run.
- Add one requirement to the `orchestration-workflow` capability with WHEN/THEN scenarios.
- Add a short `docs/progress.md` entry.
- No change to `scripts/orchestration/*` or to `src/`, so no new stub-based test.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `orchestration-workflow`: adds a requirement that the skill tells the coordinator how to handle the host's orchestration-message notice.

## Impact

- `.claude/skills/orchestration-workflow/SKILL.md` (one bullet), `docs/progress.md` (one entry).
- Possible small edits to `docs/progress.md`, `README.md`, and `docs/work_log.toml` by another coordinator's change: keep edits here small to ease merges.
- Does not touch `src/`, helper scripts, `STATE.md`, or `.scratch/`.
