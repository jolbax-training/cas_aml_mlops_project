"""Read-only trace inspection of local run bundles.

Imports only the bundle reader: no model client, no sandbox, no evaluator. It never
executes a candidate and works with Podman stopped and the network disabled.

    python -m codegen_eval.trace_inspect list
    python -m codegen_eval.trace_inspect verify RUN
    python -m codegen_eval.trace_inspect show RUN [--trial TRIAL_ID]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from codegen_eval.bundle import (
    DEFAULT_BUNDLE_ROOT, BundleError, Verification, list_runs, load_manifest, load_trial,
    resolve_bundle, verify_bundle,
)


def _print_verification(result: Verification) -> None:
    state = "COMPLETE" if result.complete else "INCOMPLETE"
    print(f"completeness: {state} — {len(result.recorded)} of {len(result.planned)} planned "
          f"trials have intact records")
    for problem in result.problems:
        where = f" [{problem.trial_id}]" if problem.trial_id else ""
        print(f"  problem {problem.kind}{where}: {problem.detail}")
    if result.grades_pending:
        print(f"  grades pending: {', '.join(result.grades_pending)}")
    if result.bundle_digest:
        print(f"bundle digest (sha256 of manifest.json): {result.bundle_digest}")


def _show_message(message: dict[str, Any]) -> None:
    role = message.get("role", "?")
    if message.get("content") is not None:
        print(f"  [{role}] {message['content']}")
    for call in message.get("tool_calls", []):
        print(f"  [{role} tool call {call.get('id')}] {call.get('name')}: {call.get('arguments')}")
    if role == "tool":
        print(f"    (reply to {message.get('tool_call_id')})")


def show_trial(bundle_dir: Any, trial_id: str) -> None:
    record = load_trial(bundle_dir, trial_id)
    print(f"\n== trial {trial_id} (task {record.get('task_id')}) ==")
    print(f"status: {record.get('status')}  label: {record.get('label')}  "
          f"infrastructure: {record.get('infrastructure_status')}")
    print(f"model calls: {record.get('model_calls')}  tool attempts: {record.get('tool_attempts')}  "
          f"usage: {json.dumps(record.get('usage'), sort_keys=True)}")
    if record.get("contract_issue"):
        print(f"contract issue: {record['contract_issue']['code']}: {record['contract_issue']['detail']}")
    print("messages:")
    for message in record.get("messages", []):
        _show_message(message)
    for draft in record.get("candidate_history", []):
        print(f"candidate draft from tool attempt {draft['attempt']}: "
              f"{json.dumps(draft['result'], sort_keys=True)}")
    print("final source:")
    print(record["final_source"] if record.get("final_source") is not None else "  (none)")
    grades = record.get("grades", {})
    print(f"grades: {grades.get('status')}")
    for check in grades.get("checks", []):
        outcome = "pass" if check["passed"] else "fail " + ",".join(check["failures"])
        print(f"  {check['case_id']} ({check.get('kind')}): {outcome}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect saved run bundles without any service.")
    parser.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT, help="bundle storage directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list runs")
    verify = sub.add_parser("verify", help="check a bundle against its planned trials")
    verify.add_argument("run")
    show = sub.add_parser("show", help="show a run's identity and trial traces")
    show.add_argument("run")
    show.add_argument("--trial", help="show only this trial")
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            for path in list_runs(args.bundles):
                result = verify_bundle(path)
                manifest = load_manifest(path) if result.run_id else {}
                print(f"{path.name}\t{manifest.get('status')}\t"
                      f"{len(result.recorded)}/{len(result.planned)} trials\t"
                      f"{'ok' if result.complete else 'PROBLEMS'}")
            return 0
        path = resolve_bundle(args.bundles, args.run)
        result = verify_bundle(path)
        if args.command == "verify":
            _print_verification(result)
            return 0 if result.complete else 1
        manifest = load_manifest(path)
        print(f"run {manifest['run_id']}  status: {manifest['status']}  "
              f"created: {manifest['created_at']}")
        print(json.dumps(manifest["identity"], indent=2, sort_keys=True))
        _print_verification(result)
        shown = [args.trial] if args.trial else list(result.recorded)
        for trial_id in shown:
            show_trial(path, trial_id)
        return 0
    except BundleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
