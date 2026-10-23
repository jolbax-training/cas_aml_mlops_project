# Define Podman services and reproducible evidence

Label: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: 01, 02, 03, 04

## Question

How will the agent, disposable code containers, and containerized local MLflow run under Podman? Decide orchestration placement, service connectivity, durable local bundles and trace layout, replay semantics, MLflow recording/recovery, deterministic CI scope and runner, and the minimum HTML work-log with its update/build workflow. Define which parts of the existing report proposal to retain or simplify and the evidence needed to verify each component.

## Comments

### Q34 — User-confirmed runtime topology

Run MLflow as a persistent local Podman service with persistent local storage and a localhost tracking endpoint. Run the trusted Python CLI on the laptop in its `uv` environment; it controls disposable candidate containers. Candidate containers remain separate and receive neither tracking credentials nor container-control access. The trusted CLI does not itself need containerization for this scope.

### Q35 — User-confirmed evidence and replay

Persist a durable local run bundle containing requests, responses, tool interactions, final source, configuration/version hashes, usage, and grading results before recording in MLflow. A tracking outage must preserve evidence and permit later upload without regeneration.

Provide three distinct offline capabilities:

- Inspect retained traces/results without model API access or Podman.
- Replay grading by executing saved final candidates against the retained benchmark with Podman and no new model calls.
- Verify the interaction loop with deterministic recorded-response fixtures, covering tool handling and stopping behavior without an API.

Regrading saved code does not reproduce a fresh model interaction. CI requirements and the HTML work-log scope remain to be confirmed before this ticket closes.

### Q36 — User-confirmed deterministic CI

Require two deterministic GitHub Actions check groups: evaluator/benchmark/agent-loop tests and Podman execution/isolation tests. Use a compatible Linux runner with documented, pinned dependencies and images. Require no model credentials or paid generation. Verify failure classification, limits, and scoring with fixtures; do not introduce candidate pass-rate gates.

### Q37 — User-confirmed minimum HTML work-log

Generate local `report/index.html` from explicitly selected Markdown and reviewed result summaries. The opening architecture diagram distinguishes implemented and planned components. Include scope/status/milestones/dated decisions; benchmark review, results/comparison/limitations; local evidence references and MLflow IDs/links; setup/replay/demo instructions; and selected student-authored learning notes. Use local assets, escaped code, validated internal links, and honest pending labels. The output opens without a server/network. Provide one documented build command, rebuild after meaningful milestones/runs, and keep execution independent of reporting. Revise the existing report proposal to this smaller agreed scope.

## Answer

User-confirmed through Q34–Q37:

- Run the trusted CLI on the laptop in its `uv` environment. It orchestrates disposable candidate containers. Run MLflow as a persistent Podman service with durable local storage and a localhost tracking endpoint. Candidate containers receive neither tracking credentials nor container-control access.
- Persist the complete local run bundle before MLflow recording: requests/responses, tool interactions, final source, configuration/version hashes, usage, and grading results. Upload retained evidence later if tracking is unavailable; never regenerate paid responses to recover tracking. Keep bundles and generated/tracking output excluded from version control.
- Support trace inspection with no execution/services, saved-final-candidate grading replay with Podman and no API, and deterministic recorded-response fixtures for interaction-loop verification. Do not describe grading replay as fresh model interaction or agent-trial reproduction.
- Capture trial/model/tool traces alongside experiment parameters, metrics, and artifacts in the already agreed local MLflow integration. Link recording and replay evidence to retained run identity; keep the original agent trace distinct from later grading evidence.
- Require deterministic evaluator/benchmark/agent-loop and real Podman isolation/execution checks in GitHub Actions on a compatible Linux runner. Pin/document tested dependency and image versions. CI uses fixtures without model credentials or paid generation; model success-rate thresholds are not gates.
- Build the local-only HTML work-log from selected authoritative Markdown and reviewed summaries, with architecture first, implemented/planned status, dated progress/decisions, benchmark review, results/comparison/limitations, local evidence/MLflow references, reproduction/demo instructions, and selected student-written learning notes. Use local assets, inert code, validated links, and pending labels; no hosting or network/server requirement for viewing.
- Provide one report-build command and update after meaningful milestones/runs. Reporting and tracking do not become prerequisites for running the local agent/evaluator. Reconcile the existing report proposal rather than implementing its full previous scope without review.
- Exact supported Linux image/Podman provisioning, local storage layout, dependency/image versions, and command names are bounded implementation choices to document and verify. Successful checks and an actually opened offline report remain implementation exit evidence, not results of this planning decision.
