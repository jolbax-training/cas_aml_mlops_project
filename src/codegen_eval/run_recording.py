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
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from codegen_eval.agent_config import (
    DEFAULT_AGENT_LIMITS, AgentLimits, AgentPrompt, load_prompt,
)
from codegen_eval.bundle import (
    DEFAULT_BUNDLE_ROOT, PENDING_GRADES, BundleError, BundleWriter, Grader, Verification,
    evaluator_revision, grades_record, new_run_id, runtime_identity, sanitize_request,
    sanitize_response, sha256_file, source_tree_sha256, utc_now,
)
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.model_client import (
    FixtureClient, ModelClient, ModelFailure, ModelRequest, ModelResponse, load_fixtures,
)
from codegen_eval.openrouter_client import BUDGET_CEILING
from codegen_eval.sandbox import IMAGE, ExecutionResult, execute_check
from codegen_eval.tasks import FREEZE_FILE, Task, check_freeze, freeze_manifest, load_benchmark
from codegen_eval.trial import TrialResult, run_trial

ROOT = Path(__file__).resolve().parents[2]


class RecordingClient:
    """Wrap a client and keep the allowlisted form of every request and response.

    `sink`, if given, receives each entry as it happens (the request before it is sent,
    the response as soon as it returns), so the caller can persist paid interactions
    before the trial finishes."""

    def __init__(self, inner: ModelClient,
                 sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.inner = inner
        self.sink = sink
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []  # physical attempts, if the inner client keeps them

    def _emit(self, entry: dict[str, Any]) -> None:
        if self.sink:
            self.sink(entry)

    def _emit_new_attempts(self) -> None:
        # A live client records each physical attempt (including retries); persist them with
        # the call log as soon as the logical call returns or fails.
        for attempt in list(getattr(self.inner, "attempts", ()))[len(self.attempts):]:
            self.attempts.append(attempt)
            self._emit({"event": "attempt", "attempt": attempt})

    def complete(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        call = len(self.requests) + 1
        recorded = sanitize_request({
            "messages": [dict(m) for m in request.messages],
            "tools": [dict(t) for t in request.tools],
            "tool_choice": request.tool_choice})
        self.requests.append(recorded)
        self._emit({"event": "request", "call": call, "request": recorded, "at": utc_now()})
        try:
            response = self.inner.complete(request)
        except BaseException as error:
            self._emit_new_attempts()
            self._emit({"event": "error", "call": call, "error": type(error).__name__,
                        "at": utc_now()})
            raise
        self._emit_new_attempts()
        if isinstance(response, ModelFailure):
            raw: dict[str, Any] = {"failure": response.kind, "detail": response.detail}
        else:
            raw = {"content": response.content, "truncated": response.truncated,
                   "usage": dict(response.usage) if response.usage else None,
                   "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments}
                                  for c in response.tool_calls]}
        clean = sanitize_response(raw)
        self.responses.append(clean)
        self._emit({"event": "response", "call": call, "response": clean, "at": utc_now()})
        return response


def _usage_totals(responses: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for response in responses:
        for key, value in (response.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                totals[key] = totals.get(key, 0) + value
    return totals


def _reservation_total(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    amounts = [Decimal(a["reservation"]["amount_chf"]) for a in attempts if a.get("reservation")]
    if not amounts:
        return None
    return {"total_chf": str(sum(amounts, Decimal(0))), "attempts_reserved": len(amounts)}


def _latency_total(attempts: Sequence[Mapping[str, Any]]) -> int | None:
    values = [a["latency_ms"] for a in attempts if isinstance(a.get("latency_ms"), int)]
    return sum(values) if values else None


def trial_record(trial_id: str, task: Task, result: TrialResult, client: RecordingClient,
                 grades: dict[str, Any]) -> dict[str, Any]:
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
        "final_source": result.submission,  # as returned, even if it failed the source contract
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
        # Filled by a live client; empty or null for the fixture client.
        "reservation": _reservation_total(client.attempts),
        "attempts": client.attempts,   # physical attempts and retries per logical call
        "latency_ms": _latency_total(client.attempts),
        "errors": [a["error_class"] for a in client.attempts if a.get("error_class")],
        "grades": grades,
    }


def freeze_content_hash(benchmark_path: Path) -> str | None:
    """Content hash over the benchmark, references, and review (part B's freeze record).

    None if the benchmark's repository carries no freeze record. A record that no longer
    matches the files is an error: the bundle would otherwise name content it did not use."""
    root = benchmark_path.resolve().parent.parent
    if not (root / FREEZE_FILE).is_file():
        return None
    try:
        check_freeze(root)
    except ValueError as error:
        raise BundleError(str(error)) from error
    return freeze_manifest(root)["content_hash"]


def build_identity(benchmark_path: Path, prompt: AgentPrompt, agent_limits: AgentLimits,
                   execution_limits: ExecutionLimits,
                   model_settings: Mapping[str, Any] | None) -> dict[str, Any]:
    envelope = json.loads(benchmark_path.read_text(encoding="utf-8"))
    lock = ROOT / "uv.lock"
    return {
        "prompt": {"version": prompt.version, "sha256": prompt.sha256},
        "benchmark": {"file": benchmark_path.name, "version": envelope.get("benchmark_version"),
                      "sha256": sha256_file(benchmark_path),
                      "freeze_content_hash": freeze_content_hash(benchmark_path)},
        "agent_limits": {"hash": agent_limits.config_hash(), **agent_limits.to_dict()},
        "execution_limits": {"hash": execution_limits.config_hash(), **execution_limits.to_dict()},
        "evaluator_revision": evaluator_revision(),
        "evaluator_source_sha256": source_tree_sha256(),
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
    extra_secrets: Sequence[str] = (),
    identity_extra: Mapping[str, Any] | None = None,
) -> tuple[Path, Verification]:
    """Run every planned trial, persisting each record as it finishes; returns the bundle.

    `identity_extra` adds named sections (for example an experiment's variant) to the
    bundle identity; it cannot replace a section this module records itself."""
    prompt = prompt or load_prompt()
    planned = [{"task_id": t.id, "trial_id": f"{t.id}-t{n}"}
               for t in tasks for n in range(1, trials_per_task + 1)]
    identity = build_identity(Path(benchmark_path), prompt, limits, execution_limits,
                              model_settings)
    clash = sorted(set(identity_extra or {}) & set(identity))
    if clash:
        raise BundleError(f"identity_extra would replace recorded sections: {', '.join(clash)}")
    identity.update(identity_extra or {})
    writer = BundleWriter(bundle_root, run_id or new_run_id(), planned, identity,
                          extra_secrets=extra_secrets)
    by_id = {t.id: t for t in tasks}
    stopped: list[str] = []
    try:
        for item in planned:
            task = by_id[item["task_id"]]
            trial_id = item["trial_id"]
            client = RecordingClient(client_for(task, trial_id),
                                     lambda entry, t=trial_id: writer.append_call(t, entry))
            result = run_trial(task, client, prompt=prompt, limits=limits,
                               execution_limits=execution_limits, runner=runner)
            grades = grades_record(grader(task, result)) if grader else dict(PENDING_GRADES)
            writer.write_trial(trial_record(item["trial_id"], task, result, client, grades))
            if result.infrastructure_status == BUDGET_CEILING:
                # The ledger ceiling blocks every further paid attempt: keep the bundle and
                # leave the unfinished trials unrecorded, so the run is incomplete.
                stopped.append(f"budget_ceiling: stopped before {item['trial_id']} finished; "
                               "later trials were not run")
                break
    except BaseException as error:  # keep partial evidence, including on Ctrl-C
        writer.finish([f"interrupted: {type(error).__name__}"])
        raise
    return writer.path, writer.finish(stopped)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run recorded-response fixture trials into a bundle.")
    parser.add_argument("--benchmark", default=str(ROOT / "data" / "benchmark_v1.json"))
    parser.add_argument("--fixtures", default=str(ROOT / "tests" / "fixtures" / "agent" / "trials.json"))
    parser.add_argument("--scenario", required=True, help="fixture scenario name")
    parser.add_argument("--task", action="append", help="task id (repeatable); default: all")
    parser.add_argument("--trials", type=int, default=1, help="trials per task")
    parser.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--grade", action="store_true", help="grade every trial now (needs Podman)")
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
        grader = make_grader()
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
