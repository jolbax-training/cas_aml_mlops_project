# Tasks

Progress is tracked by the checkboxes below and the dated entry in [docs/progress.md](../../../docs/progress.md). Image version, port, storage path, and command names are documented in the README.

## 1. Local tracking service

- [x] 1.1 Add a pinned MLflow Podman service definition with durable host storage excluded from Git and a localhost-only endpoint; document start/stop/status commands.
- [x] 1.2 Verify data survives a container restart and that candidate containers have no route, configuration, or credentials for tracking.

## 2. Recording from retained bundles

- [x] 2.1 Implement a recording command that reads one retained bundle and writes parameters, metrics, artifacts, and identity tags (bundle ID/hash, benchmark, prompt, evaluator revision, completion status) without importing the model client.
- [x] 2.2 Represent each trial as a trace with model-call, physical-attempt/retry, `run_checks`, and submission spans; attach grading evidence separately and keep hidden expectations out of the interaction trace.
- [x] 2.3 Record grading-replay evidence as distinct linked records; detect re-recording of the same bundle identity and document the chosen behavior.

## 3. Outage tolerance and safety tests

- [x] 3.1 Add fixture-based tests against a temporary tracking store covering complete and incomplete bundles, trace structure, replay separation, and absence of secrets.
- [x] 3.2 Demonstrate a run completing with tracking stopped, then later upload of the same bundle with no model calls; verify the agent/evaluator never require the service.

## 4. Evidence and documentation

- [ ] 4.1 Record the actual required comparison bundles once `run-prompt-comparison` produces them, and verify parameters/metrics/traces against bundle content.
- [ ] 4.2 Update README/progress with exact tested commands, versions, and actually observed MLflow run identifiers, and register reviewed identifiers for the work log; do not record identifiers before they exist.

## 5. Out-of-range integers in traces (amendment after verification)

- [ ] 5.1 Convert integers outside the signed 64-bit range to decimal strings in span inputs/outputs/attributes, mark the span, and leave bundles, artifacts, parameters, and metrics unchanged (test first).
- [ ] 5.2 Add `record --retrace` to replace only the traces of an existing run for the same bundle identity, with offline tests and README documentation.
- [ ] 5.3 Re-record the five unreadable traces' runs against the live service and confirm all 60 traces are readable (coordinator; writes to the live service). Then close 4.1 and 4.2.
