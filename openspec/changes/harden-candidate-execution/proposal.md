# Proposal

## Why

Every later result depends on candidate code being unable to read hidden answers, reach credentials or services, or forge its own score. The pilot isolates the host but runs candidate code and worker reporting in one Python process and still defaults to an eight-second deadline, so scoring integrity is unverified and must be established before any live comparison is trusted.

## What Changes

- Use one restricted execution mechanism for both agent-authored development checks and hidden acceptance checks, with a fresh disposable Podman container for every individual check.
- Pass only candidate source, the function name, and that check's arguments into candidate execution; keep expected answers and comparison logic in trusted orchestration.
- Deny repository mounts, credentials, tracking access, the Podman control socket, and network access; use a read-only root filesystem, unprivileged user, dropped capabilities, and restricted temporary writes.
- Apply the agreed configurable limits: 10-second deadline per check (including container startup/code loading; cleanup separate), 128 MiB memory, 1 CPU, 32 processes, 16 MiB writable temporary storage, 64 KiB source-and-arguments payload, 32 KiB captured print output, 64 KiB worker-protocol output. The 10-second deadline supersedes the pilot's eight-second default.
- Harden worker reporting so candidate code cannot forge a result or conceal input mutation; classify container unavailability and broken worker protocols as infrastructure outcomes, not candidate failures.
- Require isolation probes (host files, host environment, network, read-only paths, timeout, excessive output, input mutation) plus targeted forged-worker-response and concealed-mutation probes, and a written threat model with residual limitations.

## Capabilities

### New Capabilities

- `candidate-execution`: Run one untrusted candidate function call per fresh restricted container under fixed limits, returning trustworthy raw outcomes to trusted scoring.

### Modified Capabilities

None. The main capability inventory is empty.

## Impact

Implementation affects `src/codegen_eval/sandbox.py` (worker protocol, limits, container flags), its callers in the evaluator, configuration for limits, and focused Podman integration/probe tests. No model API, MLflow, or CI is introduced here. Exact worker hardening technique is an implementation choice bounded by the requirements below.

Completion evidence is passing isolation and scoring-integrity probes in each execution environment actually used, recorded in progress with environment/Podman/image details, plus a documented threat model and residual limitations. Production security certification is out of scope. Passing ordinary correctness tests alone is not exit evidence. This proposal is a plan; nothing here is implemented.

## Dependencies and milestone

- **Milestone:** Day 1, execution boundary/probes timebox (3h) in the [four-day plan](../../../docs/project_spec.md#four-day-delivery-plan).
- **Upstream:** The existing offline pilot evaluator and pinned Python image only. Restoring the pinned image is a prerequisite environment step.
- **Downstream:** `add-bounded-agent-loop` (`run_checks` reuses this mechanism), `add-run-bundles-and-grading-replay`, `add-reviewed-benchmark-and-graders` (evaluator fixtures for limits), `add-deterministic-ci` (Podman check group), and `run-prompt-comparison`, which must not start until a demonstrated scoring bypass is resolved.

## Traceability

- Wayfinder: [issue 02 — Define trustworthy execution and scoring boundaries](../../../.scratch/revise-project-spec/issues/02-execution-boundary.md), Q18 (assurance), Q19 (execution/information boundary), Q20 (limits, 10-second deadline, four-check batch).
- Specification: [Execution and scoring integrity](../../../docs/project_spec.md#execution-and-scoring-integrity).
- The four-check batch limit on `run_checks` (Q20) is enforced by the tool controller in `add-bounded-agent-loop`; this change provides per-check execution.
