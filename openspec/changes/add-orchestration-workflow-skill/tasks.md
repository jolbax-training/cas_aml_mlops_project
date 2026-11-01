# Tasks

Stage 2 implements sections 1 to 3 (except 3.4, which waits for the coordinator's review). The recovery playbook source is the coordinator's recovery incident record. Tasks that need a push, a live GitHub run, a live Orca dispatch, or user judgment stay unchecked with their reason.

## 1. Skill content

- [x] 1.1 Read `.claude/skills/openspec-*/SKILL.md` frontmatter/style and the `writing-for-agents` guidance, then write `.claude/skills/orchestration-workflow/SKILL.md` (frontmatter `name`, trigger `description`, project-authored `metadata.author`/`compatibility` and no generator-specific values copied from `openspec-*`; roles, seven-step lifecycle, mechanics essentials, guardrails, pointers). Verify: file exists, covers every requirement in `specs/orchestration-workflow`, and stays under ~150 lines.
- [x] 1.2 Write `briefs.md` with the worker (shared rules), fix-loop, and reviewer brief templates from the coordinator's `common.txt`, `fix.txt`, `review.txt`, using placeholders. Report locations use the placeholder `<report-path>`. Verify: `grep -rnE 'ctx_|term_|run_[0-9a-f]{6,}|delivery_|/private/tmp|/Users/|@[a-z0-9.-]+\.[a-z]+'` over the skill directory returns nothing except the required `noreply@anthropic.com` commit-trailer lines.
- [x] 1.3 Write `merge-and-ci.md` (ff-merge, unit and sandbox runs, grep for `failed`, push, CI watch, CI-red repair via `ci/**`). Verify: each step has a checkable completion condition.
- [x] 1.4 Write `recovery.md` strictly from the coordinator's first-hand recovery incident record (`recovery-notes.md`, supplied in the dispatch; seven incidents): Orca restart, stalled reviewer (API cut-off entry), Fable safeguard block, missing CI logs, load-flaky sandbox tests, architecture-specific CI failure, and the unacked-delivery replay pitfall, each as symptom, action, outcome. Where the record is silent (waiting thresholds, escalation timing) write that and say to ask the user; if the record is not in the dispatch, ask the coordinator with `orca orchestration ask` rather than inventing procedure. Verify: all seven entries present, each traceable to a record entry.
- [x] 1.5 Write `state-template.md` as a `STATE.md` template with no run-specific history, and state in `SKILL.md` that the live file is the Git-ignored `STATE.md` at the primary checkout root, read first and created from the template when absent; add `/STATE.md` to `.gitignore`. Verify: no dates, run IDs, or hashes beyond placeholders; `git check-ignore STATE.md` succeeds; the path in `SKILL.md`, `state-template.md`, and `.gitignore` agree; the template mentions no secrets or emails.
- [x] 1.6 Confirm the existing `openspec-*` skills are unmodified. Verify: `git diff main -- .claude/skills/openspec-*` is empty.

## 2. Helper scripts

- [x] 2.1 Add `scripts/orchestration/wait.sh` and `waitloop.sh` generalized from the scratchpad versions (parameters for timeout, rounds, types; stderr kept out of the JSON stream; non-JSON or error responses printed with non-zero exit; actionable delivery left unacked for the caller; non-zero exit when exhausted). Verify: behavior matches `specs/orchestration-helpers`.
- [x] 2.2 Add `scripts/orchestration/ciwatch.sh` (repo from `--repo`/`CIWATCH_REPO`/`origin`, poll interval parameter, rate-limit/error detection, non-zero exit on non-success). Verify: behavior matches the spec.
- [x] 2.3 Add `--dry-run`/`--help` to each script. Verify: each prints its resolved command or usage without calling Orca or GitHub.
- [x] 2.4 Add stub-based pytest tests (fake `orca`/`curl` on `PATH`) covering the scenarios in `specs/orchestration-helpers`. Verify: `.venv/bin/pytest -q` passes offline; report counts.
- [x] 2.5 Verify the scripts and skill paths agree (the skill names the scripts and their options as implemented). Verify: grep of option names in the skill against `--help` output.

## 3. Pointers and validation

- [x] 3.1 Add a short README section pointing to the skill and scripts; add a `CLAUDE.md` pointer only if that file exists. Verify: README diff is a few lines; no new `CLAUDE.md` created.
- [x] 3.2 Run `.venv/bin/pytest -q`, the sandbox group, and `openspec validate add-orchestration-workflow-skill --strict`; confirm `git status` clean. Verify: counts reported, output grepped for `failed`.
- [x] 3.3 Add a `docs/progress.md` entry for this change: what exists, what was verified offline, and what 4.1 and 4.2 leave open (no invented results). Verify: `.venv/bin/python scripts/build_work_log.py --check` still passes.
- [x] 3.4 Address every finding of the coordinator's post-implementation Fable review in the same worker session, recording each as fixed or declined with a reason in `worker_done` and in the progress entry. Verify: each finding number has a recorded disposition.

## 4. Left open (not implementable by the worker)

- [ ] 4.0 Coordinator-owned: Fable review of the proposal before implementation (done for stage 1; findings folded into these artifacts) and Fable review of the implemented skill, scripts, and tests. Reason: the worker cannot commission reviews and the reports live in the coordinator's scratchpad, outside the repo.
- [ ] 4.1 Try the skill in a fresh coordinator session on a real change and note gaps. Reason: needs a live Orca session and the user's judgment; do not claim it until done.
- [ ] 4.2 Verify the scripts against live Orca and a real GitHub run. Reason: needs a push and a GitHub Actions run, which only the coordinator performs.
