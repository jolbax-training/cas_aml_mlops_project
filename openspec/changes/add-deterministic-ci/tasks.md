# Tasks

Tasks 1.1–1.3 and 3.1 are implemented; 2.1–2.3 and 3.2 await real GitHub Actions runs. Runner image, job names, and exact versions are bounded implementation choices to verify and document.

## 1. Workflow

- [x] 1.1 Add a GitHub Actions workflow with a deterministic evaluator/benchmark/agent-loop group installing locked dependencies via uv and a pinned Python version.
- [x] 1.2 Add a Podman execution/isolation group on a compatible Linux runner, pulling the candidate image by pinned digest, with Podman-dependent skips treated as failures.
- [x] 1.3 Confirm the workflow defines no model secrets and that no test path issues a model request.

## 2. Verification

- [ ] 2.1 Run the workflow and verify both groups pass with limits enforced on the runner; document any residual differences from the laptop environment.
- [ ] 2.2 Demonstrate that deliberately breaking a fixture expectation fails the relevant group, then restore it.
- [ ] 2.3 Mark both groups as required checks and document how they are configured.

## 3. Evidence and documentation

- [x] 3.1 Document runner, Podman, Python, dependency, and image versions plus how to reproduce each group locally.
- [ ] 3.2 Record actual CI run identifiers, commit, and results in progress and register reviewed CI references for the work log; do not record CI success before it exists.
