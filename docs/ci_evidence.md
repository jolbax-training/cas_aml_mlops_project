# Deterministic CI evidence

Reviewed 2026-10-30 against the GitHub Actions annotations the coordinator relayed; the job logs were not read. Run links are references and are never fetched by this repository.

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). Jobs `offline` and `podman`; no secrets, no model calls, no pass-rate gates. Versions and reproduction commands are in the [README](../README.md#deterministic-ci-github-actions).

## Current green run on the rebased tree

| Field | Value |
| --- | --- |
| Run | [41131517803](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41131517803) |
| Branch / commit | `barahjos/add-deterministic-ci` / `15c9eb9` (rebased onto `main`) |
| `offline` | success |
| `podman` | success: 64 tests, 0 skipped, 0 failures |

This supersedes the run below as the evidence for the current tree; the workflow and code were not changed to obtain it.

## Earlier passing run (history, pre-rebase; completion evidence for task 2.1)

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

## Failure demonstration (task 2.2)

Two throwaway branches, each one commit on top of `ef1186e` that breaks one fixture expectation. The breaking commits were never merged; the expectations on the real branch are unchanged.

| Run | Branch / commit | Break | `offline` | `podman` |
| --- | --- | --- | --- | --- |
| [41128978798](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41128978798) | `ci/demo-broken-offline` / `bf0a259` | expectation in `tests/test_evaluate.py::test_ordinary_failure_remains_visible_alongside_passing_cases` | **failed** at the `pytest -q` step | success (63 tests, 0 failures) |
| [41128979150](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41128979150) | `ci/demo-broken-podman` / `3bf42da` | `exception` row of `SANDBOX_FIXTURES` in `tests/test_grading.py` expects `wrong_answer` | success | **failed**: 1 of 63, `tests.test_grading::test_sandbox_fixture_accounting[exception]` (actual `exception`, expected `wrong_answer`) |

Each broken expectation failed only the group that owns it, with the offending test named in an annotation, as the "Broken grading behavior" scenario requires.

## Rebased branch

After the runs above, the branch was rebased onto `main` (which gained its own container-cleanup changes in `sandbox.py`: `rm -t 0`, bounded removal, pid-prefixed names). The rebased commit `15c9eb9` ran green on GitHub: run [41131517803](https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/41131517803) (`offline` success; `podman` success, 64 tests, 0 skipped, 0 failures), recorded above.

## Required checks (task 2.3)

Configured 2026-11-06 by the user as repository ruleset `main` (id 26678579), checked through the public API (`GET /repos/jolbax-training/cas_aml_mlops_project/rulesets/26678579`): enforcement `active`, target `refs/heads/main`, rules `deletion`, `non_fast_forward` and `required_status_checks` with `offline` and `podman` (integration 15368, GitHub Actions; strict policy off), no pull-request rule. Repository admins may bypass (`always`), so the coordinator's direct pushes to `main` still go through; the next push after activation (`7212a36`, CI run 42192054359) ran both checks green.
