## ADDED Requirements

### Requirement: Orchestration-message notices
The skill SHALL tell the coordinator, in one short Mechanics bullet (`SKILL.md` stays under about 150 lines), how to handle the host's "You have N orchestration message(s)" notice while a background wait runs: run the check the notice names on the same run, process what it returns, and never start a second wait loop on that run.

#### Scenario: Notice carries only a heartbeat
- **WHEN** the host notice names `check --run <run_id>` and the batch holds only a reviewer heartbeat
- **THEN** the skill directs the coordinator to ack the delivery and keep the background wait running, noting that `waitloop.sh` acks heartbeat-only batches itself and a repeated `--ack` is a no-op

#### Scenario: Notice carries an actionable message
- **WHEN** the batch holds a `worker_done`, question, or escalation
- **THEN** the skill directs the coordinator to process it as it would a `waitloop.sh` delivery, ack it afterwards, and then keep waiting for the next message or stop and restart the wait as needed, because the background wait will not see the acked message

#### Scenario: A wait loop is already running
- **WHEN** a notice arrives while a background wait loop runs on the run
- **THEN** the skill forbids starting a second wait loop on that run
