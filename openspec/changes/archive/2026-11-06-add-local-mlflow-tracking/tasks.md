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

- [x] 4.1 Record the actual required comparison bundles once `run-prompt-comparison` produces them, and verify parameters/metrics/traces against bundle content. Done 2026-11-06: params, metrics, tags, artifacts verified against the bundles (see docs/progress.md, 2026-11-06), traces after the 5.4 re-record: 60 of 60 readable and matching.
- [x] 4.2 Update README/progress with exact tested commands, versions, and actually observed MLflow run identifiers, and register reviewed identifiers for the work log; do not record identifiers before they exist. Done 2026-11-06: commands, versions (MLflow image v3.17.2, mlflow-skinny 3.17.2) and the observed MLflow run identifiers are in docs/progress.md, README.md and docs/comparison_evidence.md (registered reviewed work-log source).

## 5. Out-of-range integers in traces (amendment after verification)

- [x] 5.1 Convert integers outside the signed 64-bit range to decimal strings in span inputs/outputs/attributes, mark the span, and leave bundles, artifacts, parameters, and metrics unchanged (test first).
- [x] 5.2 Add `record --retrace` to replace only the traces of an existing run for the same bundle identity, with offline tests and README documentation.
- [x] 5.3 Also rewrite JSON-text strings (the model's raw tool-call `arguments`, tool feedback) that hold integers outside int64, where the string is the whole span input/output/attribute value (nested strings stay as sent), and mark the span; tested with a fixture in the real bundle shape (see design addendum).
- [x] 5.4 Re-record the five unreadable traces' runs against the live service and confirm all 60 traces are readable (coordinator; writes to the live service). Then close 4.1 and 4.2. Done 2026-11-06 by the coordinator on 6deb36c code: `PYTHONPATH=src .venv/bin/python -m codegen_eval.mlflow_tracking record <run_id> --retrace --tracking-uri http://127.0.0.1:5001` for 20261103T053309Z-280182 and 20261103T095324Z-d25905 ("already recorded, traces replaced", same MLflow runs 930a188254d34d279a88a7613ea55518 and bcddf5c9561c43129504555b020a7557); a read-only check then read all 60 traces with `get_trace` (30 per run, every trial matched, CHAT_MODEL/TOOL/LLM span counts equal to the records' model calls, tool attempts and attempts), the int64 marker on exactly 5 `run_checks` spans (2 baseline, 3 revised), and no "Value out of range" error in the server log afterwards.
