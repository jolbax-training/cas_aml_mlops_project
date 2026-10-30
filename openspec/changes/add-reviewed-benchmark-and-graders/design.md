# Design

## Context

See proposal.md. The pilot (`data/pilot_tasks.json`, `src/codegen_eval/tasks.py`, `evaluate.py`) already validates task data and source, runs each case in a restricted Podman container, and compares outside it. This change grows the dataset to the agreed ten tasks, adds review evidence, and makes grading and accounting match Q21–Q24. Nothing here is implemented yet.

## Goals / Non-Goals

**Goals:** A reviewed, frozen, versioned ten-task benchmark; deterministic grading with failure labels; fixed denominators; fixture-validated evaluator behavior.

**Non-Goals:** Running models, deciding trial counts or variants (owned by `run-prompt-comparison`), container hardening (owned by `harden-candidate-execution`), LLM judging, tolerance-based or exception-based tasks.

## Decisions

### 1. Benchmark content and review records

Keep a single versioned benchmark file (exact path is an implementation choice, for example `data/benchmark_v1.json`) with task ID, category, instruction, function name, typed signature, and four cases each tagged `ordinary` or `edge`. Validation enforces ten unique task IDs, exactly two tasks per category, four cases per task with two of each kind, unique case IDs, and argument shapes matching the signature.

Each task has a reference solution written and reasoned separately from the expected answers, plus a review record (Markdown or structured file) capturing reviewer, date, derivation, corrections, and IDs. Reference solutions run against the cases as a consistency check; an additional unreviewed model answer does not count as independent validation. Pilot tasks are re-reviewed before reuse.

Freezing records a content hash over benchmark and review files. Any later edit creates a new version and requires comparable reruns.

### 2. Comparison semantics

Comparison is recursive and strict-typed over strings, integers, booleans, lists, string-keyed dictionaries, and null where a task needs it: `True` ≠ `1`, list order matters, dictionary key order does not. The pilot already implements strict comparison (`_strict_equal`) and mutated-input detection in `src/codegen_eval/evaluate.py`; `add-bounded-agent-loop` reuses them on day 1 and this change verifies and extends them against Q23 rather than reimplementing them. Mutation is detected by comparing post-call arguments with a trusted copy; expected answers and comparison remain in trusted orchestration (consistent with `harden-candidate-execution`).

### 3. Outcome labels and accounting

Per-check records carry `executed`, `passed`, and zero or more labels (for example `wrong_answer`, `mutation`, `exception`, `timeout`, `excessive_output`). Trial-level labels add `contract_error`, `syntax_error`, and `no_submission`; the latter two mark all four checks unexecuted and unsuccessful. Exact label names are an implementation choice; their meanings are fixed here.

Infrastructure outcomes (`container_unavailable`, `worker_protocol_error`, exhausted transport retries reported by the model client) are not candidate failures; they mark the run incomplete. Summaries always use planned denominators and report counts with rates. The record-level completeness check (every scheduled task/trial ID has a record, every executed check has a valid outcome) is owned by `add-run-bundles-and-grading-replay` (`run-evidence`); this change consumes its result and owns only the classification and headline-exclusion rules.

### 4. Evaluator fixtures

Deterministic candidate fixtures (no model): correct, ordinary-case wrong, edge-case wrong, syntax error, signature/other contract violations, exception, mutation, timeout, excessive output, and an infrastructure-failure double. Expected accounting for each is asserted. Fixtures validate the evaluator, not model quality.

## Open decisions for the user

1. **RESOLVED 2026-10-30 (user accepted the proposed default) — payload-too-large hidden check.** If a final submission's source plus a hidden check's arguments exceed the 64 KiB payload limit, `harden-candidate-execution` starts no container. Q24 does not list this outcome. Proposed default: a candidate failure labelled `payload_too_large`, with that check unsuccessful and unexecuted within the planned denominator (the source is agent-authored and benchmark arguments are small). Alternative: treat it as a contract failure for all four checks.
2. The pre-send input-limit rejection (`request_rejected`) was resolved on 2026-10-30 (accepted default) in `add-bounded-agent-loop/design.md`; it is a trial-level label with `no_submission` accounting.

## Risks / Trade-offs

- Review time within 3h → reuse reviewed pilot tasks where sound; keep tasks small; defer extra tasks (out of scope).
- Ambiguous instructions → reviewer corrects the instruction and records the correction before freezing.
- Reviewer and author are the same person → separate reference reasoning from expected answers and record the derivation; document this limitation.
- Late benchmark edits → versioning plus rerun requirement prevents silent comparison drift.

## Migration Plan

Add the benchmark file and validation, write and review tasks/references, implement comparison/labels/accounting with fixtures, then freeze and record the hash in progress. Keep the pilot file for history. Rollback restores pilot-only evaluation; no paid calls are involved.
