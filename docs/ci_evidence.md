# Deterministic CI evidence

Reviewed 2026-10-30 against the GitHub Actions annotations the coordinator relayed; the job logs were not read. Run links are references and are never fetched by this repository.

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). Jobs `offline` and `podman`; no secrets, no model calls, no pass-rate gates. Versions and reproduction commands are in the [README](../README.md#deterministic-ci-github-actions).

## Passing run (completion evidence for task 2.1)

| Field | Value |
| --- | --- |
| Run | [41128433037](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41128433037) |
| Branch / commit | `ci/add-deterministic-ci` / `ef1186e` |
| `offline` | success |
| `podman` | success: 63 tests, 0 skipped, 0 failures, 0 errors; 0 leftover containers |
| Runner | `ubuntu-24.04`, amd64 |
| Podman | 4.9.3, rootful, cgroup v2 (systemd), crun; cpu/memory/pids controllers present |
| Limits probe | `memory.max`/`pids.max`/`cpu.max` = `134217728 32 100000 100000` |
| Candidate image | `python:3.12.14-slim-trixie`, amd64 digest `sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b` |
| Container signals | denied by the default AppArmor profile; passed after Podman's default profile was set to unconfined |

Residual difference from the laptop (macOS VM, Podman 6.1.4, SELinux, arm64): the runner's containers ran without the AppArmor default profile. The audit line that confirmed the cause and the trade-off are in the [threat model](threat_model.md).

## Earlier failing runs (history, not completion evidence)

| Run | Commit | Result |
| --- | --- | --- |
| [41124321745](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41124321745) | `868410f` | `podman` failed in the sandbox tests |
| [41126346781](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41126346781) | `b71134c` | `podman`: 14 of 63 failed (in-container signals denied, container cleanup) |

## Failure demonstration (task 2.2): pending

Not yet run on GitHub. Two throwaway branches break one fixture expectation each; the offline break should fail only `offline`, the sandbox break only `podman`. Run identifiers and results will be added here after the runs exist; nothing is claimed before then.

## Required checks (task 2.3): pending

Marking `offline` and `podman` as required status checks is a repository setting not yet made.
