# Brief templates

Fill the `<placeholders>`, then pass the text with `worker-start --spec` (or `--terminal` for follow-ups). Keep one source of truth: edit these templates, not copies.

Placeholders: `<change>` OpenSpec change name; `<branch>` its `barahjos/<change>` branch; `<report-path>` file the reviewer writes; test commands come from the README "Verify" section.

## Worker brief (shared rules)

```text
COMMON RULES: You work in your own Orca child worktree on branch <branch>, created from main of this repository (Python 3.12, uv; run `uv sync --python 3.12` first).
Tests: `uv sync --python 3.12 --group tracking`, then `.venv/bin/pytest -q`. Podman tests: `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox` (the pinned Podman image is present and the VM runs). Also run `.venv/bin/python scripts/build_work_log.py --check`. Module CLIs need `PYTHONPATH=src` and run from the repository root (pytest does not); take commands from README.md and docs/demo.md instead of guessing module names.
Use the openspec-apply-change skill for <change>. Tick a task in its tasks.md only when it is done and evidenced. Follow docs/project_spec.md, the change's proposal, design, and specs, and the accepted decisions the coordinator names. Match the existing code style.
Leave tasks that need paid calls, a GitHub push or Actions run, or user judgment unchecked, and list them with the reason. Report every paid or API call as left-over work and read no API key (this brief never contains one; the coordinator runs paid commands itself after the user approves). Leave learning-journal reflections to the user; report only results, run IDs, and evidence you produced.
Edit only files this change owns, never the Wayfinder files under `.scratch/`, other changes, or parallel workers' files; if one of them must change, say so in worker_done.
Commit on <branch> with clear messages ending with the line `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. The coordinator pushes, merges, and archives.
Before worker_done: all tests pass (state the counts), `openspec validate <change> --strict` passes, `git status` is clean.
worker_done body: branch name, final commit hash, tasks done and left (with reasons), test evidence. A Fable reviewer checks your work; findings return to you as a follow-up in this same terminal.
```

## Fix-loop brief (sent to the same worker terminal)

```text
Fix ALL findings from the Fable review in <report-path> on your branch (same worktree). Where a finding is wrong or out of scope, say why and leave the code as is. Same rules as before: commit with the Sonnet co-author line, leave push, merge, and archive to the coordinator, keep tests and `openspec validate <change> --strict` passing, finish with a clean `git status`.
worker_done: list each finding number as fixed or declined (with the reason) and give the final commit hash.
```

## Reviewer brief

```text
You are an independent reviewer. READ-ONLY: change no file except your report at <report-path>, and make no commit.
Review the implementation on the current branch against main (`git diff main...HEAD`, `git log main..HEAD`) for OpenSpec change <change>. Compare it with proposal.md, design.md, specs/**/spec.md, tasks.md, docs/project_spec.md, and the accepted decisions the coordinator names.
Check: every ticked task is done and evidenced; each requirement and scenario is implemented and tested; no invented evidence or results, no learning-journal reflections written, no paid API use; correctness and security (especially candidate execution and scoring integrity); edits outside the change's ownership; tests that actually test something.
Run `uv sync --python 3.12 --group tracking`, `.venv/bin/pytest -q`, the sandbox group when relevant (`CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`), and `openspec validate <change> --strict`; quote real counts.
Report: a numbered findings list, each with severity (blocker, major, minor), file:line, problem, and suggested fix. When nothing is wrong, say so explicitly.
Send worker_done with outcome succeeded, the counts per severity, and `--report-path <report-path>`.
```

For a proposal-only review, replace the code comparison with a check of the artifacts against the approved workflow description and the existing `openspec-*` skills; no tests beyond `openspec validate`.
