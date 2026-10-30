"""Run bounded agent trials and write each finished trial to a local bundle.

Evidence is written before anything consumes it: every trial record is on disk, with
its hash in the manifest, before the next trial starts. A crash or interrupt leaves the
completed records and an `incomplete` manifest.

Fixture example (no model API; Podman only if the scenario calls `run_checks`):

    python -m codegen_eval.run_recording --scenario early_submission --task strings_01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from codegen_eval.agent_config import (
    DEFAULT_AGENT_LIMITS, AgentLimits, AgentPrompt, load_prompt,
)
from codegen_eval.bundle import (
    DEFAULT_BUNDLE_ROOT, PENDING_GRADES, BundleWriter, Grader, Verification, evaluator_revision,
    grades_record, new_run_id, runtime_identity, sanitize_request, sanitize_response, sha256_file,
    utc_now,
)
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.model_client import (
    FixtureClient, ModelClient, ModelFailure, ModelRequest, ModelResponse, load_fixtures,
)
from codegen_eval.sandbox import IMAGE, ExecutionResult, execute_check
from codegen_eval.tasks import Task, load_benchmark
from codegen_eval.trial import SUBMITTED, TrialResult, run_trial

ROOT = Path(__file__).resolve().parents[2]


class RecordingClient:
    """Wrap a client and keep the allowlisted form of every request and response."""

    def __init__(self, inner: ModelClient) -> None:
        self.inner = inner
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []

    def complete(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        self.requests.append(sanitize_request({
            "messages": [dict(m) for m in request.messages],
            "tools": [dict(t) for t in request.tools],
            "tool_choice": request.tool_choice}))
        response = self.inner.complete(request)
        if isinstance(response, ModelFailure):
            raw: dict[str, Any] = {"failure": response.kind, "detail": response.detail}
        else:
            raw = {"content": response.content, "truncated": response.truncated,
                   "usage": dict(response.usage) if response.usage else None,
                   "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments}
                                  for c in response.tool_calls]}
        self.responses.append(sanitize_response(raw))
        return response


def _usage_totals(responses: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for response in responses:
        for key, value in (response.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                totals[key] = totals.get(key, 0) + value
    return totals


def trial_record(trial_id: str, task: Task, result: TrialResult, client: RecordingClient,
                 grades: dict[str, Any]) -> dict[str, Any]:
    submitted = result.status == SUBMITTED
    return {
        "trial_id": trial_id,
        "task_id": task.id,
        "recorded_at": utc_now(),
        "status": result.status,
        "label": result.label,
        "infrastructure_status": result.infrastructure_status,
        "contract_issue": ({"code": result.contract_issue.code, "detail": result.contract_issue.detail}
                           if result.contract_issue else None),
        "contract_valid": result.contract_valid,
        "final_source": result.submission if submitted else None,
        "model_calls": result.model_calls,
        "tool_attempts": result.tool_attempts,
        "prompt": {"version": result.prompt_version, "sha256": result.prompt_sha256},
        "agent_limits_hash": result.limits_hash,
        "requests": client.requests,
        "responses": client.responses,
        "messages": [dict(m) for m in result.messages],
        "events": [dict(e) for e in result.events],
        "candidate_history": [{"attempt": d.attempt, "source": d.source, "result": d.result}
                              for d in result.drafts],
        "usage": _usage_totals(client.responses),
        "reservation": None,  # filled by the budget ledger change: reserved/reported cost
        "errors": [],
        "grades": grades,
    }


def build_identity(benchmark_path: Path, prompt: AgentPrompt, agent_limits: AgentLimits,
                   execution_limits: ExecutionLimits,
                   model_settings: Mapping[str, Any] | None) -> dict[str, Any]:
    envelope = json.loads(benchmark_path.read_text(encoding="utf-8"))
    lock = ROOT / "uv.lock"
    return {
        "prompt": {"version": prompt.version, "sha256": prompt.sha256},
        "benchmark": {"file": benchmark_path.name, "version": envelope.get("benchmark_version"),
                      "sha256": sha256_file(benchmark_path)},
        "agent_limits": {"hash": agent_limits.config_hash(), **agent_limits.to_dict()},
        "execution_limits": {"hash": execution_limits.config_hash(), **execution_limits.to_dict()},
        "evaluator_revision": evaluator_revision(),
        "runtime": runtime_identity(),
        "dependencies": {"uv_lock_sha256": sha256_file(lock) if lock.is_file() else None},
        "container_image": IMAGE,
        "model": dict(model_settings or {"client": "unspecified"}),
    }


def run_recorded(
    tasks: Sequence[Task],
    client_for: Callable[[Task, str], ModelClient],
    benchmark_path: str | Path,
    *,
    bundle_root: str | Path = DEFAULT_BUNDLE_ROOT,
    run_id: str | None = None,
    trials_per_task: int = 1,
    grader: Grader | None = None,
    prompt: AgentPrompt | None = None,
    limits: AgentLimits = DEFAULT_AGENT_LIMITS,
    execution_limits: ExecutionLimits = DEFAULT_LIMITS,
    runner: Callable[..., ExecutionResult] = execute_check,
    model_settings: Mapping[str, Any] | None = None,
) -> tuple[Path, Verification]:
    """Run every planned trial, persisting each record as it finishes; returns the bundle."""
    prompt = prompt or load_prompt()
    planned = [{"task_id": t.id, "trial_id": f"{t.id}-t{n}"}
               for t in tasks for n in range(1, trials_per_task + 1)]
    identity = build_identity(Path(benchmark_path), prompt, limits, execution_limits,
                              model_settings)
    writer = BundleWriter(bundle_root, run_id or new_run_id(), planned, identity)
    by_id = {t.id: t for t in tasks}
    try:
        for item in planned:
            task = by_id[item["task_id"]]
            client = RecordingClient(client_for(task, item["trial_id"]))
            result = run_trial(task, client, prompt=prompt, limits=limits,
                               execution_limits=execution_limits, runner=runner)
            grades = (grades_record(grader(task.id, result.submission))
                      if grader and result.status == SUBMITTED else dict(PENDING_GRADES))
            writer.write_trial(trial_record(item["trial_id"], task, result, client, grades))
    except BaseException as error:  # keep partial evidence, including on Ctrl-C
        writer.finish([f"interrupted: {type(error).__name__}"])
        raise
    return writer.path, writer.finish()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run recorded-response fixture trials into a bundle.")
    parser.add_argument("--benchmark", default=str(ROOT / "data" / "benchmark_v1.json"))
    parser.add_argument("--fixtures", default=str(ROOT / "tests" / "fixtures" / "agent" / "trials.json"))
    parser.add_argument("--scenario", required=True, help="fixture scenario name")
    parser.add_argument("--task", action="append", help="task id (repeatable); default: all")
    parser.add_argument("--trials", type=int, default=1, help="trials per task")
    parser.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--grade", action="store_true", help="grade final sources now (needs Podman)")
    args = parser.parse_args(argv)

    scenarios = load_fixtures(args.fixtures)
    if args.scenario not in scenarios:
        parser.error(f"unknown scenario {args.scenario!r}")
    tasks = load_benchmark(args.benchmark)
    if args.task:
        tasks = tuple(t for t in tasks if t.id in set(args.task))
        if not tasks:
            parser.error("no matching task ids")
    grader = None
    if args.grade:
        from codegen_eval.replay import make_grader
        grader = make_grader({t.id: t for t in tasks})
    path, result = run_recorded(
        tasks, lambda task, trial_id: FixtureClient.from_data(scenarios[args.scenario]),
        args.benchmark, bundle_root=args.bundles, trials_per_task=args.trials, grader=grader,
        model_settings={"client": "fixture", "scenario": args.scenario})
    print(f"bundle: {path}")
    print(f"recorded {len(result.recorded)} of {len(result.planned)} planned trials; "
          f"complete={result.complete}; grades pending for {len(result.grades_pending)}")
    return 0 if result.complete else 1


if __name__ == "__main__":
    sys.exit(main())
