# Define trustworthy execution and scoring boundaries

Label: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: 01

## Question

Given the agreed agent tools, what threat model, container restrictions, worker-protocol protections, and isolation evidence are required before live execution? Define what the agent can observe during development, what remains hidden for final grading, how generated code is separated from credentials and container controls, and which risks must be resolved versus explicitly documented.

## Comments

### Q18 — User-confirmed assurance requirements

Target a controlled course-project environment with documented residual limitations. Existing host-file, environment, network, filesystem, timeout, and output probes must pass. Add targeted probes for forged worker responses and concealed input mutation. A demonstrated scoring bypass must be resolved before live comparison results are trusted. Production security certification is outside scope. The current shared-process worker is not treated as trustworthy merely because its container isolates the host.

### Q19 — User-confirmed execution and information boundaries

Development checks and final acceptance checks use the same restricted execution mechanism, with a fresh container for each individual check. Candidate containers receive only candidate source, the function name, and that check's arguments. Expected answers and comparison logic remain in the trusted orchestration layer. No repository mounts, credentials, MLflow access, Podman control socket, or network access are provided to candidate containers. Resource use is bounded, and no filesystem or process state is intentionally reused between checks. Trusted orchestration handles development feedback, final grading, and result recording.

Precise execution limits and the maximum development-check batch remain to be settled. This ticket is still active; the requirements above are planned acceptance criteria, not claims that the current implementation satisfies them.

### Q20 — User-confirmed resource limits

The user accepted the proposed limits with one revision: the execution deadline is **10 seconds per check**, superseding the proposed eight seconds. The four-development-check batch limit and other limits were accepted unchanged.

## Answer

User-confirmed through Q18–Q20:

- Target a controlled course-project environment with documented residual limitations. Require host-file, environment, network, filesystem, timeout, and excessive-output isolation probes, plus targeted forged-response and concealed-mutation probes. Resolve demonstrated scoring bypasses before trusting live comparisons. Production security certification is outside scope.
- Use the same restricted execution mechanism for agent-authored development checks and hidden final acceptance checks. Each individual check gets a fresh disposable Podman container. Only source, the function name, and that check's arguments enter candidate execution; expected answers and comparison logic remain outside it.
- Candidate containers have no repository mounts, credentials, tracking access, Podman control socket, or network access. They do not intentionally share state across checks. Trusted orchestration handles feedback, grading, and evidence recording.
- Limit each `run_checks` request to four development checks. Combined with the agreed three attempted tool calls, a trial executes at most twelve development checks before separate hidden acceptance checks. Oversized requests return argument-error feedback and consume the attempted tool call.
- Configure a 10-second execution deadline per check, 128 MiB memory, one CPU allocation, 32 processes, 16 MiB writable temporary storage, 64 KiB source-and-arguments payload, 32 KiB captured print output, and 64 KiB worker-protocol output. The 10-second deadline supersedes the pilot's eight-second default and applies to the execution exchange including container startup/loading; cleanup is handled separately.
- Keep limits configurable, verify them on every execution environment actually used, and hold them fixed across compared variants. Exact implementation and successful probe results remain implementation exit evidence, not facts established by this planning decision. The existing shared-process worker must not be assumed to provide scoring integrity merely because its host isolation probes pass.
