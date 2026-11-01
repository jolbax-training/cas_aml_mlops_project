# Recovery playbook

Source: the coordinator's first-hand record of incidents in this project (seven entries). Each entry gives symptom, action, and the outcome that ends the recovery. Where the record gives no rule (waiting thresholds, when to escalate), ask the user instead of choosing a number.

## Orca quit or restarted mid-run
- **Symptom:** orca commands report Orca is not running; later dispatches fail with an agent-readiness timeout because the worker terminals died.
- **Action:** `orca open --json`, rebind to the same run; for each affected dispatch run `worker-start --task <task_id> --retry-of <failed dispatch_id>` with the placement and agent choices repeated (a retry inherits none).
- **Ends when:** the new worker continues from the committed state; the worktree and branch survive.

## Reviewer or worker cut off (stalled)
- **Symptom:** no heartbeats and no `worker_done`; its terminal shows an API error such as "computer went to sleep mid-response".
- **Action:** `orca terminal send` to its terminal: continue where you left off, write the report to `<report-path>`, and send `worker_done` as the preamble says.
- **Ends when:** the worker resumes and finishes. The record gives no waiting time before intervening or rule for escalation: ask the user if it does not resume.

## Fable reviewer blocked by safeguards
- **Symptom:** the session flags the request (security review) and switches model, then stalls; the dispatch ends in `stop_unknown`.
- **Action:** `worker-stop`, then `worker-abandon` the dispatch; keep its partial report under a new name (`review-<change>-fable-partial.md`); ask the user, and use an Opus 5.5 reviewer for that change only after approval.
- **Ends when:** the approved reviewer reports no blocker or major (it took three rounds in the recorded case). Never switch reviewer model without approval.

## Wait loop replays old messages
- **Symptom:** the same `worker_done` or heartbeat arrives repeatedly.
- **Cause:** deliveries were not acked. Heartbeat batches and actionable deliveries both need an ack.
- **Action:** pass the previous delivery id with `--ack` on the next check (`wait.sh --ack <id>`).
- **Ends when:** `check` returns `deliveryId: null`.

## GitHub CI logs not accessible
- **Symptom:** a job failed, but raw logs need authentication; polling too often hit the 60 requests/hour unauthenticated limit once.
- **Action:** poll about every 150 s (`ciwatch.sh`); read jobs, steps, and check-run annotations (`/check-runs/<id>/annotations`). The CI emits per-test failure annotations and environment notices, so the failing test is visible without logs. Reproduce on Linux locally and verify fixes on a `ci/**` branch before `main`.
- **Ends when:** the failing test is named and a fix is green on `ci/**`. Check the CI result of every push to main: unverified pushes once left CI red for several commits.

## Sandbox tests flaky under host load
- **Symptom:** a few sandbox failures locally while background processes loaded the machine; a rerun passed.
- **Action:** grep the pytest output for `failed` before pushing; on failure rerun once and inspect the load; report both outcomes. A real cause gets fixed in the tests (the recorded fix scaled non-timeout deadlines from a startup baseline and added a cross-worktree lock), never a skip.
- **Ends when:** the suite passes with the expected counts and the output contains no `failed`.

## CI red only on the runner's architecture
- **Symptom:** the offline job is red only on GitHub (amd64) because a committed config pinned the arm64 image digest.
- **Action:** suspect architecture-specific committed values; prefer host-independent artifacts. Local arm64 runs and arm64 Linux containers do not cover amd64.
- **Ends when:** CI is green on a `ci/**` branch, then on `main`.
