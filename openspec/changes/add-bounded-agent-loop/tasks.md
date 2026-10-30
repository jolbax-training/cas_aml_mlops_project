# Tasks

Planned for day 1 (agent/fixtures, 3h), after `harden-candidate-execution` provides per-check execution. All tasks are unstarted.

## 1. Interfaces and configuration

- [ ] 1.1 Define the model-client interface and normalised response/failure types, plus a recorded-response fixture client; unit-test fixture replay.
- [ ] 1.2 Add interaction-limit configuration (4 logical calls, 3 tool attempts, 4 checks per request) with a recordable hash, and a versioned baseline agent prompt file.

## 2. Tool and controller

- [x] 2.0 (Resolved 2026-10-30: user accepted the proposed defaults; submission is a plain final message) Obtain the user's decisions on the three open decisions in design.md (input-limit rejection outcome, submission signalling, multi-part responses) and record them in docs/progress.md before writing the affected fixtures.

- [ ] 2.1 Implement `run_checks` request validation, per-check execution through the candidate-execution mechanism, trusted strict comparison against agent-authored expectations by reusing the pilot's existing comparison and mutation detection, and bounded feedback; test that hidden data never appears.
- [ ] 2.2 Implement the trial controller: fresh conversation, limit enforcement, fourth call with tools disabled, explicit final submission, `no_submission`, recovery feedback consuming attempts, and infrastructure-incomplete classification.
- [ ] 2.3 Wire final submission to the existing source contract validator without repair; record contract failures.

## 3. Verification and documentation

- [ ] 3.1 Add fixture tests for early submission without tools, tool use and revision, malformed arguments and recovery, oversized batch, fourth-call submission, tool request on call 4, no submission, pre-send input-limit rejection, multiple tool calls in one response, fenced/invalid final source, candidate exception feedback, and container unavailability.
- [ ] 3.2 Propose the infrastructure-incomplete-trial glossary entry from design.md to the user. Run the offline suite and record exact commands and observed results in docs/progress.md; document the trial contract and fixture command in README, stating fixtures do not measure live model quality.
