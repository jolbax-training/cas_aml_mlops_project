# Design

## Context

See proposal.md. The repository has no MLflow integration. The agreed topology (Q34) runs the trusted CLI on the laptop in its uv environment and MLflow as a separate persistent Podman service on a localhost endpoint. The durable local bundle (Q35) is primary evidence; MLflow is a navigable secondary record. Implementation status is in tasks.md and docs/progress.md.

## Goals / Non-Goals

**Goals:** Persistent local tracking service, complete recording of retained runs including traces, identity links between tracking and bundles, outage-tolerant later upload, and independence of execution from tracking.

**Non-Goals:** Hosted or shared tracking, a second tracking platform, model registry/deployment, live dashboards beyond MLflow's own UI, recording directly from in-flight model calls as the only copy, or changing grading semantics.

## Decisions

### 1. MLflow as a persistent local Podman service

Run a pinned MLflow image as a Podman container with its backend store and artifact store on a durable host location excluded from Git, published only on a localhost port. Exact image version, port, and storage path are bounded implementation choices to document and verify. Candidate containers never receive the endpoint, credentials, or network access to it.

### 2. Record from retained bundles, never from regeneration

A recording command reads one retained bundle and writes an MLflow run whose tags include the bundle identity (run ID and content hash), benchmark version/hash, prompt version, evaluator revision, and completion status. Parameters carry model/provider/request settings and limits; metrics carry primary and diagnostic measures; artifacts carry the bundle summary and selected files. Because the source is the saved bundle, recording can run after the fact and repeatedly. Re-recording the same bundle is detected by identity rather than creating ambiguous duplicates; exact idempotence handling is an implementation choice to document.

### 3. Traces of the agent interaction

Represent each trial as an MLflow trace with spans for logical model calls, physical attempts/retries, `run_checks` tool calls and results, and final submission, carrying usage and latency where retained. Hidden acceptance expectations never enter the agent trace; grading results attach as separate evidence linked to the trial. Grading-replay evidence is recorded as distinct runs or artifacts linked to the original bundle identity, never overwriting or merging into the original trace.

### 4. Execution independent of tracking

The agent/evaluator never require MLflow to complete or save a run. If the service is unavailable, the run remains in its bundle and is marked as not yet recorded; later upload uses the same bundle. No paid response is regenerated to recover tracking.

Alternative: logging directly to MLflow during trials. Rejected because a tracking outage would then risk evidence loss and motivate paid reruns.

### 5. Trace values stay readable: out-of-range integers become strings (amendment)

Verification against MLflow 3.17.2 found that the server stores span attributes containing integers outside the signed 64-bit range (a model's `run_checks` arguments such as `123456789123456789123456789`), but `get_trace` and `search_traces(include_spans=True)` then fail with HTTP 500 (`ValueError: Value out of range` in `mlflow/tracing/utils/otlp.py`), so those traces are unreadable. `write_trial_trace` therefore converts every `int` (not `bool`) outside [-2**63, 2**63-1], recursively inside lists and dicts, to its decimal string before it reaches MLflow, and marks the affected span with the attribute `codegen_eval.int_out_of_range_stringified = true` so the conversion is visible. Only span inputs, outputs, and attributes are touched; bundles, artifacts (JSON keeps exact integers), parameters, metrics, and tags are unchanged, and the bundle remains the exact evidence.

Addendum (live re-record, 2026-11-06): the first fix did not repair the live traces because the bundles store each tool call's `arguments` as the model's raw JSON text (a `str`), which reaches the `run_checks` input, the `model_call` outputs, and later `model_call` inputs; MLflow parses such strings as JSON on read and fails on the same integer. Two options: (a) parse the arguments into a dict before writing, so the integer conversion applies; (b) rewrite JSON texts in place, with out-of-range integers as strings, keeping the value a string. Chosen (b): the arguments recur in several places (responses, request messages, tool feedback content) and all of them must be handled alike, so one rule in `stringify_big_ints` covers every span value, whereas (a) would change the type of the recorded value in some places and not others and need per-site code. A string is rewritten only when it is a JSON object or array (or, at the top level of a span value, a bare integer) that holds an out-of-range integer; any other string, and any JSON text without one, is left byte for byte, and the span is marked the same way.

Alternative: dropping or truncating the value. Rejected because the decimal string keeps the evidence.

### 6. Rewriting traces of an existing run (`record --retrace`, amendment)

Idempotence (decision 2) means a finished run is never touched, so traces written before decision 5 cannot be repaired by a plain re-record. `record --retrace` finds the finished run for the same bundle identity and replaces only its traces: new traces are written under the same MLflow run ID first, then the old ones are deleted, so a failure leaves the old traces in place (the partial new ones are removed). Run params, metrics, tags, artifacts, and replay runs are untouched; the run gains the tag `codegen_eval.traces_rewritten_at`. Without `--retrace` behavior is unchanged. With no finished run, `--retrace` falls back to a normal upload.

## Risks / Trade-offs

- MLflow trace API/version drift → pin and document the tested version; keep the bundle as authoritative.
- Partial recording on failure → recording reports incomplete uploads and can be repeated from the bundle.
- Secrets in artifacts → record only bundle content already filtered of credentials/authorization headers; test that no secret appears.
- Storage loss → durable host storage outside the container; bundles remain the recovery source.

## Migration Plan

Add the service definition and storage, the recording command, fixture-based tests, and documentation. Record a fixture bundle, then real bundles once they exist. Rollback stops the service and removes the integration without touching bundles or evaluator behavior. Update progress with observed commands and identifiers only after they are actually produced.
