# Proposal

## Why

The evaluator, benchmark, agent loop, and execution boundary need automated, repeatable evidence that they behave as specified on every change. A minimal deterministic GitHub Actions setup provides that evidence without model credentials or paid generation.

## What Changes

- Add two required deterministic GitHub Actions check groups: evaluator/benchmark/agent-loop tests, and real Podman execution/isolation tests.
- Run them on a compatible Linux runner with documented, pinned dependencies and container images.
- Use fixtures only: no model credentials, no paid generation, and no candidate pass-rate thresholds as gates.
- Verify failure classification, execution limits, and scoring with deterministic fixtures and probes.
- Retain CI evidence (workflow run identifiers and results) in progress once real runs exist.

## Capabilities

### New Capabilities

- `continuous-integration`: Automatically run deterministic evaluator, benchmark, agent-loop, and Podman isolation checks without model access.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation adds a GitHub Actions workflow, possibly a small script to provision/verify Podman and the pinned image on the runner, CI documentation, and progress entries. Test suites themselves come from upstream changes; this change wires and verifies them. No paid API access, secrets, or new runtime behavior is introduced.

## Dependencies and milestone

- **Milestone:** Day 3, "CI" timebox (2h) in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan); day-3 exit evidence includes passing CI. The agreed sequence adds CI only after the local path works.
- **Upstream:** `harden-candidate-execution` (isolation/limit/integrity probes), `add-bounded-agent-loop` (recorded-response interaction fixtures), `add-reviewed-benchmark-and-graders` (benchmark validation and evaluator fixtures). `add-run-bundles-and-grading-replay` tests may also be included when deterministic.
- **Downstream:** `prepare-reproducible-demo` cites retained CI evidence; `add-local-html-work-log` references CI identifiers.
- **Optional/excluded:** Automatic paid/live CI, model success thresholds, and deployment pipelines are out of scope.

Completion evidence is both check groups passing on GitHub Actions with retained run identifiers, documented runner/dependency/image versions, and a demonstrated failure when a fixture expectation is broken. No CI success is claimed by this plan.

## Traceability

- Wayfinder [issue 05](../../../.scratch/revise-project-spec/issues/05-containers-and-evidence.md): Q36, Answer bullets 5 and 8.
- Specification: "Evidence, MLflow, CI, and replay" in [docs/project_spec.md](../../../docs/project_spec.md); completion checklist item on CI.
