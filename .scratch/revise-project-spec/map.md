# Define the agent-evaluation and MLOps project

Label: wayfinder:map
Status: resolved

## Destination

Agree on one authoritative, implementable project specification for learning agent evaluation and demonstrating a reproducible MLOps workflow within 32 working hours. The specification must define scope, system behavior, acceptance evidence, milestones, exclusions, and a worked evaluation-design example for an agent-workflow orchestrator.

## Notes

- This is a planning effort. Implementation follows the agreed specification.
- Use Wayfinder, grilling, and domain-modeling. The issue tracker is the local-Markdown fallback described by the installed Wayfinder tracker template.
- Confirmed by the user in this conversation: four working days at eight hours per day; both transferable agent-evaluation understanding and a working MLOps workflow matter.
- The implemented use case includes a bounded tool-using coding agent; the linked decisions below hold its agreed behavior and limits.
- Personal explanations/reflections are learning checkpoints and do not block reaching the project deliverables. Never invent the student's reflections.
- Keep minimal deterministic CI, local MLflow with agent traces, and a simplified locally generated HTML work-log. The linked infrastructure decision defines the agreed Podman topology and evidence requirements.
- API spending has a CHF 10 checkpoint and CHF 15 ceiling. Crossing CHF 10 alone does not stop progress. This supersedes the earlier CHF 5 checkpoint / CHF 10 ceiling discussion.
- The transfer example is a research coordinator with one worker and independent verifier per item, followed by a final check across all items. There is no existing second project. The linked transfer decision defines a worked evaluation design rather than a second implemented system.
- Existing source material: [working specification](../../docs/project_spec.md), [progress](../../docs/progress.md), and [HTML work-log proposal](../../openspec/changes/add-local-html-work-log/proposal.md). These remain the previous plan until reconciled; discussion here introduces changes that are not yet implemented.
- Local tracker: child issues live in `issues/`, ordered by filename. `Type:` and `Label:` identify the ticket type. An open, unclaimed ticket is on the frontier when every issue in `Blocked by:` is resolved. Claim by changing `Status:` to `claimed` before work; resolve by appending `## Answer`, setting `Status: resolved`, and adding a named link below. No native dependency API exists for this tracker.
- The Anthropic article is a design reference, not a requirement to reproduce every technique: https://www.anthropic.com/research/demystifying-evals-for-ai-agents

## Decisions so far

- [Define the coding agent's behavior and tools](issues/01-agent-behavior.md): bounded function-writing trials with agent-authored development checks, explicit final submission, and hidden final grading; limits and failure behavior agreed through Q12–Q17.
- [Define trustworthy execution and scoring boundaries](issues/02-execution-boundary.md): fresh restricted Podman containers per check, mandatory isolation/integrity probes, four development checks per tool call, and configurable execution limits including a 10-second deadline; agreed through Q18–Q20.
- [Define tasks, graders, and evaluator validation](issues/03-benchmark-and-graders.md): ten reviewed tasks with forty hidden checks, deterministic grading/validation, final-outcome success, and fixed denominators with incomplete runs excluded from headline comparisons; agreed through Q21–Q24.
- [Verify OpenRouter model choices and budget inputs](issues/08-openrouter-model-research.md): retained primary-source research verifies GLM's documented controls, compatible endpoints, and budget inputs; live compatibility remains a smoke-test requirement.
- [Define the experiment and spending controls](issues/04-experiment-design.md): baseline/revised prompts, sixty task trials, GLM on fixed OpenInference routing, bounded requests/retries, low reasoning effort, and a shared CHF 10 checkpoint / CHF 15 ceiling; agreed through Q25–Q33.
- [Define Podman services and reproducible evidence](issues/05-containers-and-evidence.md): host CLI, containerized local MLflow, durable bundles, distinct inspection/regrading/fixture capabilities, two deterministic CI check groups, and a simplified offline HTML work-log; agreed through Q34–Q37.
- [Transfer the evaluation method to a workflow orchestrator](issues/06-orchestrator-transfer.md): research decomposition, one worker/fresh-context verifier per item, final cross-item checks, six designed scenarios, and a reusable guide with labelled illustrative evidence; agreed through Q38–Q41.
- [Agree on four-day delivery and reconcile the specification](issues/07-delivery-and-spec.md): Q42 fixes the 32-hour schedule and exit evidence; the authoritative specification and related planning documents are consolidated and validated.

## Not yet specified

None remaining for the agreed planning destination. [The authoritative specification](../../docs/project_spec.md) contains the implementation requirements and completion checklist. Functional smoke tests, worker hardening, runner/version verification, and actual experiment evidence remain implementation work and must not be described as completed by this map.

## Out of scope

- Implementing the project during this planning effort.
- Building the agent-workflow orchestrator as a second working system.
- Integrating a second tracking platform alongside MLflow.
- Requiring personal reflection completion as a delivery gate.
- Hosting or publishing the HTML work-log; it remains locally readable.
