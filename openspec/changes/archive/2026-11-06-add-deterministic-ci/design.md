# Design

## Context

See proposal.md. A GitHub origin exists but no Actions workflow. Offline tests run with pytest under uv; Podman integration tests currently skip when Podman or the pinned image is unavailable. The workflow passed on GitHub (run 41128433037) and the failure demonstrations behaved as specified; only branch protection (a repository setting) is pending.

## Goals / Non-Goals

**Goals:** Two required deterministic check groups, real Podman execution in CI, pinned/documented environment, no secrets, retained evidence.

**Non-Goals:** Live model calls, paid generation, candidate pass-rate gates, release/deployment automation, matrix testing across many platforms, or MLflow service tests requiring persistent storage.

## Decisions

### 1. Two check groups in one workflow

Group A runs evaluator, benchmark validation, contract, accounting, and recorded-response agent-loop tests with no container dependency. Group B runs real Podman execution/isolation/limit and scoring-integrity probes against the pinned candidate image. Both are required checks; exact job and workflow names are implementation choices to document.

### 2. Compatible Linux runner with real Podman

Use a GitHub-hosted Linux runner verified to support rootless Podman with the required restrictions, or document the provisioning step if needed. The exact runner image and Podman version are bounded choices to verify and record; limits that cannot be enforced on the runner make Group B fail rather than silently skip. In CI, Podman-dependent tests MUST NOT be skipped when Podman is expected; a skip is treated as failure.

### 3. Pinned and documented environment

Install dependencies from the uv lockfile, pin the Python version and the candidate image by digest, and record tested versions in documentation and progress.

### 4. No credentials or paid generation

The workflow defines no model secrets and network access is not used for model calls. Tests use recorded-response fixtures and known candidates. Candidate success rates are experiment evidence, never CI gates.

## Risks / Trade-offs

- Runner Podman differs from the laptop → verify limits on each environment used and document differences as residual limitations.
- Flaky timing near the 10-second deadline → use clearly bounded timeout fixtures well beyond the deadline and fast-passing fixtures well within it.
- Silent skips hiding missing Podman → explicit environment flag that turns skips into failures in CI.

## Migration Plan

Add the workflow, run it on a branch, fix environment issues, and record successful run identifiers. Rollback removes the workflow file without affecting local tests.
