# Tasks

Planned for day 1 (bundles/regrading, 2h), after the execution boundary and agent fixtures. All tasks are implemented; see docs/progress.md for evidence.

## 1. Bundle writer

- [x] 1.1 Define the versioned manifest and per-trial record schema (identity, planned IDs, version/config hashes, requests/responses, tool interactions, candidates, final source, grades, usage, reservation fields) and write records incrementally with atomic file replacement.
- [x] 1.2 Integrate the writer with the fixture-driven trial controller; test interrupted runs retain partial evidence and are marked incomplete.
- [x] 1.3 Exclude credentials/authorization headers via an allowlist; test with a fake key; verify bundle storage is ignored by Git.

## 2. Read paths

- [x] 2.1 Add a trace-inspection command that works with Podman and network unavailable; test it imports no API client and starts no containers.
- [x] 2.2 Add a grading-replay command that regrades saved final candidates with Podman and no credentials, writes linked separate replay evidence, verifies benchmark hash, and reports mismatches.
- [x] 2.3 Add completeness verification against planned task/trial IDs and executed-check validity, exposed for reuse by the benchmark/grading accounting (single owner of this check).

## 3. Documentation and evidence

- [x] 3.1 Document the bundle location/layout and exact inspection/replay commands in README, labelling replay as regrading rather than reproduction.
- [x] 3.2 Run a fixture-driven run, inspection, and replay of known candidates; record commands and observed results in docs/progress.md.
