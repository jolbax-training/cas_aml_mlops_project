# Tasks

All tasks except 2.3 are done (green run 41128433037; failure demonstrations in runs 41128978798 and 41128979150). 2.3 (branch protection) is a user step in GitHub settings. Runner image, job names, and exact versions are bounded implementation choices to verify and document.

## 1. Workflow

- [x] 1.1 Add a GitHub Actions workflow with a deterministic evaluator/benchmark/agent-loop group installing locked dependencies via uv and a pinned Python version.
- [x] 1.2 Add a Podman execution/isolation group on a compatible Linux runner, pulling the candidate image by pinned digest, with Podman-dependent skips treated as failures.
- [x] 1.3 Confirm the workflow defines no model secrets and that no test path issues a model request.

## 2. Verification

- [x] 2.1 Run the workflow and verify both groups pass with limits enforced on the runner; document any residual differences from the laptop environment.
- [x] 2.2 Demonstrate that deliberately breaking a fixture expectation fails the relevant group, then restore it.
- [x] 2.3 Mark both groups as required checks and document how they are configured. Done 2026-11-06: repository ruleset `main` (id 26678579) is active on `refs/heads/main` with required status checks `offline` and `podman` (GitHub Actions); configuration documented in docs/ci_evidence.md.

## 3. Evidence and documentation

- [x] 3.1 Document runner, Podman, Python, dependency, and image versions plus how to reproduce each group locally.
- [x] 3.2 Record actual CI run identifiers, commit, and results in progress and register reviewed CI references for the work log; do not record CI success before it exists.
