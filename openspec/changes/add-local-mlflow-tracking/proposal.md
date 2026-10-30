# Proposal

## Why

Both comparison runs must be completely recorded in containerized local MLflow with agent/model/tool traces, so the experiment can be navigated and compared through a standard tracking interface. Recording must never become a source of lost evidence or new paid generation, which is why it builds on the durable local run bundle rather than on live execution.

## What Changes

- Run MLflow as a persistent local Podman service with durable local storage outside ephemeral containers and a localhost tracking endpoint.
- Record each evaluation run from its retained local bundle: parameters, metrics, artifacts, and traces of the trial/model/tool interactions, linked to the bundle identity and grading evidence.
- Keep the original agent trace distinct from later grading-replay evidence in tracking.
- Support later upload of an already retained bundle after a tracking outage, without regenerating paid responses.
- Keep candidate containers without tracking access or credentials, and keep the agent/evaluator runnable when MLflow is stopped.
- Document the service start/stop, recording, and navigation commands once they are implemented and tested.

## Capabilities

### New Capabilities

- `experiment-tracking`: Record retained local evaluation runs, their agent traces, and grading evidence in a containerized local MLflow service.

### Modified Capabilities

None. The main capability inventory is empty; this change remains unimplemented.

## Impact

Implementation affects a local MLflow Podman service definition and persistent storage location, a recording/upload command reading retained bundles, an MLflow dependency locked through uv, focused tests using a temporary or fixture tracking store, setup documentation, and progress/report sources. MLflow stores remain excluded from version control. No model API, benchmark, or evaluator semantics change.

## Dependencies and milestone

- **Milestone:** Day 3, "MLflow/traces" timebox (2h) in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan). Exit evidence for day 3 includes two complete comparable runs retained locally and in MLflow.
- **Upstream:** `add-run-bundles-and-grading-replay` (bundle identity, layout, and grading-replay evidence are the recording source). The local path established on day 1 precedes this integration, per the agreed sequence. Trace content depends on `add-bounded-agent-loop` and `add-openrouter-client-and-budget-ledger` producing the retained interactions.
- **Downstream:** `run-prompt-comparison` records both required runs here; `add-local-html-work-log` references recorded MLflow identifiers; `prepare-reproducible-demo` navigates them.
- **Optional/excluded:** A second tracking platform, hosted tracking, and remote artifact stores are out of scope.

Completion evidence is a running local service with persistent data surviving a container restart, a bundle recorded with parameters/metrics/artifacts/traces linked to its identity, a demonstrated outage-then-upload path without new generation, and documented tested commands. No MLflow run is claimed by this plan.

## Traceability

- Wayfinder [issue 05](../../../.scratch/revise-project-spec/issues/05-containers-and-evidence.md): Q34 (topology), Q35 (bundle before recording, later upload without regeneration), Answer bullets 1, 2, and 4.
- Specification: "System and local-first sequence" and "Evidence, MLflow, CI, and replay" in [docs/project_spec.md](../../../docs/project_spec.md); completion checklist item on MLflow recording.
