Text equivalent of the one-trial sequence diagram ([`run_flow_sequence.drawio.svg`](run_flow_sequence.drawio.svg), editable in draw.io), verified against `src/codegen_eval/` at commit `37968d8` of `main`. It is the supplement to the [experiment-lifecycle activity diagram](run_flow_activity.md): the activity diagram shows the whole experiment and every ending, this one shows the exact call order inside **one trial**. Participant headers carry the name of the logical-diagram box and its status (**IMPLEMENTED**, **PARTIAL: NO LIVE RUN YET**, **PENDING**); messages carry no status. OpenRouter is `EXTERNAL` and `PHASE 2` (dashed). No live run has happened, so the diagram shows control flow only: no result, spend, or run identifier.

## Participants (left to right)

- `rr`: run_recording.py; + experiment.py; PARTIAL: NO LIVE RUN YET — code: `run_variant, run_recorded, RecordingClient`
- `tr`: trial.py; the bounded agent loop; IMPLEMENTED — code: `run_trial`
- `oc`: openrouter_client.py; ModelClient, model_client.py; PARTIAL: NO LIVE RUN YET — code: `OpenRouterClient.complete`
- `lg`: ledger.py; spend ledger file; PARTIAL: NO LIVE RUN YET — code: `Ledger.reserve, settle, keep`
- `or`: OpenRouter; (EXTERNAL, PHASE 2); PENDING — code: `chat completions endpoint`
- `bd`: bundle.py; run bundle writer; IMPLEMENTED — code: `BundleWriter`
- `ml`: mlflow_tracking.py; MLflow recorder; PARTIAL: NO LIVE RUN YET — code: `bundle_recorder, record_bundle`
- `rc`: run_checks.py; development tool; IMPLEMENTED — code: `run_checks`
- `ev`: evaluate.py + contract.py; grader on the host; IMPLEMENTED — code: `grade_trial, score_case`
- `sb`: sandbox.py + limits.py; host launcher; IMPLEMENTED — code: `execute_check, run_case`
- `wk`: worker.py; in the candidate container; IMPLEMENTED — code: `SUPERVISOR, EXECUTOR`

The trust boundary is the dashed frame `TRUST BOUNDARY; candidate container` around `worker.py`. Only two arrows touch it, both with the host launcher `sandbox.py`: the payload in (candidate source, the function name, one check's or one case's arguments, a per-check token) and one bounded report out. There is no message between the container and OpenRouter, the ledger, the bundle, MLflow, or Podman controls, and expected answers never enter the container (`evaluate.score_case` and `run_checks._check_feedback` compare on the host).

## Messages in order

1. rr → rr: client_for(): OpenRouterClient;; RecordingClient(sink) — code: `experiment_cli.client_for, run_recording.RecordingClient`
2. rr → tr: run_trial(task, client, prompt, limits) — code: `run_recording.run_recorded -> trial.run_trial`
3. tr → rr: complete(request): tool_choice auto, or none — code: `trial.run_trial -> RecordingClient.complete`
4. rr → bd: append_call(request): fsync, before the send — code: `run_recording.RecordingClient.complete -> bundle.BundleWriter.append_call`
5. rr → oc: inner.complete(request) — code: `RecordingClient.complete -> OpenRouterClient.complete`
6. oc → oc: input_token_bound(body) — code: `openrouter_client.input_token_bound`
7. oc → rr: ModelFailure(request_rejected): no reserve, no send — code: `openrouter_client.OpenRouterClient.complete`
8. oc → lg: reserve(amount): before every send — code: `ledger.Ledger.reserve`
9. lg → oc: BudgetCeiling (refusal event) — code: `ledger.BudgetCeiling`
10. oc → rr: ModelFailure(budget_ceiling) — code: `openrouter_client._attempt`
11. oc → or: POST chat completions, key in header — code: `transport.post(config.endpoint, ...)`
12. or → oc: reply, or transport failure — code: `openrouter_client._interpret`
13. oc → lg: settle(...) or keep(...) — code: `ledger.Ledger.settle, ledger.Ledger.keep`
14. oc → oc: transient failure and retries left: reserve again — code: `openrouter_client.OpenRouterClient.complete`
15. oc → rr: ModelResponse, or ModelFailure(...) — code: `openrouter_client.OpenRouterClient.complete`
16. rr → bd: append_call(response) — code: `run_recording.RecordingClient.complete -> bundle.BundleWriter.append_call`
17. rr → tr: response — code: `run_recording.RecordingClient.complete`
18. tr → tr: no_submission (request_rejected) — code: `trial.run_trial: ModelFailure request_rejected`
19. tr → tr: infrastructure_incomplete (kind) — code: `trial.run_trial`
20. tr → tr: no_submission (tool_request_when_disabled) — code: `trial.run_trial`
21. tr → rc: run_checks(arguments, task, runner) — code: `trial._handle_tool_calls -> run_checks.run_checks`
22. rc → sb: execute_check(source, function_name, args) — code: `run_checks.run_checks -> sandbox.execute_check`
23. sb → wk: podman create / start; stdin: source, args, token — code: `sandbox.execute_check`
24. wk → sb: one bounded report on stdout — code: `worker.SUPERVISOR`
25. sb → rc: ExecutionResult — code: `sandbox.ExecutionResult`
26. rc → rc: compare with the agent's expected value — code: `run_checks._check_feedback`
27. rc → tr: feedback (infrastructure status: no feedback, trial ends) — code: `run_checks.ToolResult.feedback; trial._handle_tool_calls`
28. tr → tr: no_submission (no_final_message) — code: `trial.run_trial`
29. tr → tr: validate_source(content): submitted — code: `contract.validate_source, trial.run_trial`
30. tr → rr: TrialResult — code: `trial.run_trial`
31. rr → ev: grade_trial(task, result) — code: `run_recording.run_recorded -> grader = evaluate.grade_trial`
32. ev → ev: no container: four checks unexecuted — code: `evaluate.grade_trial`
33. ev → sb: run_case(source, task, case) — code: `evaluate.grade_trial -> sandbox.run_case`
34. sb → wk: podman create / start; stdin: source, args, token — code: `sandbox.execute_check`
35. wk → sb: one bounded report on stdout — code: `worker.SUPERVISOR`
36. sb → ev: ExecutionResult — code: `sandbox.ExecutionResult`
37. ev → ev: score_case: compare with hidden expected (host only) — code: `evaluate.score_case`
38. ev → rr: TrialGrade — code: `evaluate.TrialGrade`
39. rr → bd: write_trial(record): atomic, manifest hash — code: `bundle.BundleWriter.write_trial`
40. rr → rr: if infrastructure_status is budget_ceiling:; stop the schedule loop — code: `run_recording.run_recorded`
41. rr → bd: finish(): once, after the last trial — code: `bundle.BundleWriter.finish`
42. rr → ml: record_run(bundle, variant): once per run — code: `experiment.run_variant -> mlflow_tracking.bundle_recorder`

## Fragments

- `loop` `[model_calls < 4: at most four logical model calls (AgentLimits)]`: the agent loop of `trial.run_trial`; tools are offered (`tool_choice` auto) only while model calls and tool attempts remain (`max_model_calls` 4, `max_tool_attempts` 3), otherwise `tool_choice` is none and the tool definitions are still sent.
- `alt` `[bound above max_input_tokens]` / `[else: within the bound]`: the pre-send check in `OpenRouterClient.complete`; a rejected request is never reserved or sent.
- `loop` `[each physical attempt, retries included]` containing `alt` `[reservation refused: total + amount > CHF 15]` / `[else: reserved]`: `ledger.reserve` comes first; a refusal records a `refusal` event and returns `ModelFailure(budget_ceiling)`; otherwise the POST, the reply, and `settle` or `keep`. A transient failure with retries left (at most one per request and two per trial) reserves again.
- `alt` with five outcomes in the code order of `trial.run_trial`: `ModelFailure(request_rejected)` ends the trial as `no_submission`; any other `ModelFailure` ends it `infrastructure_incomplete`; a tool call while tools are disabled ends it `no_submission` (`tool_request_when_disabled`); a tool call with tools enabled runs `run_checks.run_checks` (only the first call named `run_checks` executes, other calls get error feedback), with an inner `loop` per check (at most 4 per request), and an infrastructure status from a check ends the trial with no feedback; no content ends it `no_submission` (`no_final_message`), otherwise the content is the final submission, checked by `contract.validate_source`, and the trial ends `submitted` (a contract issue is recorded and never repaired).
- `alt` `[no_submission, infrastructure_incomplete, or a contract issue]` / `[else: submission without a contract issue]` with an inner `loop` `[each executed case, up to 4]`: `evaluate.grade_trial` starts no container for the first branch; for the second, each executed case runs through `sandbox.run_case` in a fresh container (a `payload_too_large` outcome starts no container).

After the trial (outside the loop frames): `finish()` once after the last trial, then `record_run(bundle, variant)` once per run (`mlflow_tracking.bundle_recorder`; the run marker is finalised after it). The recorder is idempotent: it searches MLflow for an earlier upload of the same bundle digest, then uploads; results are never read back, and an outage writes `tracking.json` with `not_recorded` without changing the run.

Maintenance: edit the diagram in draw.io (File > Properties: Compressed off), save it as `.drawio.svg`, then edit this page in the same change; `tests/test_run_flow_diagrams.py` checks the labels, names, order claims, and the boundary against the source tree.
