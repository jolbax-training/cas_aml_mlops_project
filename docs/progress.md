# Project progress and decisions

Updated 2026-10-16. This is an editable factual source for the planned local HTML work log. [The working specification](project_spec.md) defines acceptance criteria. Personal reflections belong in the [learning journal](learning_journal.md).

## Current status

The project is at the offline pilot stage. The first major milestone is a complete laptop generation/evaluation loop with local evidence and offline replay, understood before adding GitHub Actions or MLflow. The report remains Markdown source material until its HTML generator is implemented.

| Area | Verified state as of this review | Next evidence needed |
| --- | --- | --- |
| Benchmark | Three tasks and 12 cases in [pilot data](../data/pilot_tasks.json) | Independent answer review and a frozen minimum of 10 tasks, 40 cases, 20 edge cases across five categories |
| Evaluator | Dataset validation, static source contract, per-case Podman execution, and external scoring implemented | Local loop connected to generation, with complete saved request/response/result bundles |
| Offline checks | Earlier check in this task: 21 passed, eight sandbox tests skipped | Retained run output for the next milestone; later deterministic CI evidence |
| Podman | CLI 6.1.4 and VM reachable outside the task sandbox; pinned image absent on latest check | Acquire the documented image and rerun isolation/integration checks |
| Container checks | Latest check: eight failed with infrastructure errors; a diagnostic case returned `image not known` | Successful execution after restoring the image; review worker-protocol scoring integrity before live candidates |
| OpenSpec | Initialized with `spec-driven` configuration and six Codex skills; no changes/specs authored | Use for scoped implementation changes as needed |
| Version control / CI | Local Git repository initialized; initial commit captures the pilot and planning baseline. No remote or Actions workflow | GitHub/CI integration after the laptop milestone |
| Live generation / tracking | No OpenRouter client, saved live run workflow, or MLflow integration implemented | First a local pilot loop and replay; then tracking; finally two complete comparable experiments |
| Report / demo | Markdown sources exist; HTML generator and `report/index.html` do not | Local report build after the loop works, then documented demo and replay |

The test and connection observations above come from earlier checks in this task, not newly rerun checks during this documentation revision. Raw outputs are in the task conversation, not retained repository artifacts yet. No CI or MLflow result links exist yet. The September journal records an earlier successful container run; that historical result does not resolve the current missing-image condition.

## 2026-10-16 — Scope and delivery decisions

- **Context:** Self-directed course-related work, no formal assignment or rubric, roughly four weeks available. Exact demo date remains to be confirmed.
- **Goal:** Demonstrate the complete MLOps workflow using Python code generation as the evaluation use case.
- **Sequence:** The first major milestone is a working, understood laptop generation/evaluation loop using Podman and local saved results. Add GitHub Actions and MLflow only after this milestone passes. OpenRouter supplies live generation; replay and deterministic checks remain offline.
- **Benchmark:** Adopt 10 independently reviewed tasks as the planning minimum, two per category across five categories, each with four cases. Keep 30 tasks as a stretch target. Freeze the selected benchmark before the comparison.
- **Experiment:** One baseline and one revised-prompt complete run, with fixed model/settings/benchmark and one candidate per task. Record improvements, regressions, unchanged outcomes, and limits; improvement itself is not an acceptance requirement.
- **Deliverables:** Repository, continuously updated local HTML work log generated from Markdown, and a runnable final demo. No publishing or hosting requirement.
- **Report:** Planned single entry point `report/index.html`. Preserve editable sources and dated evidence; do not invent student reflections or missing run links.
- **Priority:** Reproducibility, isolated execution, independent benchmark review, CI evidence, and complete MLflow records come before larger datasets, automatic live CI, Deepchecks, or DVC.
- **Superseded:** Exactly 30 tasks as a completion gate; pending rubric/artifact questions; automatic paid CI as a required path; introducing CI/MLflow before the local breakthrough.
- **Evidence:** User scope decisions recorded in this task; [working specification](project_spec.md) and [OpenSpec configuration](../openspec/config.yaml). This entry records decisions, not personal learning claims.

## Next milestone: local loop

1. Restore the pinned image using the [setup instructions](../README.md) and rerun the container checks. Distinguish task-sandbox socket restrictions from actual Podman availability.
2. Review and document execution and scoring-integrity boundaries before live candidate execution.
3. Choose model/settings and a bounded API budget, then build the local request → generation → evaluation → saved-results path on the three-task pilot. Demonstrate offline replay and inspect a pass and a failure.
4. Record what each stage does and the student's interpretation of the evidence. Only then integrate CI/MLflow, expand/freeze the reviewed minimum benchmark, and build the report.

No implementation or runtime changes were made by this planning revision. Validation confirmed that local Markdown links resolve across all six Markdown documents, the documented pilot counts match the JSON dataset, and the OpenSpec YAML parses with its schema, context, and artifact rules. Application tests were not rerun for this documentation-only change. See the specification for the four-week sequence and remaining decisions.

## 2026-10-16 — Initial repository baseline

- **Action:** Establish the first local commit of source, tests, pilot data, editable documentation, dependency lockfile, and OpenSpec configuration/skills.
- **Exclusions:** Virtual environments, caches, local credentials, generated run bundles, MLflow storage, generated HTML, and machine/editor state are ignored. Curated fixtures and editable Markdown remain versioned.
- **Scope:** No remote configured or push performed. The local-first milestone and later CI/MLflow sequence remain unchanged.
- **Evidence:** The repository's initial commit and its file list; no commit hash is embedded in this entry because it is part of that commit.

## Future evidence entries

After each milestone or experiment, append the date, purpose, relevant versions, exact commands, observed result, local artifact paths and available CI/MLflow identifiers, limitations, decision, and next step. Update the status table and regenerate the report once the generator exists. Label incomplete runs explicitly; keep personal reflections in the student's own words.
