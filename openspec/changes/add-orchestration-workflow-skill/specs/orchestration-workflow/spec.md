# Orchestration Workflow Spec Delta

## Purpose

Record how this project is worked on so that a future Claude Code session can load one project skill and coordinate implementers and reviewers, and manage OpenSpec changes end to end, in the same way.

## ADDED Requirements

### Requirement: Loadable project skill
The repository SHALL provide a project skill at `.claude/skills/orchestration-workflow/SKILL.md` (and not a copy under `.agents/skills/`) whose frontmatter has a `name` and a `description` that names the situations that should load it (supervising Orca workers, reviewing or fixing a change, merging and watching CI, handing off a session). The main file MUST stay concise and MUST reach situational detail only through pointers to reference files in the same skill directory.

#### Scenario: Session needs to coordinate
- **WHEN** a session is asked to dispatch, supervise, review, merge, or hand off project work
- **THEN** the skill's description identifies it as the one to load, and its body gives the roles, lifecycle, and guardrails without requiring other documents

#### Scenario: Skill coexists with existing skills
- **WHEN** the skill is added
- **THEN** the existing `openspec-*` skills are unmodified and the new skill refers to them for propose, apply, and archive steps instead of duplicating them

### Requirement: Roles and authority
The skill SHALL state four roles. The user decides scope, formats, models, and cost gates and owns human-only steps (branch protection, browser checks, learning-journal reflections). The coordinator (Claude Opus 5.5 in Orca) plans, dispatches, and monitors workers in one orchestration run, decides worktree-per-change and parallel versus queued, and alone merges, pushes, archives, and verifies CI.

#### Scenario: Worker finishes
- **WHEN** an implementer completes its work
- **THEN** the skill directs it to leave the branch committed and unpushed and report with evidence, and directs the coordinator to perform any merge, push, or archive


### Requirement: Worker and reviewer limits
The skill SHALL state that implementers (Claude Sonnet 5.5) work in their own child worktree on a `barahjos/<change>` branch, commit with the Sonnet co-author trailer, and never push, merge, or archive, and that reviewers (Claude Fable 5.1) are read-only and write a report file. A security-sensitive review blocked by Fable safeguards SHALL go to Opus 5.5 only with user approval.

#### Scenario: Reviewer is blocked by safeguards
- **WHEN** a Fable review of security-sensitive work is blocked
- **THEN** the skill directs the coordinator to ask the user before using an Opus 5.5 reviewer

### Requirement: Per-change lifecycle
The skill SHALL describe each change's lifecycle in order: propose, implement, review, fix loop, merge, CI-red repair, and archive. Propose means one change per finding or need, with `openspec validate --strict` and a Fable review of the proposal before implementation. Implement uses `openspec-apply-change`, shared worker rules, honest task ticking, passing tests, a clean git status, and `worker_done` with evidence.

#### Scenario: Review returns findings
- **WHEN** a reviewer reports blocker or major findings
- **THEN** the skill directs the coordinator to send them to the same worker session and to review again until none remain

#### Scenario: Task needs a human or paid step
- **WHEN** a task requires user judgment, a human action, or a paid call
- **THEN** the skill directs that the task stays unchecked with its reason recorded and that the change is archived only when all tasks are done or explicitly left open with reasons

### Requirement: Review and fix loop
The skill SHALL direct reviewers (Fable) to check the artifacts and code and rerun the tests, grading findings as blocker, major, or minor, and SHALL direct the coordinator to send findings back to the same worker session, where each finding is fixed or declined with a reason, repeating until no blocker or major remains. Minor findings MAY follow after merge.

#### Scenario: Minor findings remain
- **WHEN** only minor findings remain
- **THEN** the skill permits merging and fixing them afterwards

### Requirement: Merge and CI discipline
The skill SHALL direct the coordinator to fast-forward merge to main, run the unit tests and the sandbox suite, search the test output for `failed` instead of trusting exit codes, push, and watch GitHub CI on main, and SHALL state that every merge to main is followed by green CI. When CI is red it SHALL direct a worker to reproduce and fix the root cause, never by adding skips or weakening guards, and to verify the fix on a `ci/**` branch before main.

#### Scenario: Test exit code is zero but output reports failures
- **WHEN** merge verification output contains `failed`
- **THEN** the skill treats the verification as failed regardless of the exit code

#### Scenario: CI is red on main
- **WHEN** the CI run for a merged commit fails
- **THEN** the skill directs a root-cause fix verified on a `ci/**` branch before it reaches main, and forbids skips or weakened guards as the fix

### Requirement: Orchestration mechanics
The skill SHALL document the Orca mechanics the project uses: starting workers with a spec or task, a new-child or explicit worktree, and a model; reusing the same terminal for follow-ups; redispatching with a retry reference after an Orca restart; waiting for worker messages with explicit acks; a background wait loop and CI watcher; unauthenticated GitHub API use with gentle polling and check-run annotations instead of logs; and a `STATE.md` handoff.

#### Scenario: Delivery is received
- **WHEN** the coordinator receives a `worker_done`, question, or escalation delivery
- **THEN** the skill directs it to ack that delivery id explicitly after processing, because an unacked delivery is replayed and hides newer messages

#### Scenario: Orca restarts mid-run
- **WHEN** worker terminals are lost after an Orca restart
- **THEN** the recovery reference directs redispatch of the affected tasks with a retry reference to the original dispatch

### Requirement: Orca CLI constraints
The skill SHALL record that `--types` only sets the wake condition while a delivery is the whole FIFO batch, that reusing a terminal requires its worktree and cannot change the model, and that a retry names the failed task and does not inherit placement.

#### Scenario: Follow-up to a retained worker
- **WHEN** the coordinator sends a follow-up to an existing worker terminal
- **THEN** the skill directs reuse of that terminal with its worktree and without a model override

### Requirement: Unacked deliveries pitfall
The skill SHALL record that an actionable delivery that is not acked is replayed and hides newer messages, and SHALL direct the coordinator to ack each processed delivery id explicitly, including actionable ones.

#### Scenario: Replayed delivery
- **WHEN** the same `worker_done` or question appears again after being processed
- **THEN** the skill identifies a missing ack as the cause and directs acking its delivery id

### Requirement: Reusable briefs
The skill's reference files SHALL provide templates for the shared worker rules, the fix-loop brief, and the reviewer brief, parameterized by placeholders (change name, branch, report path, test commands) and free of hard-coded scratchpad paths, run IDs, dispatch IDs, or terminal handles.

#### Scenario: Dispatch a worker
- **WHEN** the coordinator fills in the worker template for a change
- **THEN** the result states the role limits, commit trailer, task-ticking honesty, test and validation commands, and the `worker_done` contents without further editing of boilerplate

#### Scenario: Reviewer report format
- **WHEN** the reviewer template is used
- **THEN** the reviewer writes a numbered findings list with severity (blocker, major, minor), file and line, problem, and suggested fix, and states explicitly when nothing is wrong

### Requirement: Recovery playbook
The skill's reference files SHALL include a recovery playbook covering an Orca restart, a stalled reviewer, a Fable safeguard block, missing CI logs, load-flaky sandbox tests, and architecture-specific CI failure, each with the symptom, the action, and the outcome that ends the recovery. The entries MUST be based on the coordinator's first-hand incident record and MUST state where that record is silent (such as waiting thresholds) instead of asserting a value.

#### Scenario: Reviewer stalls
- **WHEN** a reviewer or worker shows an API error (for example a cut-off mid-response) and sends no heartbeat or `worker_done`
- **THEN** the playbook directs sending a message to its terminal to continue, write the report to the report path, and send `worker_done`, and says to ask the user where the record gives no further rule

#### Scenario: CI logs unavailable
- **WHEN** GitHub logs cannot be fetched without authentication
- **THEN** the playbook directs use of check-run annotations through the unauthenticated API at a gentle polling rate

#### Scenario: Sandbox test fails only under load
- **WHEN** a sandbox test fails when run alongside other work but passes alone
- **THEN** the playbook directs grepping the output for `failed`, rerunning once while inspecting host load, recording both outcomes honestly, and fixing the cause rather than skipping the test

#### Scenario: Fable review blocked
- **WHEN** a Fable reviewer is blocked by safeguards and stalls
- **THEN** the playbook directs stopping and abandoning that dispatch, keeping its partial report under a new name, and asking the user before any other reviewer model is used

#### Scenario: CI fails only on another architecture
- **WHEN** CI fails on the runner but passes locally
- **THEN** the playbook names an architecture-specific committed value as a suspect and directs preferring host-independent artifacts

### Requirement: Guardrails
The skill SHALL state these guardrails: no paid OpenRouter call before the user approves the paid phase, and then only with `--i-accept-cost` (the flag of the OpenRouter and experiment CLIs) and the budget ledger; never fabricate evidence, run IDs, or results; never write the user's reflections; never send the user's email to external services; every merge to main is followed by green CI.

#### Scenario: Paid phase not yet approved
- **WHEN** a task would make a paid model call and the user has not approved the paid phase
- **THEN** the skill directs the task to be left unchecked and reported, not run

### Requirement: Work-log rebuild
The skill SHALL direct the coordinator to rebuild the work log after milestones with `scripts/build_work_log.py` (verified with `--check`) while keeping pending sections visibly pending.

#### Scenario: Milestone reached
- **WHEN** a change is merged and CI is green
- **THEN** the skill directs a work-log rebuild that leaves unfinished sections marked pending

### Requirement: Session handoff state
The skill SHALL provide a `STATE.md` template that records merged and archived changes, changes in flight with branch and review status, remaining work, and CI status, with no run-specific history included in the template itself. The live file SHALL be a Git-ignored `STATE.md` at the root of the primary checkout, read first by a new coordinator and created from the template when absent, and MUST NOT contain secrets or email addresses.

#### Scenario: State file is ignored
- **WHEN** a coordinator creates the live `STATE.md`
- **THEN** `git status` does not list it and the repository's ignore rules cover it

#### Scenario: New session resumes
- **WHEN** a new coordinator session reads the filled-in state file
- **THEN** it can identify what is merged, what is in flight, what the user must do, and the last verified CI result
