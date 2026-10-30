# Design

## Context

See proposal.md. The pilot (`src/codegen_eval/sandbox.py`) already starts a restricted Podman container per case, sends a JSON payload to an embedded worker script, and scores outside the container. Its default deadline is eight seconds and the worker shares a Python process with candidate code, so candidate code could in principle write a forged protocol message or mutate inputs after the worker's snapshot. This design describes target behavior; none of it is implemented.

## Goals / Non-Goals

**Goals:** One execution mechanism for development and acceptance checks; a fresh container per check; only source/function name/arguments inside; agreed configurable limits; trustworthy raw outcomes; mandatory probes and a documented threat model.

**Non-Goals:** Production security certification, defending against Podman/kernel escapes, network or filesystem tools for the agent, scoring inside the container, or performance optimisation beyond the 10-second deadline.

## Decisions

### 1. Single per-check execution entry point

Expose one trusted function that executes a single check: inputs are candidate source, function name, the check's arguments, and the frozen limit configuration; output is a raw execution outcome (returned value, post-call argument state or mutation evidence, captured print output within limits, bounded diagnostics, and a classification such as completed, candidate exception, timeout, output limit, payload too large, or infrastructure failure). Expected values are never parameters of this function. Development feedback and acceptance scoring both compare its output in trusted code. Exact names and data types are implementation choices.

### 2. Limit configuration

Hold limits in one configuration object with the agreed defaults:

| Limit | Default |
| --- | ---: |
| Wall-time deadline per check (startup/loading included, cleanup excluded) | 10 s |
| Memory | 128 MiB |
| CPU | 1 |
| Processes | 32 |
| Writable temporary storage | 16 MiB |
| Source-and-arguments payload | 64 KiB |
| Captured print output | 32 KiB |
| Worker-protocol output | 64 KiB |

The configuration is serialisable so its hash can be recorded with each run (consumed by `add-run-bundles-and-grading-replay`) and held fixed across compared variants. Oversized payloads are rejected before a container starts.

### 3. Worker-reporting integrity

The protection technique is an implementation decision, constrained by the probes: candidate code must not be able to emit a protocol message that the trusted side accepts as a genuine result, nor hide argument mutation. Candidate options to evaluate during implementation include an unpredictable per-check protocol token unavailable to candidate code, a separate reporting process, and comparing a trusted-side serialisation of the arguments after the call. The chosen approach, its rationale, and what it does not protect against are recorded in the threat model. Host isolation passing does not by itself establish integrity.

### 4. Infrastructure versus candidate outcomes

Container start failures, unavailable Podman, and malformed/missing/oversized worker-protocol output that cannot be attributed to the candidate's own behaviour are infrastructure outcomes. Candidate exceptions, timeouts, excessive print output, and mutation are candidate outcomes. Payload-too-large is reported as its own classification before any container starts; whether it is a candidate failure is an open decision recorded in `add-reviewed-benchmark-and-graders/design.md` (proposed: candidate failure). Downstream accounting (`add-reviewed-benchmark-and-graders`) maps outcomes to failures or incomplete runs.

### 5. Probes and threat model

Probes are deliberately hostile candidates run through the real mechanism: read host files, read host environment/credentials, open network connections, write read-only paths, exceed the deadline, flood output, mutate inputs, forge a worker response, and conceal mutation. Each probe asserts the trusted-side classification. A short threat-model document lists assets (expected answers, credentials, tracking, Podman control, score integrity), attacker capability (arbitrary Python inside the container), protections, and residual limitations.

## Risks / Trade-offs

- Container startup consumes part of the 10-second deadline → measure startup in each environment and record it; do not silently raise the limit after baseline.
- Hardening fixes may change pilot behaviour → keep pilot tests and add probes; rerun before comparison.
- Environment differences (macOS Podman VM vs Linux CI) → verify limits and probes on each environment actually used.
- A bypass found late → live comparison waits; scoring evidence is not trusted until resolved.

## Migration Plan

Restore the pinned image, run current probes to record the baseline state, change the deadline default and limits, harden worker reporting, add targeted probes, write the threat model, and record observed results in progress. Rollback restores the previous sandbox module; no stored evidence depends on it before live runs.
