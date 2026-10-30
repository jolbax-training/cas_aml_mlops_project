"""Record a retained run bundle in MLflow: parameters, metrics, artifacts, and trial traces.

The bundle is the primary evidence; MLflow is a navigable secondary record built from it.
Nothing here imports a model client, the sandbox, or the evaluator, so recording (and a
later upload after an outage) never generates a paid response and needs no credentials.
Candidate containers never see the tracking endpoint: they run with `--network=none`.

Identity and idempotence: a bundle is identified by its run ID and the SHA-256 of its
manifest (the bundle digest). Recording the same identity again is detected and returns
the existing MLflow run without changing it. An interrupted earlier upload is detected by
a missing completion tag; its partial run is deleted and rebuilt from the bundle. A bundle
whose digest differs (the manifest changes only until the run is finalized) is a different
identity and gets its own run, tagged with the same run ID.

    python -m codegen_eval.mlflow_tracking record RUN [--tracking-uri http://127.0.0.1:5000]
    python -m codegen_eval.mlflow_tracking status
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from codegen_eval.bundle import (
    DEFAULT_BUNDLE_ROOT, BundleError, _check_id, atomic_write, list_runs, load_manifest, load_trial,
    read_json, redact_value, resolve_bundle, secret_values, utc_now, verify_bundle,
    Verification, GRADE_GRADED, GRADE_PENDING, UNREADABLE_MANIFEST, UNSUPPORTED_SCHEMA,
    TAMPERED_RECORD, UNREADABLE_RECORD, UNEXPECTED_RECORD, UNRECORDED_RECORD, IDENTITY_MISMATCH,
)

DEFAULT_TRACKING_URI = "http://127.0.0.1:5000"
DEFAULT_EXPERIMENT = "codegen-eval-runs"
SIDECAR = "tracking.json"  # not part of the hashed bundle; says whether it is recorded

TAG = "codegen_eval."
KIND_BUNDLE = "bundle"
KIND_REPLAY = "grading_replay"
UPLOAD_COMPLETE = TAG + "upload_complete"

# Problems that make a bundle's contents untrustworthy as recording input.
_BLOCKING = {UNREADABLE_MANIFEST, UNSUPPORTED_SCHEMA, TAMPERED_RECORD, UNREADABLE_RECORD,
             UNEXPECTED_RECORD, UNRECORDED_RECORD, IDENTITY_MISMATCH}
_BATCH = 90  # MLflow accepts at most 100 params/tags per batch call
_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9_\-. /:]")
_PARAM_MAX = 6000  # MLflow 3's parameter value limit; applied after redaction


class TrackingUnavailable(Exception):
    """The tracking service could not be reached or refused a call; the bundle is untouched."""


@dataclass(frozen=True)
class RecordResult:
    run_id: str                  # MLflow run ID
    created: bool                # False: this bundle identity was already recorded
    replays: tuple[str, ...]     # replay IDs recorded in this call
    redactions: int = 0
    notes: tuple[str, ...] = field(default=())


# --- flattening bundle content into MLflow parameters and metrics -----------------------

def _safe(name: str) -> str:
    return _NAME_UNSAFE.sub("_", name)[:240]


def flatten(prefix: str, value: Any, out: dict[str, str]) -> None:
    """Dotted-key scalars; lists of scalars become JSON text."""
    if isinstance(value, Mapping):
        for key in sorted(value):
            flatten(f"{prefix}.{key}" if prefix else str(key), value[key], out)
    else:
        text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        out[_safe(prefix)] = text


def parameters(manifest: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    flatten("", manifest["identity"], out)
    out["planned_trials"] = str(len(manifest["planned"]))
    return out


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _chf(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(0)


def attempt_measures(record: Mapping[str, Any]) -> dict[str, float]:
    """Totals over a trial's physical attempts (retries included); empty when the bundle has
    none (fixture client). Money is summed as Decimal and logged as a float; a missing value
    counts as zero and is visible through `attempts_missing_fields`."""
    attempts = [a for a in record.get("attempts") or [] if isinstance(a, Mapping)]
    if not attempts:
        return {}
    def total(key: str) -> float:
        return float(sum(a[key] for a in attempts if _numeric(a.get(key))))
    return {
        "attempts": len(attempts),
        "retries": sum(1 for a in attempts if (a.get("retry_index") or 0) > 0),
        "attempt_errors": sum(1 for a in attempts if a.get("error_class")),
        "attempts_sent": sum(1 for a in attempts if a.get("sent")),
        "attempts_provider_mismatch": sum(1 for a in attempts
                                          if a.get("provider_matches_pin") is False),
        "attempts_missing_fields": sum(len(a.get("missing_fields") or []) for a in attempts),
        "latency_ms": total("latency_ms"),
        "prompt_tokens": total("prompt_tokens"),
        "completion_tokens": total("completion_tokens"),
        "reasoning_tokens": total("reasoning_tokens"),
        "cost_reported_usd": total("reported_cost_usd"),
        "cost_reserved_chf": float(sum((_chf(a["reservation"].get("amount_chf"))
                                        for a in attempts if a.get("reservation")), Decimal(0))),
        "cost_charged_chf": float(sum((_chf(a["charge"].get("amount_chf"))
                                       for a in attempts if a.get("charge")), Decimal(0))),
    }


def summarize(manifest: Mapping[str, Any], verification: Verification,
              records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Run-level and per-trial measures computed from the saved records only.

    The primary score keeps the full planned denominator: a trial without a record, or whose
    grades are pending or unreliable, counts as not successful rather than being dropped."""
    planned = len(manifest["planned"])
    trials: dict[str, dict[str, float]] = {}
    totals: dict[str, float] = {}
    labels: dict[str, int] = {}
    checks_total = checks_passed = edge_total = edge_passed = 0
    successes = graded = unreliable = 0
    for trial_id, record in records.items():
        grades = record.get("grades") or {}
        calls, attempts = record.get("model_calls", 0), record.get("tool_attempts", 0)
        entry: dict[str, float] = {"model_calls": calls, "tool_attempts": attempts}
        totals["model_calls"] = totals.get("model_calls", 0) + calls
        totals["tool_attempts"] = totals.get("tool_attempts", 0) + attempts
        for key, value in (record.get("usage") or {}).items():
            if _numeric(value):
                totals["usage." + key] = totals.get("usage." + key, 0) + value
        for key, value in attempt_measures(record).items():
            entry[key] = value
            totals["attempt." + key] = totals.get("attempt." + key, 0) + value
        if grades.get("status") == GRADE_GRADED:
            graded += 1
            checks = grades.get("checks", [])
            entry["success"] = float(bool(grades.get("success")))
            entry["checks_passed"] = sum(bool(c["passed"]) for c in checks)
            entry["checks_total"] = len(checks)
            successes += bool(grades.get("success"))
            checks_total += len(checks)
            checks_passed += entry["checks_passed"]
            for check in checks:
                if check.get("kind") == "edge":
                    edge_total += 1
                    edge_passed += bool(check["passed"])
            for label in grades.get("labels", []):
                labels[label] = labels.get(label, 0) + 1
        elif grades.get("status") != GRADE_PENDING:
            unreliable += 1
        trials[trial_id] = entry
    run: dict[str, float] = {
        "trials_planned": planned, "trials_recorded": len(records), "trials_graded": graded,
        "trials_grades_pending": len(verification.grades_pending),
        "trials_grading_incomplete": unreliable, "trials_successful": successes,
        "success_rate": successes / planned if planned else 0.0,
        "checks_total": checks_total, "checks_passed": checks_passed,
        "check_pass_rate": checks_passed / checks_total if checks_total else 0.0,
        "edge_checks_total": edge_total, "edge_checks_passed": edge_passed,
        "run_complete": float(verification.complete),
        **{_safe(k): v for k, v in totals.items()},
        **{_safe("label." + k): v for k, v in labels.items()},
    }
    return {"run": run, "trials": trials}


def is_headline(verification: Verification) -> bool:
    """Only a complete, fully graded run is a candidate for a headline comparison."""
    return verification.complete and not verification.grades_pending


# --- trial traces -----------------------------------------------------------------------

def _tool_exchange(record: Mapping[str, Any], call: int, executed: str | None
                   ) -> tuple[Any, Any]:
    """The `run_checks` arguments the model sent and the feedback it got back."""
    responses = record.get("responses", [])
    arguments = None
    if executed and call - 1 < len(responses):
        for tool_call in responses[call - 1].get("tool_calls") or []:
            if tool_call.get("id") == executed:
                arguments = tool_call.get("arguments")
    feedback = next((m.get("content") for m in record.get("messages", [])
                     if m.get("role") == "tool" and m.get("tool_call_id") == executed), None)
    return arguments, feedback


def _attempt_entries(record: Mapping[str, Any]) -> dict[int, list[dict[str, Any]]]:
    """Physical attempts/retries per logical call, as the OpenRouter client records them
    (`call`, `retry_index`, `started_at`, `latency_ms`, `reservation`, `charge`, ...)."""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for entry in record.get("attempts") or []:
        if isinstance(entry, dict) and isinstance(entry.get("call"), int):
            grouped.setdefault(entry["call"], []).append(entry)
    return grouped


def _ns(stamp: Any) -> int | None:
    """Nanoseconds since the epoch for an ISO timestamp from the bundle, else None."""
    try:
        return int(datetime.fromisoformat(str(stamp)).timestamp() * 1e9)
    except (TypeError, ValueError):
        return None


def _attempt_window(attempt: Mapping[str, Any]) -> tuple[int | None, int | None]:
    """(start, end) of one physical attempt. The end is the start plus the measured latency
    because the stored timestamps have one-second resolution."""
    start = _ns(attempt.get("started_at")) or _ns(attempt.get("at"))
    latency = attempt.get("latency_ms")
    if start is not None and isinstance(latency, int):
        return start, start + latency * 1_000_000
    return start, _ns(attempt.get("ended_at")) or start


def _attempt_attributes(attempt: Mapping[str, Any]) -> dict[str, Any]:
    """Scalar view of an attempt record: nested dicts become dotted keys, lists become JSON,
    empty values are dropped. The client records no credential, and the whole record is
    passed through redaction before it reaches this function."""
    out: dict[str, Any] = {}

    def add(prefix: str, value: Any) -> None:
        if isinstance(value, Mapping):
            for key, inner in value.items():
                add(f"{prefix}.{key}" if prefix else str(key), inner)
        elif isinstance(value, (list, tuple)):
            if value:
                out[prefix] = json.dumps(list(value))
        elif value is not None:
            out[prefix] = value

    add("", attempt)
    return out


def write_trial_trace(client: Any, experiment_id: str, run_id: str, record: Mapping[str, Any],
                      tags: Mapping[str, str]) -> str:
    """One trace per trial: model-call, physical-attempt, run_checks, and submission spans.

    Only interaction content is used (requests, responses, tool exchange, final outcome).
    Grades, hidden case outcomes, and expected values are never read here. Physical attempts
    (including transport retries) become child spans of their logical model call, with the
    client's recorded usage, cost, reservation, latency, and error class as attributes.
    Attempt and model-call spans carry the recorded start time and measured latency; spans
    without a recorded time (tool calls, submission) sit at the end of the preceding model
    call. A bundle without attempt records (a fixture client) has only upload-time spans,
    where order is the evidence."""
    all_attempts = [a for group in _attempt_entries(record).values() for a in group]
    windows = [_attempt_window(a) for a in all_attempts]
    starts = [w[0] for w in windows if w[0] is not None]
    ends = [w[1] for w in windows if w[1] is not None]
    cursor: int | None = min(starts) if starts else None  # latest recorded time seen so far
    trial_id = record["trial_id"]
    root = client.start_trace(
        name=f"trial {trial_id}", span_type="AGENT", experiment_id=experiment_id, run_id=run_id,
        inputs={"task_id": record["task_id"], "prompt": record.get("prompt")},
        attributes={"trial_id": trial_id, "task_id": record["task_id"],
                    "agent_limits_hash": record.get("agent_limits_hash")},
        tags=dict(tags), start_time_ns=cursor)
    trace_id = root.trace_id
    requests, responses = record.get("requests", []), record.get("responses", [])
    attempts = _attempt_entries(record)
    step = 0
    for event in record.get("events", []):
        kind = event.get("event")
        step += 1
        if kind == "model_call":
            call = event["call"]
            call_windows = [_attempt_window(a) for a in attempts.get(call, [])]
            call_start = next((w[0] for w in call_windows if w[0] is not None), cursor)
            call_end = max((w[1] for w in call_windows if w[1] is not None), default=call_start)
            span = client.start_span(
                name=f"model_call {call}", trace_id=trace_id, parent_id=root.span_id,
                span_type="CHAT_MODEL", attributes={"step": step},
                inputs=requests[call - 1] if call - 1 < len(requests) else None,
                start_time_ns=call_start)
            for index, (attempt, (a_start, a_end)) in enumerate(
                    zip(attempts.get(call, []), call_windows), 1):
                child = client.start_span(
                    name=f"attempt {index}", trace_id=trace_id, parent_id=span.span_id,
                    span_type="LLM", inputs=None, attributes=_attempt_attributes(attempt),
                    start_time_ns=a_start)
                client.end_span(trace_id, child.span_id, end_time_ns=a_end,
                                status="ERROR" if attempt.get("error_class") else "OK")
            cursor = call_end if call_end is not None else cursor
            client.end_span(
                trace_id, span.span_id, end_time_ns=call_end,
                outputs=responses[call - 1] if call - 1 < len(responses) else None,
                attributes={"tools_enabled": event.get("tools_enabled"),
                            "outcome": event.get("outcome"), "truncated": event.get("truncated"),
                            "usage": event.get("usage"), "detail": event.get("detail")},
                status="ERROR" if event.get("detail") else "OK")
        elif kind == "tool_attempt":
            call = next((e["call"] for e in reversed(record["events"][:step])
                         if e.get("event") == "model_call"), 0)
            arguments, feedback = _tool_exchange(record, call, event.get("executed"))
            span = client.start_span(
                name=f"run_checks attempt {event['attempt']}", trace_id=trace_id,
                parent_id=root.span_id, span_type="TOOL", inputs=arguments,
                attributes={"step": step, "calls_in_response": event.get("calls_in_response"),
                            "rejected_extras": event.get("rejected_extras")},
                start_time_ns=cursor)
            client.end_span(trace_id, span.span_id, outputs=feedback, end_time_ns=cursor)
        elif kind == "contract_failure":
            span = client.start_span(name="contract_failure", trace_id=trace_id,
                                     parent_id=root.span_id, span_type="UNKNOWN",
                                     attributes={"step": step, "code": event.get("code")},
                                     start_time_ns=cursor)
            client.end_span(trace_id, span.span_id, status="ERROR", end_time_ns=cursor)
    submission = client.start_span(
        name="submission", trace_id=trace_id, parent_id=root.span_id, span_type="CHAIN",
        attributes={"step": step + 1}, start_time_ns=cursor)
    final = record.get("final_source")
    client.end_span(trace_id, submission.span_id, outputs={
        "final_source": final, "submitted": final is not None and record.get("status") == "submitted",
        "status": record.get("status"), "label": record.get("label"),
        "infrastructure_status": record.get("infrastructure_status"),
        "contract_issue": record.get("contract_issue")}, end_time_ns=cursor)
    client.end_trace(trace_id, outputs={"status": record.get("status"), "label": record.get("label")},
                     attributes={"model_calls": record.get("model_calls"),
                                 "tool_attempts": record.get("tool_attempts"),
                                 "usage": record.get("usage"),
                                 "attempts": len(all_attempts),
                                 "reservation": record.get("reservation"),
                                 "latency_ms": record.get("latency_ms")},
                     status="ERROR" if record.get("infrastructure_status") else "OK",
                     end_time_ns=max(ends) if ends else None)
    return trace_id


# --- connection, lookup, and upload -----------------------------------------------------

def _tracking_errors() -> tuple[type[BaseException], ...]:
    """Failures that mean the service (or the connection to it) is the problem. Anything
    else, such as a bug in the mapping code, is not reported as an outage."""
    import requests
    from mlflow.exceptions import MlflowException
    return (MlflowException, requests.RequestException, OSError)


def _preflight(tracking_uri: str, timeout: float = 3.0) -> None:
    """Fail fast when an HTTP tracking server is down (MLflow's own retries take minutes)."""
    if not tracking_uri.startswith(("http://", "https://")):
        return
    try:
        with urllib.request.urlopen(tracking_uri.rstrip("/") + "/health", timeout=timeout):
            return
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise TrackingUnavailable(f"tracking service not reachable at {tracking_uri}: {error}") \
            from error


def make_client(tracking_uri: str) -> Any:
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    os.environ.setdefault("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")  # fail inside the call
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "30")
    _preflight(tracking_uri)
    import mlflow  # imported late: bundles can be read without MLflow
    # The trace exporter follows the global URI, not the client's: without this, traces
    # would be sent to ./mlruns (or fail with only a log warning) instead of the target.
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.MlflowClient(tracking_uri=tracking_uri)


def _experiment_id(client: Any, name: str) -> str:
    experiment = client.get_experiment_by_name(name)
    return experiment.experiment_id if experiment else client.create_experiment(name)


def _find_run(client: Any, experiment_id: str, filters: Mapping[str, str]) -> list[Any]:
    clause = " and ".join(f"tags.`{TAG}{k}` = '{v}'" for k, v in filters.items())
    return list(client.search_runs([experiment_id], clause, max_results=50))


def _log_params_tags(client: Any, run_id: str, params: Mapping[str, str],
                     tags: Mapping[str, str]) -> None:
    from mlflow.entities import Param, RunTag
    items = [("p", Param(k, v)) for k, v in params.items()] + \
            [("t", RunTag(k, v)) for k, v in tags.items()]
    for start in range(0, len(items), _BATCH):
        chunk = items[start:start + _BATCH]
        client.log_batch(run_id, params=[x for k, x in chunk if k == "p"],
                         tags=[x for k, x in chunk if k == "t"])


def _log_metrics(client: Any, run_id: str, metrics: Mapping[str, float]) -> None:
    from mlflow.entities import Metric
    stamp = int(time.time() * 1000)
    items = [Metric(_safe(k), float(v), stamp, 0) for k, v in metrics.items()]
    for start in range(0, len(items), 900):
        client.log_batch(run_id, metrics=items[start:start + 900])


def _stage(directory: Path, name: str, data: Any, secrets: Sequence[str]) -> int:
    clean, count = redact_value(data, secrets)
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=2, sort_keys=True), encoding="utf-8")
    return count


def _stage_partial_calls(stage: Path, bundle_dir: Path, secrets: Sequence[str]) -> int:
    """Retained request/response entries of trials that never got a record (paid evidence
    of an interrupted run), redacted line by line."""
    count = 0
    for file in sorted((bundle_dir / "trials").glob("*.calls.jsonl")):
        lines = []
        for line in file.read_text(encoding="utf-8").splitlines():
            try:
                clean, c = redact_value(json.loads(line), secrets)
            except ValueError:
                clean, c = {"unreadable_line": True}, 0
            count += c
            lines.append(json.dumps(clean, sort_keys=True))
        target = stage / "trials" / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def _delete_partial(client: Any, experiment_id: str, run_id: str) -> None:
    traces = client.search_traces(locations=[experiment_id], run_id=run_id, include_spans=False,
                                  max_results=1000)
    ids = [t.info.trace_id for t in traces]
    if ids:
        client.delete_traces(experiment_id, trace_ids=ids)
    client.delete_run(run_id)


def record_bundle(bundle_dir: str | Path, tracking_uri: str = DEFAULT_TRACKING_URI, *,
                  experiment: str = DEFAULT_EXPERIMENT, client: Any = None,
                  extra_secrets: Sequence[str] = ()) -> RecordResult:
    """Upload one retained bundle (and its grading replays) as an MLflow run with traces."""
    path = Path(bundle_dir)
    verification = verify_bundle(path)
    blocking = [p for p in verification.problems if p.kind in _BLOCKING]
    if blocking:
        raise BundleError("bundle cannot be recorded: " + "; ".join(
            f"{p.kind}{' ' + p.trial_id if p.trial_id else ''}: {p.detail}" for p in blocking))
    manifest = load_manifest(path)
    digest = verification.bundle_digest
    try:
        client = client or make_client(tracking_uri)
        experiment_id = _experiment_id(client, experiment)
        existing = _find_run(client, experiment_id, {"record_kind": KIND_BUNDLE,
                                                     "bundle_digest": digest})
        done = [r for r in existing if r.data.tags.get(UPLOAD_COMPLETE) == "true"]
        if done:
            run_id = done[0].info.run_id
            created, redactions = False, 0
        else:
            for partial in existing:  # an interrupted upload: rebuild it from the bundle
                _delete_partial(client, experiment_id, partial.info.run_id)
            run_id, redactions = _upload(client, experiment_id, path, manifest, verification,
                                         digest, extra_secrets)
            created = True
        replays = _record_replays(client, experiment_id, path, manifest["run_id"], digest, run_id,
                                  extra_secrets)
        all_replays = sorted(
            r.data.tags[TAG + "replay_id"]
            for r in _find_run(client, experiment_id, {"record_kind": KIND_REPLAY,
                                                       "bundle_digest": digest})
            if r.data.tags.get(UPLOAD_COMPLETE) == "true")
    except TrackingUnavailable:
        raise
    except _tracking_errors() as error:
        raise TrackingUnavailable(f"tracking call failed: {type(error).__name__}: {error}") from error
    result = RecordResult(run_id, created, tuple(replays), redactions)
    write_sidecar(path, {"status": "recorded", "tracking_uri": tracking_uri,
                         "experiment": experiment, "mlflow_run_id": run_id,
                         "bundle_digest": digest, "recorded_at": utc_now(),
                         "replays": all_replays})
    return result


def _upload(client: Any, experiment_id: str, path: Path, manifest: Mapping[str, Any],
            verification: Verification, digest: str, extra_secrets: Sequence[str]
            ) -> tuple[str, int]:
    secrets = secret_values(extra_secrets)
    records = {t: load_trial(path, t) for t in verification.recorded}
    summary = summarize(manifest, verification, records)
    identity = manifest["identity"]
    tags = {
        TAG + "record_kind": KIND_BUNDLE, TAG + "bundle_run_id": manifest["run_id"],
        TAG + "bundle_digest": digest, TAG + "bundle_status": manifest.get("status", "?"),
        TAG + "run_complete": str(verification.complete).lower(),
        TAG + "headline_candidate": str(is_headline(verification)).lower(),
        TAG + "benchmark_version": str(identity.get("benchmark", {}).get("version")),
        TAG + "benchmark_sha256": str(identity.get("benchmark", {}).get("sha256")),
        TAG + "prompt_version": str(identity.get("prompt", {}).get("version")),
        TAG + "prompt_sha256": str(identity.get("prompt", {}).get("sha256")),
        TAG + "evaluator_revision": str(identity.get("evaluator_revision")),
        TAG + "missing_trials": ",".join(verification.missing()) or "none",
        TAG + "problems": ",".join(sorted({p.kind for p in verification.problems})) or "none",
        "mlflow.note.content": ("Recorded from a retained local bundle; "
                               "the bundle is the primary evidence."),
    }
    redacted_tags, count = redact_value(tags, secrets)
    run = client.create_run(experiment_id, run_name=manifest["run_id"], tags=redacted_tags)
    run_id = run.info.run_id
    try:
        params, c = redact_value(parameters(manifest), secrets)
        count += c
        _log_params_tags(client, run_id, params, {})
        _log_metrics(client, run_id, summary["run"])
        _log_metrics(client, run_id, {f"trial/{t}/{k}": v for t, m in summary["trials"].items()
                                      for k, v in m.items()})
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            count += _stage(stage, "manifest.json", manifest, secrets)
            count += _stage(stage, "summary.json", summary, secrets)
            count += _stage(stage, "verification.json", [
                {"kind": p.kind, "trial_id": p.trial_id, "detail": p.detail}
                for p in verification.problems], secrets)
            count += _stage_partial_calls(stage, path, secrets)
            for trial_id, record in records.items():
                count += _stage(stage, f"trials/{trial_id}.json", record, secrets)
                count += _stage(stage, f"grading/{trial_id}.json",
                                {"trial_id": trial_id, "grades": record.get("grades")}, secrets)
            client.log_artifacts(run_id, str(stage), "bundle")
        trace_tags = {TAG + "bundle_run_id": manifest["run_id"], TAG + "bundle_digest": digest}
        for trial_id, record in records.items():
            clean, c = redact_value(record, secrets)
            count += c
            write_trial_trace(client, experiment_id, run_id, clean,
                              {**trace_tags, TAG + "trial_id": trial_id,
                               TAG + "task_id": record["task_id"]})
        stored = client.search_traces(locations=[experiment_id], run_id=run_id, include_spans=False,
                                      max_results=len(records) + 1)
        if len(stored) != len(records):  # the exporter only logs a warning when it fails
            raise TrackingUnavailable(f"only {len(stored)} of {len(records)} trial traces "
                                      "were stored")
        client.set_tag(run_id, TAG + "redactions_at_upload", str(count))
        client.set_tag(run_id, UPLOAD_COMPLETE, "true")
        client.set_terminated(run_id, "FINISHED")
    except BaseException:
        try:
            client.set_terminated(run_id, "FAILED")
        except Exception:  # noqa: BLE001 - keep the original error, not one from cleanup
            pass
        raise
    return run_id, count


def _record_replays(client: Any, experiment_id: str, path: Path, bundle_run: str, digest: str,
                    parent_run_id: str, extra_secrets: Sequence[str]) -> list[str]:
    """Each saved grading replay becomes its own run, nested under (linked to) the original.

    It carries grading evidence only: no trace, and never a new agent trial."""
    recorded: list[str] = []
    secrets = secret_values(extra_secrets)
    for file in sorted((path / "replays").glob("*.json")):
        evidence = read_json(file)
        replay_id = _check_id(str(evidence.get("replay_id", file.stem)), "replay id")
        existing = _find_run(client, experiment_id, {"record_kind": KIND_REPLAY,
                                                     "replay_id": replay_id,
                                                     "bundle_digest": digest})
        if any(r.data.tags.get(UPLOAD_COMPLETE) == "true" for r in existing):
            continue
        for partial in existing:
            client.delete_run(partial.info.run_id)
        summary = evidence.get("summary", {})
        run = client.create_run(experiment_id, run_name=replay_id, tags={
            "mlflow.parentRunId": parent_run_id, TAG + "record_kind": KIND_REPLAY,
            TAG + "replay_id": replay_id, TAG + "bundle_run_id": bundle_run,
            TAG + "bundle_digest": digest,
            TAG + "linked_manifest_sha256": str(evidence.get("linked_manifest_sha256")),
            TAG + "linked_manifest_matches_bundle":
                str(evidence.get("linked_manifest_sha256") == digest).lower(),
            TAG + "headline_candidate": "false", TAG + "agent_trial": "false",
            TAG + "evaluator_revision": str(evidence.get("evaluator_revision")),
            "mlflow.note.content": evidence.get("note", "")})
        run_id = run.info.run_id
        _log_params_tags(client, run_id, {
            "container_image": str(evidence.get("container_image")),
            "benchmark_sha256": str(evidence.get("benchmark_sha256")),
            "execution_limits_hash": str(evidence.get("execution_limits_hash"))}, {})
        _log_metrics(client, run_id, {f"replay_{k}": v for k, v in summary.items() if _numeric(v)})
        with tempfile.TemporaryDirectory() as tmp:
            _stage(Path(tmp), "replay.json", evidence, secrets)
            client.log_artifacts(run_id, tmp, "replay")
        client.set_tag(run_id, UPLOAD_COMPLETE, "true")
        client.set_terminated(run_id, "FINISHED")
        recorded.append(replay_id)
    return recorded


# --- sidecar status ---------------------------------------------------------------------

def write_sidecar(bundle_dir: Path, data: Mapping[str, Any]) -> None:
    atomic_write(bundle_dir / SIDECAR, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode())


def read_sidecar(bundle_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((bundle_dir / SIDECAR).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"status": "unreadable"}
    except FileNotFoundError:
        return {"status": "not_recorded"}
    except (OSError, ValueError):
        return {"status": "unreadable"}


def bundle_recorder(tracking_uri: str | None = None, *, experiment: str | None = None,
                    client: Any = None) -> Any:
    """A `record_run(bundle, label) -> str` hook for runners (the experiment runner's).

    The verified bundle is recorded once (re-recording changes nothing). If the service is
    down, the client is not installed, or the bundle cannot be recorded, the hook keeps the
    outage marker (`tracking.json`, status `not_recorded`) for a later
    `python -m codegen_eval.mlflow_tracking record <run>` and returns a message; it never
    raises, blocks, or regenerates anything, and needs no model call or credential."""
    def record(bundle: str | Path, label: str = "") -> str:
        path = Path(bundle)
        uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)
        try:
            result = record_bundle(path, uri, experiment=experiment or DEFAULT_EXPERIMENT,
                                   client=client)
        except (TrackingUnavailable, ImportError, BundleError) as error:
            reason = ("MLflow client not installed (uv sync --group tracking)"
                      if isinstance(error, ImportError) else str(error))
            write_sidecar(path, {"status": "not_recorded", "tracking_uri": uri,
                                 "last_error": reason, "last_attempt_at": utc_now()})
            return (f"not recorded: {reason}; upload later with: "
                    f"python -m codegen_eval.mlflow_tracking record {path}")
        return f"recorded: MLflow run {result.run_id} at {uri}"
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record retained run bundles in local MLflow "
                                                 "(no model API, no credentials).")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="upload one bundle (idempotent)")
    rec.add_argument("run", help="run id under --bundles, or a bundle directory")
    for p in (rec, sub.add_parser("status", help="show recorded / not-recorded per bundle")):
        p.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    rec.add_argument("--tracking-uri", default=os.environ.get("MLFLOW_TRACKING_URI",
                                                              DEFAULT_TRACKING_URI),
                     help="default: $MLFLOW_TRACKING_URI if set, else " + DEFAULT_TRACKING_URI)
    rec.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    args = parser.parse_args(argv)

    if args.command == "status":
        for bundle in list_runs(args.bundles):
            side = read_sidecar(bundle)
            print(f"{bundle.name}: {side['status']}"
                  + (f" (MLflow run {side['mlflow_run_id']})" if side.get("mlflow_run_id") else ""))
        return 0
    try:
        path = resolve_bundle(args.bundles, args.run)
        result = record_bundle(path, args.tracking_uri, experiment=args.experiment)
    except BundleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except TrackingUnavailable as error:
        write_sidecar(resolve_bundle(args.bundles, args.run),
                      {"status": "not_recorded", "tracking_uri": args.tracking_uri,
                       "last_error": str(error), "last_attempt_at": utc_now()})
        print(f"not yet recorded: {error}\nThe bundle is unchanged; rerun this command when "
              f"the service is up. No model call is made.", file=sys.stderr)
        return 3
    print(("recorded" if result.created else "already recorded (unchanged)")
          + f": MLflow run {result.run_id} at {args.tracking_uri}")
    for replay in result.replays:
        print(f"  grading replay recorded: {replay}")
    if result.redactions:
        print(f"  note: {result.redactions} secret value(s) redacted at upload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
