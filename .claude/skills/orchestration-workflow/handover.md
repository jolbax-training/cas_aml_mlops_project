# Handover and concurrent coordinators

## Hand the coordinator role to a new session

1. Update `STATE.md` at the primary checkout root from [state-template.md](state-template.md): merged, in flight (owner, run id, branch, review status), remaining, CI, and the approvals the user gave. Check it holds no secrets or emails.
2. Launch the new coordinator from the primary checkout:
   `orca agent launch --agent claude --surface terminal --model claude-opus-5-5 --worktree path:<primary checkout> --prompt "<load the orchestration-workflow skill, read STATE.md, continue>"`
3. The new session creates its own run with `orca orchestration run-create` at its first dispatch ([SKILL.md](SKILL.md)). It never waits, acks, or dispatches in your run.
4. Keep only the changes you had in flight, in your run, until they merge; mark the new owner in `STATE.md` for everything else.

Flags are checked against `orca agent launch --help`; `orca agent launch` and `orca orchestration --help` are the authority if they differ. The procedure was exercised once, in the first handover test, not repeatedly.

## Two coordinators at once

- Split ownership by change in `STATE.md`: each change has one owner and one run id; edit only your own rows.
- Use separate runs. Never check, ack, or dispatch in the other coordinator's run.
- Shared documents (`docs/progress.md`, `README.md`, `docs/work_log.toml`): keep your edits small and self-contained, and rebase onto the other coordinator's merged edits before you merge. Resolve a documentation conflict yourself; send code conflicts to a worker.
