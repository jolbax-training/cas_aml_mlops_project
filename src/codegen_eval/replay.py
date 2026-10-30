"""Grading replay: re-execute a bundle's saved final candidates against the retained benchmark.

This is regrading of saved code, not reproduction of an agent trial: no model is called,
no credentials are read, and no conversation is regenerated. It needs Podman, because the
hidden checks run through the same container path as the original grading. Results go to
`replays/<replay_id>.json` beside the bundle and never overwrite the original grades.

    python -m codegen_eval.replay RUN [--benchmark data/benchmark_v1.json]
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from codegen_eval.bundle import (
    BUNDLE_SCHEMA_VERSION, DEFAULT_BUNDLE_ROOT, INFRASTRUCTURE_FAILURES, TAMPERED_RECORD,
    UNEXPECTED_RECORD, UNREADABLE_MANIFEST, UNREADABLE_RECORD, UNSUPPORTED_SCHEMA, BundleError,
    CheckGrade, Grader, evaluator_revision, grades_record, load_manifest, load_trial,
    resolve_bundle, sha256_file, utc_now, verify_bundle, write_replay,
)
from codegen_eval.evaluate import evaluate_task
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.sandbox import IMAGE, ExecutionResult, run_case
from codegen_eval.tasks import Case, Task, load_benchmark

ROOT = Path(__file__).resolve().parents[2]
REPLAY_NOTE = ("Grading replay: saved final candidates were re-executed and regraded. "
               "No model was called and no agent trial was reproduced.")
# Problems that make a record's contents untrustworthy as replay input.
_BLOCKING = {TAMPERED_RECORD, UNREADABLE_RECORD, UNSUPPORTED_SCHEMA, UNREADABLE_MANIFEST,
             UNEXPECTED_RECORD}


def make_grader(tasks: Mapping[str, Task],
                runner: Callable[[str, Task, Case], ExecutionResult] = run_case) -> Grader:
    """Grader over the current evaluator: validates the source, then runs each hidden case."""

    def grade(task_id: str, source: str) -> list[CheckGrade]:
        result = evaluate_task(tasks[task_id], source, runner)
        return [CheckGrade(c.id, c.kind, c.executed, c.passed, tuple(c.failures))
                for c in result.cases]

    return grade


def _outcomes(grades: Mapping[str, Any]) -> dict[str, tuple[bool, tuple[str, ...]]]:
    return {c["case_id"]: (c["passed"], tuple(c["failures"])) for c in grades.get("checks", [])}


def compare_grades(original: Mapping[str, Any], replayed: Mapping[str, Any]) -> list[str]:
    """Describe each difference between original and replayed outcomes (empty when equal)."""
    before, after = _outcomes(original), _outcomes(replayed)
    notes = []
    for case_id in sorted(before.keys() | after.keys()):
        if before.get(case_id) != after.get(case_id):
            notes.append(f"{case_id}: original {before.get(case_id)} replay {after.get(case_id)}")
    return notes


def replay_bundle(
    bundle_dir: str | Path,
    benchmark_path: str | Path,
    *,
    runner: Callable[[str, Task, Case], ExecutionResult] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Regrade a bundle's saved final candidates and write linked replay evidence."""
    path = Path(bundle_dir)
    manifest = load_manifest(path)
    verification = verify_bundle(path)
    blocking = [p for p in verification.problems if p.kind in _BLOCKING]
    if blocking:
        raise BundleError("bundle cannot be replayed: " + "; ".join(
            f"{p.kind}{' ' + p.trial_id if p.trial_id else ''}: {p.detail}" for p in blocking))

    recorded_hash = manifest["identity"]["benchmark"]["sha256"]
    actual_hash = sha256_file(benchmark_path)
    if actual_hash != recorded_hash:
        raise BundleError(f"benchmark mismatch: bundle recorded {recorded_hash} but "
                          f"{benchmark_path} hashes to {actual_hash}; refusing to grade "
                          f"against different checks")
    tasks = {t.id: t for t in load_benchmark(benchmark_path)}
    limits_data = {k: v for k, v in manifest["identity"]["execution_limits"].items() if k != "hash"}
    limits = ExecutionLimits.from_dict(limits_data) if limits_data else DEFAULT_LIMITS
    grader = make_grader(tasks, runner or (lambda s, t, c: run_case(s, t, c, limits=limits)))

    trials: list[dict[str, Any]] = []
    for trial_id in verification.recorded:
        record = load_trial(path, trial_id)
        entry: dict[str, Any] = {"trial_id": trial_id, "task_id": record["task_id"]}
        source = record.get("final_source")
        if source is None:
            entry.update(skipped="no final source (status " f"{record.get('status')})")
        elif record["task_id"] not in tasks:
            raise BundleError(f"task {record['task_id']} is not in the retained benchmark")
        else:
            replayed = grades_record(grader(record["task_id"], source))
            original = record.get("grades", {"status": "pending"})
            entry["grades"] = replayed
            if original.get("status") == "graded":
                entry["mismatches"] = compare_grades(original, replayed)
            else:
                entry["original"] = "pending: nothing to compare"
            entry["infrastructure"] = any(f in INFRASTRUCTURE_FAILURES
                                          for c in replayed["checks"] for f in c["failures"])
        trials.append(entry)

    graded = [t for t in trials if "grades" in t]
    evidence = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "kind": "grading_replay",
        "note": REPLAY_NOTE,
        "replay_id": "replay-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                     + "-" + uuid.uuid4().hex[:6],
        "run_id": manifest["run_id"],
        "linked_manifest_sha256": verification.bundle_digest,
        "created_at": utc_now(),
        "evaluator_revision": evaluator_revision(),
        "container_image": IMAGE,
        "benchmark_sha256": actual_hash,
        "execution_limits_hash": limits.config_hash(),
        "original_run_complete": verification.complete,
        "missing_original_records": list(verification.missing()),
        "trials": trials,
        "summary": {
            "regraded": len(graded),
            "skipped": len(trials) - len(graded),
            "mismatched": sum(bool(t.get("mismatches")) for t in graded),
            "infrastructure": sum(bool(t.get("infrastructure")) for t in graded),
            "compared": sum("mismatches" in t for t in graded),
        },
    }
    return write_replay(path, evidence), evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regrade a bundle's saved final candidates in Podman (no model API).")
    parser.add_argument("run", help="run id under --bundles, or a bundle directory")
    parser.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--benchmark", default=str(ROOT / "data" / "benchmark_v1.json"))
    args = parser.parse_args(argv)
    try:
        path, evidence = replay_bundle(resolve_bundle(args.bundles, args.run), args.benchmark)
    except BundleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(REPLAY_NOTE)
    print(f"replay evidence: {path}")
    for trial in evidence["trials"]:
        if "grades" in trial:
            checks = trial["grades"]["checks"]
            print(f"  {trial['trial_id']}: {sum(c['passed'] for c in checks)}/{len(checks)} checks passed"
                  + (f"; MISMATCH vs original: {trial['mismatches']}" if trial.get("mismatches") else ""))
        else:
            print(f"  {trial['trial_id']}: skipped ({trial['skipped']})")
    summary = evidence["summary"]
    print(f"summary: {summary}")
    return 1 if summary["mismatched"] or summary["infrastructure"] else 0


if __name__ == "__main__":
    sys.exit(main())
