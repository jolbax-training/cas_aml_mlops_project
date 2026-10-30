Text equivalent of the figure above, as of 2026-10-30. **Implemented** means code exists in this repository today; **planned** means it is specified in the [working specification](project_spec.md) but not built. Status comes from the [progress record](progress.md), not from this page.

**Implemented**

1. The offline pilot loads three tasks and twelve cases, validates one-function Python source without running it, runs one case at a time in a restricted Podman container, and scores the returned value outside that container.
2. The container receives only source and one case's arguments. Expected answers, scoring, credentials, and repository files stay outside it. The execution boundary has not yet had its integrity review, so live model comparisons stay disabled.
3. This report builder turns the selected Markdown sources into `report/index.html`.

**Planned**

1. Task instruction and signature plus a versioned prompt go to a bounded coding agent (four model calls, three development-tool attempts, at most four checks per request) that calls the model through OpenRouter.
2. The agent may write its own example checks. `run_checks` runs them in fresh containers and returns bounded development feedback. This feedback never contains hidden expected answers.
3. An explicit final submission passes source validation and then separate hidden acceptance grading in fresh containers.
4. Results are written to durable local run bundles first. Grading replay re-runs hidden grading on saved final candidates without any model generation, and still uses Podman. Containerized local MLflow records the runs after the local bundles exist.
5. Deterministic CI covers fixtures and probes only. A baseline and one revised prompt are compared on the same benchmark, and reviewed Markdown summaries of that comparison are registered as report sources.

Sections of this report whose evidence does not exist yet are labelled pending. No result, URL, or reflection is invented to fill them.
