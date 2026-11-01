# Merge and CI checklist

Run as coordinator, from the primary checkout, for one change at a time. Each step ends on its stated condition.

1. **Confirm readiness.** Latest review has no blocker or major finding (or every one is recorded as declined with a reason), and the worker's `worker_done` named a clean tree. Done when you can quote the branch and final commit hash.
2. **Fast-forward.** `git merge --ff-only <branch>` on `main`. Done when it succeeds without a merge commit. If `main` moved, have the worker rebase on `main`, re-review the delta, and start again.
3. **Unit tests.** `uv sync --python 3.12 --group tracking`, then `.venv/bin/pytest -q`. Save the output to a file.
4. **Sandbox suite** (needs the running Podman VM): `CODEGEN_EVAL_TEST_SECRET=present RUN_SANDBOX_TESTS=1 .venv/bin/pytest -q -m sandbox`. Save the output.
5. **Search the output for `failed`**: `grep -ci failed <output file>` for both runs. Done when the count is 0 and the summary lines show the expected passed counts. Exit codes and `tail` output are not evidence (a `&&` chain can hide a failure). A failure under load follows [recovery.md](recovery.md).
6. **Other checks:** `openspec validate --all --strict`, `.venv/bin/python scripts/build_work_log.py --check`, and `scripts/freeze_benchmark.py --check` when the change touches the benchmark.
7. **Push** `main`. Done when `git status -sb` shows no ahead count.
8. **Watch CI.** Find the run for the pushed commit on GitHub Actions, then `scripts/orchestration/ciwatch.sh <run_id>` (`--repo` or `CIWATCH_REPO` overrides the `origin` default). Done when the run concludes `success` for the pushed commit hash; note the run id in `STATE.md`.
9. **CI red:** dispatch the fix per lifecycle step 6. The worker reproduces on Linux, pushes a `ci/<name>` branch, and shows green there; only then merge to `main`, and watch CI again from step 8. Local arm64 runs do not cover the amd64 runner: prefer host-independent artifacts.
10. **After green:** rebuild the work log (`scripts/build_work_log.py`, then `--check`), update `STATE.md`, and archive the change when its tasks are all done.
