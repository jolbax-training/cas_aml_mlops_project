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
    BUNDLE_SCHEMA_VERSION, DEFAULT_BUNDLE_ROOT, GRADE_PENDING, TAMPERED_RECORD, UNEXPECTED_RECORD,
    UNRECORDED_RECORD, UNREADABLE_MANIFEST, UNREADABLE_RECORD, UNSUPPORTED_SCHEMA, BundleError,
    Grader, evaluator_revision, grades_record, load_manifest, load_trial, resolve_bundle,
    sha256_file, source_tree_sha256, utc_now, verify_bundle, write_replay,
)
from codegen_eval.contract import ContractIssue
from codegen_eval.evaluate import grade_trial
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.sandbox import IMAGE, ExecutionResult, run_case
from codegen_eval.tasks import Case, FREEZE_FILE, Task, freeze_manifest, load_benchmark
from codegen_eval.trial import TrialResult

ROOT = Path(__file__).resolve().parents[2]
REPLAY_NOTE = ("Grading replay: saved final candidates were re-executed and regraded. "
               "No model was called and no agent trial was reproduced.")
# Problems that make a record's contents untrustworthy as replay input.
_BLOCKING = {TAMPERED_RECORD, UNREADABLE_RECORD, UNSUPPORTED_SCHEMA, UNREADABLE_MANIFEST,
             UNEXPECTED_RECORD, UNRECORDED_RECORD}

Runner = Callable[[str, Task, Case], ExecutionResult]


def make_grader(runner: Runner = run_case) -> Grader:
    """The grading side's own function, `evaluate.grade_trial`, bound to a case runner."""
    return lambda task, trial: grade_trial(task, trial, runner)


def trial_from_record(record: Mapping[str, Any]) -> TrialResult:
    """Rebuild the parts of a trial that grading reads (status, label, submission,
    contract verdict, infrastructure status) from its saved record."""
    issue = record.get("contract_issue")
    prompt = record.get("prompt") or {}
    return TrialResult(
        status=record["status"], label=record.get("label"), submission=record.get("final_source"),
        contract_issue=ContractIssue(issue["code"], issue["detail"]) if issue else None,
        infrastructure_status=record.get("infrastructure_status"),
        model_calls=record.get("model_calls", 0), tool_attempts=record.get("tool_attempts", 0),
        drafts=(), messages=(), events=(), limits_hash=record.get("agent_limits_hash", ""),
        prompt_version=prompt.get("version", ""), prompt_sha256=prompt.get("sha256", ""))


def _outcomes(grades: Mapping[str, Any]) -> dict[str, tuple[bool, bool, tuple[str, ...]]]:
    return {c["id"]: (c["executed"], c["passed"], tuple(c["failures"]))
            for c in grades.get("checks", [])}


def compare_grades(original: Mapping[str, Any], replayed: Mapping[str, Any]) -> list[str]:
    """Describe each difference between original and replayed grades (empty when equal)."""
    notes = []
    for key in ("labels", "success", "incomplete", "infrastructure_status"):
        if original.get(key) != replayed.get(key):
            notes.append(f"{key}: original {original.get(key)!r} replay {replayed.get(key)!r}")
    before, after = _outcomes(original), _outcomes(replayed)
    for case_id in sorted(before.keys() | after.keys()):
        if before.get(case_id) != after.get(case_id):
            notes.append(f"{case_id}: original {before.get(case_id)} replay {after.get(case_id)}")
    return notes


def _check_benchmark_identity(manifest: Mapping[str, Any], benchmark_path: Path) -> str:
    recorded = manifest["identity"].get("benchmark", {})
    if not isinstance(recorded.get("sha256"), str):
        raise BundleError("manifest identity has no benchmark hash")
    actual = sha256_file(benchmark_path)
    if actual != recorded["sha256"]:
        raise BundleError(f"benchmark mismatch: bundle recorded {recorded['sha256']} but "
                          f"{benchmark_path} hashes to {actual}; refusing to grade "
                          f"against different checks")
    freeze = recorded.get("freeze_content_hash")
    if freeze is not None:  # also covers the reference solutions and the review record
        root = benchmark_path.resolve().parent.parent
        try:
            current = freeze_manifest(root)["content_hash"]
        except (OSError, KeyError, ValueError) as error:
            raise BundleError(f"cannot recompute the benchmark freeze under {root}: {error}") from error
        if current != freeze:
            raise BundleError(f"benchmark freeze mismatch: bundle recorded {freeze} but the "
                              f"files under {root} hash to {current} ({FREEZE_FILE}); refusing "
                              f"to grade against different checks")
    return actual


def replay_bundle(
    bundle_dir: str | Path,
    benchmark_path: str | Path,
    *,
    runner: Runner | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Regrade a bundle's saved final candidates and write linked replay evidence."""
    path = Path(bundle_dir)
    manifest = load_manifest(path)
    verification = verify_bundle(path)
    blocking = [p for p in verification.problems if p.kind in _BLOCKING]
    if blocking:
        raise BundleError("bundle cannot be replayed: " + "; ".join(
            f"{p.kind}{' ' + p.trial_id if p.trial_id else ''}: {p.detail}" for p in blocking))

    actual_hash = _check_benchmark_identity(manifest, Path(benchmark_path))
    tasks = {t.id: t for t in load_benchmark(benchmark_path)}
    identity = manifest["identity"]
    limits_data = {k: v for k, v in identity.get("execution_limits", {}).items() if k != "hash"}
    try:
        limits = ExecutionLimits.from_dict(limits_data) if limits_data else DEFAULT_LIMITS
    except (TypeError, ValueError) as error:
        raise BundleError(f"recorded execution limits are invalid: {error}") from error
    grader = make_grader(runner or (lambda s, t, c: run_case(s, t, c, limits=limits)))

    trials: list[dict[str, Any]] = []
    for trial_id in verification.recorded:
        record = load_trial(path, trial_id)
        task = tasks.get(record["task_id"])
        if task is None:
            raise BundleError(f"task {record['task_id']} is not in the retained benchmark")
        try:
            replayed = grades_record(grader(task, trial_from_record(record)))
        except (KeyError, TypeError, ValueError) as error:
            raise BundleError(f"trial {trial_id} cannot be regraded: {error}") from error
        original = record.get("grades", {"status": GRADE_PENDING})
        entry: dict[str, Any] = {"trial_id": trial_id, "task_id": task.id, "grades": replayed}
        if original.get("status") == GRADE_PENDING:
            entry["original"] = "pending: nothing to compare"
        else:
            entry["mismatches"] = compare_grades(original, replayed)
        trials.append(entry)

    environment = {
        "container_image": (identity.get("container_image"), IMAGE),
        "evaluator_revision": (identity.get("evaluator_revision"), evaluator_revision()),
        "evaluator_source_sha256": (identity.get("evaluator_source_sha256"), source_tree_sha256()),
        "execution_limits_hash": (identity.get("execution_limits", {}).get("hash"),
                                  limits.config_hash()),
    }
    differences = {k: {"original": a, "replay": b} for k, (a, b) in environment.items() if a != b}
    compared = [t for t in trials if "mismatches" in t]
    evidence = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "kind": "grading_replay",
        "note": REPLAY_NOTE,
        "replay_id": "replay-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                     + "-" + uuid.uuid4().hex[:6],
        "run_id": manifest["run_id"],
        "linked_manifest_sha256": verification.bundle_digest,
        "created_at": utc_now(),
        "evaluator_revision": environment["evaluator_revision"][1],
        "evaluator_source_sha256": environment["evaluator_source_sha256"][1],
        "container_image": IMAGE,
        "benchmark_sha256": actual_hash,
        "benchmark_freeze_content_hash": identity.get("benchmark", {}).get("freeze_content_hash"),
        "execution_limits_hash": limits.config_hash(),
        "environment_differences": differences,
        "original_run_complete": verification.complete,
        "original_problems": [{"kind": p.kind, "trial_id": p.trial_id, "detail": p.detail}
                              for p in verification.problems],
        "missing_original_records": list(verification.missing()),
        "trials": trials,
        "summary": {
            "regraded": len(trials),
            "compared": len(compared),
            "mismatched": sum(bool(t["mismatches"]) for t in compared),
            "incomplete": sum(t["grades"]["incomplete"] for t in trials),
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
        grades = trial["grades"]
        checks = grades["checks"]
        line = (f"  {trial['trial_id']}: {sum(c['passed'] for c in checks)}/{len(checks)} checks passed"
                f"; labels {grades['labels']}" + ("; INCOMPLETE" if grades["incomplete"] else ""))
        if trial.get("mismatches"):
            line += f"; MISMATCH vs original: {trial['mismatches']}"
        print(line)
    for key, values in evidence["environment_differences"].items():
        print(f"  environment differs ({key}): original {values['original']} replay {values['replay']}")
    for problem in evidence["original_problems"]:
        print(f"  original bundle problem {problem['kind']} [{problem['trial_id']}]: {problem['detail']}")
    summary = evidence["summary"]
    print(f"summary: {summary}")
    return 1 if summary["mismatched"] or summary["incomplete"] else 0


if __name__ == "__main__":
    sys.exit(main())
