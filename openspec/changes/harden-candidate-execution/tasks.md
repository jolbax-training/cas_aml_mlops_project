# Tasks

Planned for day 1 (boundary/probes, 3h). All tasks are unstarted. Results are recorded only when observed.

## 1. Environment baseline

- [ ] 1.1 Restore the pinned Python image, run the existing Podman integration tests, and record Podman version, VM/host details, image digest, and observed pass/skip/fail counts in docs/progress.md.

## 2. Execution mechanism and limits

- [ ] 2.1 Introduce a single per-check execution entry point that receives only source, function name, and check arguments, and returns raw outcomes with candidate/infrastructure classification; add unit tests showing expected values are never passed.
- [ ] 2.2 Add a serialisable limit configuration with the agreed defaults (10 s deadline including startup, 128 MiB, 1 CPU, 32 processes, 16 MiB tmp, 64 KiB payload, 32 KiB print, 64 KiB protocol), cleanup outside the deadline, and pre-start payload rejection; test each limit through the real container path.
- [ ] 2.3 Confirm container flags: no mounts, credentials, network, tracking, or Podman socket; read-only root, unprivileged user, dropped capabilities, restricted tmp; fresh container per check.

## 3. Scoring integrity

- [ ] 3.1 Harden worker reporting against forged responses and concealed mutation using an approach chosen during implementation; record the rationale.
- [ ] 3.2 Add probes for host files, environment, network, read-only paths, timeout, excessive output, mutation, forged response, and concealed mutation; each asserts the trusted-side classification.

## 4. Documentation and evidence

- [ ] 4.1 Write the threat model with assets, attacker capability, protections, and residual limitations; register it as a work-log source when the report builder exists.
- [ ] 4.2 Run the full probe suite in each environment used and record exact commands, environment, and observed results in docs/progress.md; mark any unresolved bypass as blocking live comparison.
