# Design

## Context

See proposal.md. The trusted CLI runs on the laptop in its uv environment (Q34). There is currently no persistence beyond test output. This design defines the bundle as the primary evidence and two read paths over it. Planned only.

## Goals / Non-Goals

**Goals:** Write-before-track durability; enough content to inspect, regrade, and later upload without regeneration; clear separation of original and replay evidence; completeness verification against planned records.

**Non-Goals:** MLflow integration, report generation, re-running agent interactions, database storage, remote storage, or compression/retention policies.

## Decisions

### 1. Bundle as a directory of plain files

One directory per evaluation run identified by a run ID, containing a manifest (run ID, timestamps, status, planned task/trial IDs, configuration and version hashes: prompt, benchmark/review, limits, evaluator revision, Python/dependency versions, container image digest, model/provider settings) and per-trial records (rendered requests, raw responses, physical attempts, tool arguments/results, candidate history, final source, per-check grades/failure labels, usage, cost reservations/reported cost, errors). JSON or JSON Lines are suitable; exact layout and paths are implementation choices. Records are written incrementally as trials progress so a crash or ceiling stop retains partial evidence. Writes use temp-file-then-rename to avoid torn files.

Fields owned by later changes (benchmark hash, ledger entries, MLflow IDs) are recorded when those changes supply them; this change defines where they live.

### 2. Secret exclusion

Serialisation passes through an allowlist of request fields; authorization headers, API keys, and secret environment values are never written. Tests write a run with a fake key present and assert it does not appear anywhere in the bundle.

### 3. Trace inspection

A read-only command lists runs and shows a trial's messages, tool calls/feedback, final source, and grades. It imports no API client, never starts containers, and works with Podman stopped and network disabled.

### 4. Grading replay

A command loads a bundle's final candidates and the benchmark version it references, executes hidden checks with the candidate-execution mechanism, and writes results to a separate replay record linked to the original run ID (with its own timestamp, evaluator revision, and image digest). It requires Podman, takes no model credentials, and never calls the API. Its output is described as regrading, never as agent-trial reproduction. Original grades are never overwritten. A mismatch between replay and original grades is reported, not silently reconciled.

### 5. Completeness

A check compares recorded trial IDs against the manifest's planned IDs and validates that executed checks have valid outcomes. Missing records or infrastructure/transport/budget stops mark the run incomplete; denominators stay at planned values. This change is the single owner of the completeness check; `add-reviewed-benchmark-and-graders` consumes its result and owns accounting/classification and headline exclusion.

### 6. Footprint outside the new modules

Producing this change's own sandbox evidence exposed an intermittent container leftover in `sandbox.py`, whose owning change is archived. It was fixed here and is recorded so the branch is not mistaken for purely additive: `podman create` is a separate step before `podman start --attach --interactive` (so cleanup never races a creation a killed client left in flight); removal uses `rm -f -t 0` (the PID 1 supervisor ignores SIGTERM) and is verified with `podman container exists` within one bounded time budget; container names carry the process ID so concurrent sessions on one Podman VM do not see each other's containers. `tests/test_isolation_probes.py` filters on that prefix with its assertions unchanged; `tests/test_execution_limits.py` pins the new behaviour. Evidence is in docs/progress.md.

## Risks / Trade-offs

- Bundle schema churn during day 1–3 → include a schema version in the manifest; replay refuses unknown versions with a clear message.
- Large raw responses → acceptable at 60 trials; no compression needed in scope.
- Benchmark files changed after a run → replay uses the hash recorded in the bundle and fails if the retained benchmark content does not match.

## Migration Plan

Add bundle writer and manifest, integrate with the fixture-driven controller, add inspection and replay commands, verify ignore rules, and record commands/results in progress. Rollback removes the modules; existing bundles remain readable files.
