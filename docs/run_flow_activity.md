Text equivalent of the experiment-lifecycle activity diagram ([`run_flow_activity.drawio.svg`](run_flow_activity.drawio.svg), editable in draw.io), verified against `src/codegen_eval/` and `scripts/` at commit `37968d8` of `main` (no code changed on the branch). The [physical view](architecture_physical.md) shows where things run and the [logical view](architecture_logical.md) which components exist; this view shows the **order**: when the whole experiment starts, what must hold before a run, what one `run` command does, and every way a run or a command ends. A supplement, the [one-trial sequence diagram](run_flow_sequence.md), shows the exact call order inside one trial. **No live run has happened**: no model call, spend, or result exists, so none is shown. Lane headers carry the status of their modules (**IMPLEMENTED**: code exists and its tests ran; **PARTIAL: NO LIVE RUN YET**: built and tested offline only; **PENDING**: the evidence does not exist); action and decision nodes carry no status. Phase-2 and external elements (OpenRouter, the paid smoke trial) have a dashed outline and the literal tags `EXTERNAL` and `PHASE 2`.

## How the code differs from a one-loop picture

1. **One `run` command runs one variant.** `experiment_cli run --variant baseline` and `run --variant revised` are two separate invocations, each writing its own bundle. The diagram draws the `run` command once as a sub-activity (the dashed frame) and calls it twice from the lifecycle. The revised prompt is unset in `experiments/prompt_comparison_v1.json` today, so a `revised` run is refused by the `variant_prompt` check until the human writes it.
2. **MLflow is recorded once per run, after the bundle is finalized**, not per trial: `experiment.run_variant` calls `record_run` after `BundleWriter.finish` and `verify_schedule`. Per trial the order is: the trial record is written to the bundle, then the next trial.
3. **`compare`, human review, and the work-log rebuild are separate commands outside `run`.** `compare` calls `summary.summarize_bundle` and `experiment.verify_schedule` on two finished bundles and reads bundles only, never MLflow.

## Lanes and the logical diagram

| Lane | Logical-diagram boxes | Header status |
|---|---|---|
| human (manual steps) | reviewed result summaries | PENDING |
| host CLI (trusted process) | `experiment.py + experiment_cli.py`, `run_recording.py`, `trial.py`, `run_checks.py`, `evaluate.py + contract.py`, `sandbox.py + limits.py`, `comparison.py`, `summary.py` | PARTIAL: NO LIVE RUN YET (the weakest status of its boxes) |
| OpenRouter (EXTERNAL) | `OpenRouter (external model API)`, reached through `openrouter_client.py` | EXTERNAL, PHASE 2, PENDING |
| sandbox container (TRUST BOUNDARY) | `worker.py` | IMPLEMENTED |
| on disk and MLflow | `run_recording.py + bundle.py` (bundles, run marker), `ledger.py` (the file), `mlflow_tracking.py`, `MLflow tracking store` | PARTIAL: NO LIVE RUN YET |

The container lane is the only trust-boundary region. Only candidate source plus one check's or one case's arguments flow in, and only one bounded report flows out, always to and from the host launcher `sandbox.py`. Expected answers, scoring, the key, and the ledger stay on the host side. No arrow joins the container lane to OpenRouter, the ledger, the bundle, or MLflow.

## Lifecycle nodes (top part of the diagram)

- (human; start node) START: experiment begins — code: `initial node of the lifecycle`
- (host CLI; action) Freeze the benchmark; scripts/freeze_benchmark.py --check — code: `scripts/freeze_benchmark.py (tasks.check_freeze)`
- (host CLI; action) build-config (--check); experiment.build_config, config_drift — code: `experiment.build_config, experiment.config_drift`
- (host CLI; action) record-probes (Podman probe suite); experiment_cli.run_probe_suite — code: `experiment_cli.run_probe_suite, experiment.write_probes_evidence`
- (host CLI; action) smoke trial (PAID, PHASE 2); openrouter_cli smoke --i-accept-cost; retained smoke bundle — code: `openrouter_cli.run_smoke`
- (OpenRouter (EXTERNAL); action) OpenRouter API (EXTERNAL, PHASE 2); no live call has been made — code: https://openrouter.ai/api/v1/chat/completions (openrouter_config)
- (host CLI; action) calibrate --smoke-bundle B; experiment.calibrate — code: `experiment.calibrate`
- (host CLI; action) freeze-settings --smoke-bundle B; experiment.write_settings_freeze — code: `experiment.write_settings_freeze`
- (host CLI; action) mlflow_service.sh start; (optional; an outage never blocks a run) — code: `scripts/mlflow_service.sh`
- (host CLI; action) check --variant baseline; experiment.check_preconditions — code: `experiment_cli.main check -> experiment.check_preconditions`
- (host CLI; decision) unmet; preconditions? — code: `check: failures printed`
- (human; final node) FINAL: check reports unmet preconditions; exit 1, nothing spent — code: `experiment_cli.main: return 1 if failures`
- (host CLI; call-behaviour action) run --variant baseline; [sub-activity: see frame below] — code: `experiment_cli.main run -> experiment.run_variant`
- (human; action) Inspect the baseline failures (read-only); trace_inspect list | verify | show,; replay, mlflow_tracking status — code: `trace_inspect.main, replay.main, mlflow_tracking.main status`
- (human; action) Write the revised prompt file; prompts/<version>.md (human) — code: `agent_config.load_prompt`
- (host CLI; action) build-config --revised-prompt; probe evidence and settings freeze stay valid — code: `experiment.build_config; evaluator_code_sha256 and settings_hash exclude prompt files`
- (host CLI; action) check --variant revised; experiment.check_preconditions — code: `experiment.check_preconditions`
- (host CLI; decision) unmet; preconditions? — code: `check: failures printed`
- (host CLI; call-behaviour action) run --variant revised; [sub-activity: see frame below] — code: `experiment_cli.main run -> experiment.run_variant`
- (on disk and MLflow; data store) run bundles (run_bundles/); baseline and revised — code: `bundle.DEFAULT_BUNDLE_ROOT`
- (host CLI; action) compare --baseline RUN_A --revised RUN_B; comparison.compare_runs — code: `comparison.compare_runs -> summary.summarize_bundle, experiment.verify_schedule`
- (host CLI; decision) headline; comparison? — code: `result['headline_comparison']`
- (human; final node) FINAL: compare is not a headline comparison; exit 1, figures still printed — code: `experiment_cli.main compare: return 0 if headline else 1`
- (human; action) Human review of the comparison; reviewed result summary (PENDING) — code: `reviewed result summaries (logical diagram, PENDING)`
- (host CLI; action) scripts/build_work_log.py (--check); rebuild the offline work log — code: `scripts/build_work_log.py`
- (host CLI; final node) FINAL: experiment complete — code: `end of the lifecycle`

### Lifecycle flows

- START: experiment begins → Freeze the benchmark
- Freeze the benchmark → build-config (--check)
- build-config (--check) → record-probes (Podman probe suite)
- record-probes (Podman probe suite) → smoke trial (PAID, PHASE 2)
- smoke trial (PAID, PHASE 2) → OpenRouter API (EXTERNAL, PHASE 2) [paid call]
- smoke trial (PAID, PHASE 2) → calibrate --smoke-bundle B
- calibrate --smoke-bundle B → freeze-settings --smoke-bundle B
- freeze-settings --smoke-bundle B → mlflow_service.sh start [optional]
- mlflow_service.sh start → check --variant baseline
- check --variant baseline → unmet
- unmet → FINAL: check reports unmet preconditions [yes]
- unmet → run --variant baseline [no]
- run --variant baseline → Inspect the baseline failures (read-only) [run completed]
- Inspect the baseline failures (read-only) → Write the revised prompt file
- Write the revised prompt file → build-config --revised-prompt
- build-config --revised-prompt → check --variant revised
- check --variant revised → unmet
- unmet → FINAL: check reports unmet preconditions [yes]
- unmet → run --variant revised [no]
- run --variant revised → compare --baseline RUN_A --revised RUN_B [run completed]
- run bundles (run_bundles/) → compare --baseline RUN_A --revised RUN_B [reads bundles only]
- compare --baseline RUN_A --revised RUN_B → headline
- headline → FINAL: compare is not a headline comparison [no]
- headline → Human review of the comparison [yes]
- Human review of the comparison → scripts/build_work_log.py (--check)
- scripts/build_work_log.py (--check) → FINAL: experiment complete

## The run sub-activity

The dashed frame `activity: run --variant V (one invocation; entered from both run actions above)` is entered from both `run` actions. Its normal outcome is the exit edge `EXIT: run completed`, which returns to the lifecycle; it is not a final node. The dashed regions are `loop: for each planned trial (30 trials, task_major order)` and, inside it, `loop: agent loop, at most 4 model calls (AgentLimits)`.

- (host CLI; action) experiment_cli run; --variant V --pricing P --i-accept-cost — code: `experiment_cli.main (run)`
- (host CLI; action) load config, prices, model config;; build the MLflow recorder (unless --no-tracking) — code: `load_config, PriceInputs.from_file, load_model_config, mlflow_tracking.bundle_recorder`
- (host CLI; decision) inputs; usable? — code: `experiment_cli.main: return 1 (config) or REFUSED`
- (host CLI; action) check_preconditions() inside run_variant; all failures reported together:; - cost acceptance, API key, variant prompt; - config_drift, host platform and pinned image; - benchmark freeze (check_freeze); - probe evidence (probes_problems); - settings freeze, smoke bundle, calibrate; - budget projection against the CHF 15 ceiling; - no earlier run of this variant — code: `experiment.check_preconditions`
- (host CLI; decision) any precondition; unmet? — code: `PreconditionsFailed`
- (human; final node) FINAL: refused; exit 2 (exit 1 if the config is unreadable); nothing written, nothing spent — code: `experiment_cli.main: REFUSED = 2; PreconditionsFailed`
- (host CLI; action) write run marker: started; experiment.run_variant atomic_write — code: `experiment.run_variant: atomic_write(marker)`
- (on disk and MLflow; data store) run marker; <run_id>.experiment.json — code: `experiment._sidecar_path`
- (host CLI; action) run_recorded(): plan 10 tasks x 3 trials; BundleWriter: manifest in_progress — code: `run_recording.run_recorded, bundle.BundleWriter`
- (on disk and MLflow; data store) run bundle; manifest.json: in_progress — code: `bundle.BundleWriter._save_manifest`
- (host CLI; action) client_for(): OpenRouterClient per trial,; RecordingClient(sink = append_call) — code: `experiment_cli.client_for, run_recording.RecordingClient`
- (host CLI; action) build request (trial.run_trial); tools offered (tool_choice auto) only while; model calls < 4 and tool attempts < 3,; else tool_choice none — code: `trial.run_trial`
- (host CLI; action) log the request; RecordingClient.complete -> append_call — code: `run_recording.RecordingClient.complete, bundle.BundleWriter.append_call`
- (on disk and MLflow; data store) call log: request; fsync, before the send — code: `bundle.BundleWriter.append_call`
- (host CLI; decision) bound within the; input limit? — code: `openrouter_client.input_token_bound`
- (host CLI; action) request_rejected; no_submission (no reserve, no send) — code: `ModelFailure(request_rejected) -> trial.run_trial`
- (host CLI; action) ledger.reserve(); before every send, retries included — code: `openrouter_client.OpenRouterClient._attempt -> ledger.Ledger.reserve`
- (on disk and MLflow; data store) ledger: spend_ledger.jsonl; reservation (fsync, exclusive lock) — code: `ledger.Ledger.reserve`
- (host CLI; decision) total + amount >; CHF 15 ceiling? — code: `ledger.BudgetCeiling`
- (host CLI; action) budget_ceiling; infrastructure_incomplete — code: `ModelFailure(budget_ceiling) -> trial.run_trial`
- (on disk and MLflow; action) CHF 10 checkpoint: logged once,; the run continues — code: `ledger.Ledger._log_checkpoint (reserve, settle, adjust)`
- (OpenRouter (EXTERNAL); action) OpenRouter API (EXTERNAL, PHASE 2); POST chat completions, one reply — code: `transport.post(config.endpoint, ...)`
- (host CLI; action) settle or keep; ledger.settle / ledger.keep — code: `openrouter_client.OpenRouterClient._interpret, _settle`
- (on disk and MLflow; data store) ledger: settlement or kept; committed charge or counted reservation — code: `ledger.Ledger.settle, ledger.Ledger.keep`
- (host CLI; decision) reply usable? — code: `openrouter_client.OpenRouterClient.complete / _interpret`
- (host CLI; action) ModelFailure (transport_exhausted,; api_error, malformed_response); infrastructure_incomplete — code: `TRANSPORT_EXHAUSTED, API_ERROR, MALFORMED_RESPONSE`
- (host CLI; action) log the response; RecordingClient.complete -> append_call — code: `run_recording.RecordingClient.complete`
- (on disk and MLflow; data store) call log: response; fsync — code: `bundle.BundleWriter.append_call`
- (host CLI; decision) response outcome?; (trial.run_trial) — code: `trial.run_trial`
- (host CLI; action) tool call while tools disabled; no_submission (tool_request_when_disabled) — code: `tool_request_when_disabled`
- (host CLI; action) no content; no_submission (no_final_message) — code: `no_final_message`
- (host CLI; action) final content: contract.validate_source; submitted (issue recorded, never repaired) — code: `contract.validate_source, trial.run_trial`
- (host CLI; action) run_checks.run_checks() (tool call, tools on); parse_request (at most 4 checks), validate_source,; then sandbox.execute_check per check — code: `run_checks.run_checks, run_checks.parse_request, sandbox.execute_check`
- (sandbox container (TRUST BOUNDARY); action) worker.py: fresh container per check; source + one check's arguments in,; bounded result out — code: `worker.SUPERVISOR via sandbox.execute_check`
- (host CLI; action) compare actual with the agent's expected; value on the host (_check_feedback) — code: `run_checks._check_feedback`
- (host CLI; decision) infrastructure; status? — code: `run_checks.ToolResult.infrastructure`
- (host CLI; action) infrastructure_incomplete; (no feedback sent) — code: `trial._handle_tool_calls`
- (host CLI; action) trial ends: TrialResult; submitted | no_submission | infrastructure_incomplete — code: `trial.TrialResult`
- (host CLI; decision) submitted without; contract issue? — code: `evaluate.grade_trial`
- (host CLI; action) no container is run; all four checks unexecuted — code: `evaluate.grade_trial`
- (host CLI; action) grade_trial -> run_case per executed case; (up to 4; payload_too_large starts no container) — code: `evaluate.grade_trial, sandbox.run_case, sandbox.execute_check`
- (sandbox container (TRUST BOUNDARY); action) worker.py: fresh container per case; source + one case's arguments + token in,; one bounded report out — code: `sandbox.execute_check, worker.SUPERVISOR`
- (host CLI; action) score_case: compare with the hidden; expected answer (host only) — code: `evaluate.score_case`
- (host CLI; action) grades_record -> write_trial; BundleWriter.write_trial (atomic) — code: `bundle.grades_record, bundle.BundleWriter.write_trial`
- (on disk and MLflow; data store) run bundle: trial record; manifest hash; call log deleted — code: `bundle.BundleWriter.write_trial`
- (host CLI; decision) infrastructure_status ==; budget_ceiling? — code: `run_recording.run_recorded: break`
- (host CLI; decision) more planned; trials? — code: `run_recording.run_recorded: for item in planned`
- (host CLI; action) BundleWriter.finish(); verify_bundle; manifest complete | incomplete — code: `bundle.BundleWriter.finish, bundle.verify_bundle`
- (on disk and MLflow; data store) run bundle: manifest status; complete | incomplete — code: `bundle.STATUS_COMPLETE, STATUS_INCOMPLETE`
- (host CLI; action) BaseException in the loop (Ctrl-C, LedgerError,; BundleError, ...): finish(['interrupted: type']);; marker interrupted; exception re-raised — code: `run_recording.run_recorded, experiment.run_variant`
- (host CLI; final node) FINAL: aborted; exception leaves main, traceback; marker interrupted (or started) — code: `experiment.run_variant; three variants in the twin`
- (host CLI; action) verify_schedule(); bundle against the configured schedule — code: `experiment.verify_schedule`
- (host CLI; action) record_run(bundle, variant); mlflow_tracking.bundle_recorder (once per run) — code: `mlflow_tracking.bundle_recorder, record_bundle`
- (host CLI; decision) MLflow reachable and; bundle recordable? — code: `mlflow_tracking.record_bundle: TrackingUnavailable, ImportError, BundleError`
- (on disk and MLflow; data store) MLflow tracking store; record_bundle uploads (idempotent); tracking.json: recorded — code: `mlflow_tracking.record_bundle, write_sidecar`
- (host CLI; action) tracking.json: not_recorded; outage marker; run outcome unchanged — code: `mlflow_tracking.bundle_recorder`
- (host CLI; action) marker finalised: complete | incomplete; experiment.run_variant atomic_write — code: `experiment.run_variant`
- (host CLI; decision) verification.complete; and schedule ok? — code: `VariantRun.complete`
- (host CLI; exit of the sub-activity) EXIT: run completed, back to the lifecycle; exit 0, manifest complete, marker complete — code: `experiment_cli.main: return 0`
- (host CLI; decision) stopped at; budget_ceiling? — code: `bundle manifest reason budget_ceiling`
- (host CLI; final node) FINAL: budget ceiling; exit 1, manifest incomplete (budget_ceiling); marker incomplete — code: `run_recording.run_recorded stopped list`
- (host CLI; final node) FINAL: incomplete after infrastructure; outcomes or schedule problems; exit 1, manifest incomplete, marker incomplete — code: `bundle.INFRASTRUCTURE_STOP, experiment.verify_schedule`

### Run flows

- experiment_cli run → load config, prices, model config;
- load config, prices, model config; → inputs
- inputs → check_preconditions() inside run_variant [yes]
- inputs → FINAL: refused [no]
- check_preconditions() inside run_variant → any precondition
- any precondition → FINAL: refused [yes]
- any precondition → write run marker: started [no]
- write run marker: started → run_recorded(): plan 10 tasks x 3 trials
- write run marker: started → run marker [writes]
- run_recorded(): plan 10 tasks x 3 trials → run bundle [writes]
- run_recorded(): plan 10 tasks x 3 trials → client_for(): OpenRouterClient per trial,
- client_for(): OpenRouterClient per trial, → build request (trial.run_trial)
- build request (trial.run_trial) → log the request
- log the request → call log: request [writes]
- log the request → bound within the
- bound within the → request_rejected [no]
- bound within the → ledger.reserve() [yes]
- ledger.reserve() → ledger: spend_ledger.jsonl [reserve]
- ledger.reserve() → total + amount >
- total + amount > → budget_ceiling [yes (refusal)]
- ledger: spend_ledger.jsonl → CHF 10 checkpoint: logged once,
- total + amount > → OpenRouter API (EXTERNAL, PHASE 2) [no: send]
- OpenRouter API (EXTERNAL, PHASE 2) → settle or keep [reply]
- settle or keep → ledger: settlement or kept [settle / keep]
- settle or keep → reply usable?
- reply usable? → ledger.reserve() [retry]
- reply usable? → ModelFailure (transport_exhausted, [other failure]
- reply usable? → log the response [usable reply]
- log the response → call log: response [writes]
- log the response → response outcome?
- response outcome? → tool call while tools disabled
- response outcome? → no content
- response outcome? → final content: contract.validate_source
- response outcome? → run_checks.run_checks() (tool call, tools on) [tool call, tools enabled]
- run_checks.run_checks() (tool call, tools on) → worker.py: fresh container per check [source + one check's args]
- worker.py: fresh container per check → compare actual with the agent's expected [bounded result]
- compare actual with the agent's expected → infrastructure
- infrastructure → infrastructure_incomplete [yes]
- infrastructure → build request (trial.run_trial) [no: feedback, next call]
- final content: contract.validate_source → trial ends: TrialResult
- request_rejected → trial ends: TrialResult
- budget_ceiling → trial ends: TrialResult
- ModelFailure (transport_exhausted, → trial ends: TrialResult
- tool call while tools disabled → trial ends: TrialResult
- no content → trial ends: TrialResult
- infrastructure_incomplete → trial ends: TrialResult
- trial ends: TrialResult → submitted without
- submitted without → no container is run [no]
- submitted without → grade_trial -> run_case per executed case [yes]
- grade_trial -> run_case per executed case → worker.py: fresh container per case [source + one case's args]
- worker.py: fresh container per case → score_case: compare with the hidden [bounded report]
- score_case: compare with the hidden → grades_record -> write_trial
- no container is run → grades_record -> write_trial
- grades_record -> write_trial → run bundle: trial record [writes]
- grades_record -> write_trial → infrastructure_status ==
- more planned → client_for(): OpenRouterClient per trial, [yes: next trial]
- infrastructure_status == → more planned [no]
- more planned → BundleWriter.finish() [no: loop ends]
- infrastructure_status == → BundleWriter.finish() [yes: stop, later trials not run]
- loop: for each planned trial (30 trials, task_major order) → BaseException in the loop (Ctrl-C, LedgerError, [any exception]
- BaseException in the loop (Ctrl-C, LedgerError, → FINAL: aborted
- BundleWriter.finish() → run bundle: manifest status [writes]
- BundleWriter.finish() → verify_schedule()
- verify_schedule() → record_run(bundle, variant)
- record_run(bundle, variant) → MLflow reachable and
- MLflow reachable and → MLflow tracking store [yes]
- MLflow reachable and → tracking.json: not_recorded [no]
- tracking.json: not_recorded → marker finalised: complete | incomplete
- MLflow tracking store → marker finalised: complete | incomplete
- marker finalised: complete | incomplete → verification.complete
- verification.complete → EXIT: run completed, back to the lifecycle [yes]
- verification.complete → stopped at [no]
- stopped at → FINAL: budget ceiling [yes]
- stopped at → FINAL: incomplete after infrastructure [no]

The ceiling decision `total + amount > CHF 15 ceiling?` is the test in `ledger.Ledger.reserve` (`state.total + amount > ceiling`, total being committed plus outstanding reservations). The CHF 10 checkpoint is logged once by `ledger.Ledger._log_checkpoint`, called from `reserve`, `settle`, and `adjust`; it only records, the run continues, and the final printout reports `checkpoint_reached`. A retry after a transient failure (timeout, connection error, HTTP 408/429/5xx) reserves again before it sends (`openrouter_client.OpenRouterClient._attempt`). When tools are not offered (`tool_choice` none) the client still sends the tool definitions so the history's tool calls stay valid.

## Endings

Final nodes (UML final nodes, seven in all). A completed run is the exit edge, not a final node.

**In the run sub-activity**

1. **FINAL: refused.** Three code paths, all before anything is written: `experiment_cli.main` returns **1** with `error: ...` when `load_config` raises (`ExperimentError`, `BundleError`, `ValueError`, `OSError`); it returns `REFUSED` (**2**) with `refusing to run: ...` for an unreadable pricing file, an unusable model config, or a missing MLflow client; and `PreconditionsFailed` from `experiment.run_variant` returns `REFUSED` (**2**) after printing every failed check. Argparse exits 2 on bad arguments. No run marker, bundle, client, or ledger event exists afterwards (the ledger file may be created empty when it is opened).
2. **FINAL: budget ceiling.** A trial's model call returns `ModelFailure(budget_ceiling)`: that trial is graded and written as `infrastructure_incomplete`, `run_recorded` stops the loop, and later trials are not run. Exit **1**; bundle manifest `incomplete` with the reason `budget_ceiling: stopped before <trial> finished; later trials were not run`; run marker `incomplete`. The MLflow recording is still attempted and succeeds for such a bundle (`run_not_finalized` and `missing_record` are not blocking), so `tracking.json` says `recorded`, or `not_recorded` on an outage.
3. **FINAL: incomplete after infrastructure outcomes or schedule problems.** Any other trial that ended `infrastructure_incomplete` (`transport_exhausted`, `api_error`, `malformed_response`, or a hidden check that returned `infrastructure_error` or `protocol_error`), or a schedule problem found by `verify_schedule`: the loop continued, `verify_bundle` reports `infrastructure_stop` or the schedule problem, so `verification.complete and schedule.ok` is false. Exit **1**; manifest `incomplete`; run marker `incomplete` with the `schedule_problems` listed; MLflow recording attempted as above.
4. **FINAL: aborted.** Any `BaseException`; the exception leaves `main` with a traceback because only `PreconditionsFailed` is caught around `run_variant`. Three observable variants. (a) Raised inside `run_recorded` after the writer exists (Ctrl-C, `LedgerError`, `BundleError`, `FixtureExhausted`, an unexpected exception): `finish(["interrupted: <type>"])` stores manifest `incomplete`, and the run marker is rewritten `interrupted`. (b) Raised after the marker but before the writer exists (`load_prompt`, `load_benchmark`, `build_identity`, or `BundleWriter` raising `bundle already exists`): the marker is `interrupted` and there is no bundle, or one still `in_progress`. (c) Raised after `run_recorded` returned (`verify_schedule` raising `BundleError`, `ledger.state()` raising `LedgerError`, the final marker write): the manifest is already finalised and the marker stays `started`.

**Completed (exit edge `EXIT: run completed`).** `verification.complete and schedule.ok`: exit **0**, manifest `complete`, marker `complete`; the printout states the bundle, the ledger totals before and after, the checkpoint flags, and the tracking outcome (`recorded`, or `not recorded` with the later-upload command, or `tracking failed`).

**In the lifecycle**

5. **FINAL: check reports unmet preconditions.** `experiment_cli check` prints `unmet: <check>: <detail>` for every failed precondition and `N unmet precondition(s)`, exit **1**; nothing is spent and nothing is written.
6. **FINAL: compare is not a headline comparison.** `compare` prints the figures labelled `NOT a headline comparison` with the reasons (an incomplete, ungraded, or non-matching run), exit **1**.
7. **FINAL: experiment complete.** After the work-log rebuild; the end of the lifecycle.

**Not endings.** The CHF 10 checkpoint (logged, the run continues). An MLflow outage (`tracking.json` `not_recorded`, run status unchanged). A wrong answer, a `no_submission`, or a `request_rejected` trial is a normal graded trial.

## Source of each claim

Every node above names its function or command. The order claims (request logged before the send; the ledger reservation before the POST; the run marker written before `run_recorded`; bundle finalised, schedule verified, then the MLflow recording; the trial record written after grading) are asserted against the source by `tests/test_run_flow_diagrams.py`.

Maintenance: edit the diagram in draw.io (File > Properties: Compressed off), save it as `.drawio.svg`, then edit this page in the same change; `tests/test_run_flow_diagrams.py` checks that the labels, names, endings, and claims agree with each other and with the source tree.
