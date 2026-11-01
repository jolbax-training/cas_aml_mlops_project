## Context

The host injects "You have N orchestration message(s). Run `orca orchestration check --run <run_id>`." into the coordinator session when mail arrives, independent of the background `waitloop.sh`. Observed twice on 2026-11-01, both times a heartbeat-only batch.

Facts checked before writing the rule:

- `orca orchestration check --help`: the default check returns the bound Run's oldest unacknowledged FIFO batch and has a `--run <run_id>` option (the help lists `--run` without a description; that it selects the Run inbox is inferred from the notice and from the one-run-per-coordinator bullet in `SKILL.md`). A bound Run replays the same Delivery until `--ack` or until all its messages are marked read. Several `--wait` calls may wait on one Run inbox; waiting reserves nothing, and listeners woken together get the same Delivery. A repeated `--ack` is a no-op. A returned Delivery is always the whole FIFO batch.
- `scripts/orchestration/wait.sh` calls `orca orchestration check [--terminal] [--ack] --wait --types worker_done,escalation,question`. It has no `--run` option, so it relies on the bound Run.
- `scripts/orchestration/waitloop.sh` loops `wait.sh`. A batch without `worker_done`, `question`, or `escalation` (heartbeats) is acked by the loop itself (it passes the delivery id to the next `wait.sh --ack`). An actionable delivery is printed and left unacked for the caller.

## Goals / Non-Goals

**Goals:** a short rule that stops three mistakes: ignoring the notice, starting a second wait loop on the run, and losing an actionable message.

**Non-Goals:** changing the helper scripts, adding `--run` to `wait.sh`, or controlling the host's notice behavior.

## Decisions

1. **Run the check the notice names, same run.** The notice names `--run <run_id>`. The coordinator uses its own session run (derived from the "One Orca run per coordinator" requirement, not stated by the three sources) and never another coordinator's.
2. **Heartbeat-only batch: ack it, keep waiting.** Because `waitloop.sh` acks such batches itself and a repeated `--ack` is a no-op, acking by hand is harmless even if the loop acks first. A heartbeat does not wake the loop (`--types` is the wake condition, per `check --help`), so the hand ack is what clears the batch now; if the loop acks it later as well, the repeated ack is a no-op (inference from the help text, consistent with the 2026-11-01 observation). The background wait continues; nothing needs a restart.
3. **Actionable batch: process like a waitloop delivery, then ack, then look at the background job.** Process every message, then ack the delivery id. After the hand check and its ack the background wait will not see that message again (the help names both `--ack` and marked-read as the end of a replay; which applies to a plain check is not stated, so the rule assumes the stricter case: the loop gets the message at most once). `waitloop.sh` exits 0 as soon as it prints an actionable delivery, so exactly two states exist: (a) the loop was woken by the same message, printed the same delivery id, and exited: restart it with `--ack <that id>` (a repeated ack is a no-op); (b) the loop is still blocked in `check --wait`: leave it running, it will not replay the acked delivery. Keep "process once, ack once".
4. **No second wait loop on the same run.** Two listeners get the same delivery and share one ack, which is the same hazard as two coordinators in one run. A restart means stopping the old loop first.
5. **Skill only.** The helpers already behave as the rule needs, so no helper script or test changes. Confirm by reading the scripts again at implementation time; if a helper must change, add a stub-based test then.

## Risks / Trade-offs

- The notice text is host-generated and may change. The rule keys on the `check --run` command it names, not on its wording.
- A race: the loop may print an actionable delivery just as the coordinator checks by hand. Both get the same delivery, and the single ack is idempotent, so no message is lost. Mitigation: the bullet says to process once and ack once.
- `SKILL.md` is at 57 lines, so one bullet leaves it far under ~150.

## Open Questions

None blocking. A wording check against a live notice with an actionable batch is not possible offline; the rule for that case rests on `check --help` and the script source.
