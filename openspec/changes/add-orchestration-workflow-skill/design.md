## Context

The coordinator is a Claude Opus 5.5 session in Orca. Today its working material sits in a session scratchpad: shared worker rules (`common.txt`), a fix-loop brief (`fix.txt`), a reviewer brief (`review.txt`), `wait.sh`/`waitloop.sh` (block on worker messages), `ciwatch.sh` (poll a GitHub Actions run), `STATE.md` (handoff), and example review reports. Hard-coded values (repository URL, scratchpad paths, run and dispatch IDs, terminal handles) make them unusable elsewhere. The repo has six `openspec-*` project skills under `.claude/skills/` (frontmatter `name`, `description`, then a procedural body) and no `CLAUDE.md`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- A future session loads one skill and coordinates the same way: same roles, lifecycle, gates, and brief wording.
- The main file stays short enough to read in one pass; situational material is reached through pointers (progressive disclosure).
- Helper scripts are generic, runnable from the repo, and checkable offline.

**Non-Goals:**
- No new process, role, or gate beyond the user-approved description.
- No change to Orca, the existing `openspec-*` skills, CI workflows, or evaluator code.
- No recorded results: the skill states procedure, not run IDs, hashes, or review verdicts.

## Decisions

1. **One skill, `orchestration-workflow`, with reference files.** `SKILL.md` holds roles, the seven-step lifecycle (propose, implement, review, fix loop, merge, CI-red repair, archive), mechanics essentials, and guardrails. Reference files sit beside it: `briefs.md` (worker, fix, review templates), `merge-and-ci.md`, `recovery.md`, `state-template.md`. Each is reached through a pointer that names its branch ("when merging…", "when a reviewer stalls…"). *Alternative:* one long file (rejected: sprawl, situational recovery text buries the steps); one skill per role (rejected: the coordinator needs the whole loop, and the roles share the guardrails).
2. **Frontmatter description is a trigger pointer.** It leads with the coordinator role and lists the distinct branches that should load the skill (dispatching or supervising Orca workers, reviewing or fixing a change, merging and watching CI, handing off a session), without restating the body. It carries no `allowed-tools` restriction, since the coordinator needs shell, git, and `orca`.
3. **Briefs are templates with named placeholders** (`<change>`, `<branch>`, `<report-path>`, `<test commands>`), not literal text with IDs. The shared worker rules keep their content (roles, no push/merge/archive, commit trailer, honest task ticking, evidence in `worker_done`) and phrase targets positively, keeping prohibitions only for hard guardrails (paid calls, invented evidence, user reflections), each paired with the positive action. Test commands and the image note are project facts the template names once.
4. **Scripts live in `scripts/orchestration/`, are POSIX `sh`, and take parameters.**
   - `wait.sh [ack_delivery]`: one blocking `orca orchestration check --wait` for `worker_done,escalation,question` messages, prints a readable summary.
   - `waitloop.sh [ack_delivery]`: repeats `wait.sh`, acking each non-terminal batch and returning when a `worker_done`, `question`, or `escalation` arrives; the actionable delivery is **printed and its id left for the caller to ack explicitly**, because an unacked batch is replayed and hides newer mail. Loop count and timeout are parameters.
   - `ciwatch.sh <run_id>`: polls the run until completed, then prints run, jobs, failing steps, and check-run annotations (annotations rather than logs, which need authentication). The repository comes from `--repo`/`CIWATCH_REPO` or the `origin` remote, not a literal. Poll interval is a parameter, default gentle enough for the unauthenticated 60 requests/hour limit.
   - Common helper: `orca`, `curl`, and `python3` are looked up on `PATH`, so tests substitute stubs. A `--dry-run`/`--help` path prints the resolved command without calling Orca or GitHub.
   *Alternative:* Python scripts (rejected: the originals are shell and mostly glue, and tests of stubs are equally easy; keeps one idiom with the existing `scripts/ci_*.sh`).
5. **Checks for the scripts are stub-based pytest tests** under `tests/`, with fake `orca` and `curl` executables on `PATH` and canned JSON. They run in the existing offline test group, need no network, Orca, or Podman, and cover: summary output, ack passing, replay-pitfall handling, loop termination, repo resolution, completed/failed run printing, and `--dry-run`.
6. **Pointers.** `README.md` gets a short section naming the skill and when to load it. `CLAUDE.md` is not created; if it exists when the task runs, a one-line pointer is added.
7. **Consistency with `openspec-*` skills.** Same frontmatter keys (`name`, `description`, `license`, `metadata`), imperative step wording, and references to those skills by name rather than copying their steps. The apply and archive procedures stay in those skills.
8. **Generalization rules.** Replace the scratchpad path with a `$SCRATCH`/"session scratchpad" mention, repository URL with `<owner>/<repo>` resolved at runtime, run/dispatch/terminal IDs with placeholders. Example review reports are mined for the report format and severity scale only; no report content or run identifiers are copied. `STATE.md` becomes a template with section headings (merged/archived, in flight, remaining, CI status) and no historical entries.
9. **Pitfalls recorded where they bite.** Actionable deliveries must be acked or are replayed (in the wait-loop step and in `recovery.md`); grep test output for `failed` rather than trusting exit codes (merge checklist); CI-red repair never uses skips or weakened guards and is verified on a `ci/**` branch first; Orca restarts kill worker terminals, so redispatch with `--retry-of`.

## Risks / Trade-offs

- [Skill drifts from how work is actually done] → Reference files cite the one place each fact lives (scripts, briefs); Fable reviews the skill against the approved description; `STATE.md` template keeps run-specific facts out of the skill.
- [Orca CLI flags change] → The skill names flags as used today and points to `orca orchestration --help` as the authority; scripts isolate Orca calls in one wrapper.
- [Stub tests pass while real Orca/GitHub behave differently] → Tests are labelled as stub checks; real behavior is exercised only when a session uses the scripts, and a task records that this was not verified against live services unless it is.
- [Wording too long for agents] → Main file kept to the lifecycle and guardrails; everything situational is disclosed behind pointers.
- [Unauthenticated GitHub API rate limit (60/h)] → Default 150 s poll, annotation lookups only on completion.

## Migration Plan

Additive. Merge like any change (fast-forward by the coordinator, then watch CI). Rollback is deleting the skill directory, `scripts/orchestration/`, the tests, and the README section. The scratchpad originals remain untouched.

## Open Questions

- The skill directory name (`orchestration-workflow`) can be renamed in review without changing the specs or tasks.
