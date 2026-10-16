# Personal learning journal

This journal records the learning process behind the MLOps evaluation project. Add an entry after each milestone and whenever an experiment, failure, or design decision changes your understanding. Use links to code, CI runs, MLflow runs, and saved results as evidence for the final report. Write personal reflections in your own words.

This is personal source material for the planned local HTML work log, not a substitute for its factual status and run records. [Progress and decisions](progress.md) records those facts. Select student-authored passages for the report; unfinished reflection prompts remain unfinished.

Entries below preserve the decisions and uncertainty at the time they were written. The September plan for exactly 30 tasks and an unresolved rubric is superseded by the 2026-10-16 [working specification](project_spec.md): there is no formal rubric, the minimum is 10 reviewed tasks, and the complete laptop loop comes before CI and MLflow integration. The historical test claims below are not a statement of current environment readiness.

## Entry template

### Date — Milestone or experiment

- **Learning question:** What did I want to understand?
- **Initial expectation:** What did I think would happen, and why?
- **Work attempted:** What did I build, change, or test?
- **Evidence:** What actually happened? Link to runs, results, commits, or relevant files.
- **Interpretation:** What does that evidence support, and what remains uncertain?
- **What I learned:** What changed in my understanding of evals or MLOps?
- **Next decision:** What will I do differently or investigate next?
- **Final-report note:** Which result or lesson may be worth showing in the report?

## Entries

### 2026-09-25 — Project framing

- **Learning question:** How can a code-generation task help me learn to build and use an MLOps evaluation pipeline?
- **Decisions recorded:** The evaluation pipeline is the main outcome. The current design uses 30 function-generation tasks, behavioral tests, prompt comparison, CI, and MLflow. Deepchecks and DVC are optional extensions.
- **Evidence:** [Working project spec](project_spec.md).
- **Personal reflection:** _Add your own starting expectations and what you hope to learn before implementation begins._
- **Next decision:** Confirm the course rubric and time available, then define the first implementation milestone.

### 2026-09-25 — Offline evaluator pilot

- **Learning question:** Can the evaluator classify known good and bad generated functions consistently while keeping expected answers outside the code-execution container?
- **Work attempted:** Added pilot data validation, a static response-contract check, isolated per-case execution with Podman, and scoring outside the container.
- **Evidence:** [Offline evaluator tests](../tests/test_evaluate.py), [container integration tests](../tests/test_sandbox_integration.py), and [run instructions](../README.md). The offline suite passed 21 checks; the Podman integration suite passed 8 checks, including input mutation, timeout, output limit, and isolation probes.
- **Initial expectation:** _Write what you expected before inspecting the results._
- **Interpretation and what I learned:** _In your own words, explain one failure label that changed your understanding of evals._
- **Remaining uncertainty:** The case-pass denominator policy was proposed as fixed; the full benchmark and CI behavior still need design and validation.
- **Next decision:** Review the failure categories and confirm how unexecuted cases contribute to the case pass rate.
