# Tasks

Planning only: nothing below is implemented yet. Tasks that need a push, a live GitHub run, a live Orca dispatch, or user judgment stay unchecked with their reason.

## 1. Skill content

- [ ] 1.1 Read `.claude/skills/openspec-*/SKILL.md` frontmatter/style and the `writing-for-agents` guidance, then write `.claude/skills/orchestration-workflow/SKILL.md` (frontmatter `name`, trigger `description`; roles, seven-step lifecycle, mechanics essentials, guardrails, pointers). Verify: file exists, covers every requirement in `specs/orchestration-workflow`, and stays under ~150 lines.
- [ ] 1.2 Write `briefs.md` with the worker (shared rules), fix-loop, and reviewer brief templates from the coordinator's `common.txt`, `fix.txt`, `review.txt`, using placeholders. Verify: `grep -rnE 'scratchpad|ctx_|term_|run_[0-9a-f]{6}|/private/tmp'` over the skill directory returns nothing.
- [ ] 1.3 Write `merge-and-ci.md` (ff-merge, unit and sandbox runs, grep for `failed`, push, CI watch, CI-red repair via `ci/**`). Verify: each step has a checkable completion condition.
- [ ] 1.4 Write `recovery.md` covering Orca restart, stalled reviewer, Fable safeguard block, missing CI logs, load-flaky sandbox tests, and the unacked-delivery replay pitfall (symptom, action, end condition each). Verify: all five situations plus the pitfall are present.
- [ ] 1.5 Write `state-template.md` as a `STATE.md` template with no run-specific history. Verify: no dates, run IDs, or hashes beyond placeholders.
- [ ] 1.6 Confirm the existing `openspec-*` skills are unmodified. Verify: `git diff main -- .claude/skills/openspec-*` is empty.

## 2. Helper scripts

- [ ] 2.1 Add `scripts/orchestration/wait.sh` and `waitloop.sh` generalized from the scratchpad versions (parameters for timeout, rounds, types; actionable delivery left unacked for the caller; non-zero exit when exhausted). Verify: behavior matches `specs/orchestration-helpers`.
- [ ] 2.2 Add `scripts/orchestration/ciwatch.sh` (repo from `--repo`/`CIWATCH_REPO`/`origin`, poll interval parameter, rate-limit/error detection, non-zero exit on non-success). Verify: behavior matches the spec.
- [ ] 2.3 Add `--dry-run`/`--help` to each script. Verify: each prints its resolved command or usage without calling Orca or GitHub.
- [ ] 2.4 Add stub-based pytest tests (fake `orca`/`curl` on `PATH`) covering the scenarios in `specs/orchestration-helpers`. Verify: `.venv/bin/pytest -q` passes offline; report counts.
- [ ] 2.5 Verify the scripts and skill paths agree (the skill names the scripts and their options as implemented). Verify: grep of option names in the skill against `--help` output.

## 3. Pointers and validation

- [ ] 3.1 Add a short README section pointing to the skill and scripts; add a `CLAUDE.md` pointer only if that file exists. Verify: README diff is a few lines; no new `CLAUDE.md` created.
- [ ] 3.2 Run `.venv/bin/pytest -q`, the sandbox group, and `openspec validate add-orchestration-workflow-skill --strict`; confirm `git status` clean. Verify: counts reported, output grepped for `failed`.
- [ ] 3.3 Commission a Fable review of the proposal (before implementation) and, after implementation, of the skill's accuracy against the approved workflow and its readability for agents; address findings in the same worker session. Verify: review report files exist and each finding is recorded as fixed or declined.

## 4. Left open (not implementable by the worker)

- [ ] 4.1 Try the skill in a fresh coordinator session on a real change and note gaps. Reason: needs a live Orca session and the user's judgment; do not claim it until done.
- [ ] 4.2 Verify the scripts against live Orca and a real GitHub run. Reason: needs a push and a GitHub Actions run, which only the coordinator performs.
