"""Primary metric and diagnostics for the two variants of the prompt comparison (task 4.1 tooling).

This computes counts and rates from retained bundles; it writes no conclusions. A variant is
headline-eligible only if its run is complete against the schedule and every trial is graded,
and the pair is comparable only if nothing but the prompt differs. Otherwise the figures are
still reported, labelled as not headline, and no difference between the variants is computed:
denominators are the planned ones either way."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from codegen_eval.bundle import BundleError, load_manifest, load_trial
from codegen_eval.experiment import BASELINE, REVISED, ExperimentConfig, verify_schedule
from codegen_eval.summary import RunSummary, summarize_bundle

# Identity sections that legitimately differ between the variants. Everything else recorded
# (benchmark, limits, evaluator, container image, model settings, dependencies) must match.
VARIANT_SECTIONS = ("prompt", "experiment")
SAME_EXPERIMENT_FIELDS = ("experiment_id", "config_sha256", "schedule_sha256", "trial_order",
                          "settings_hash")


def _ratio(count: int, total: int) -> dict[str, Any]:
    return {"count": count, "of": total, "rate": count / total if total else None}


def _sum(values: list[float | int]) -> float | int | None:
    return sum(values) if values else None


def _dev_failed(draft: Mapping[str, Any]) -> bool:
    result = draft.get("result") or {}
    return not result.get("ok") or any(not c.get("passed") for c in result.get("checks", []))


def variant_metrics(bundle_dir: str | Path, summary: RunSummary) -> dict[str, Any]:
    """Counts and rates for one run. Trial-level diagnostics read the intact records; trials
    without a usable record count as planned, unsuccessful, and unmeasured (`trials_measured`)."""
    path = Path(bundle_dir)
    manifest = load_manifest(path)
    planned = manifest["planned"]
    verification = summary.classification.verification
    per_task: dict[str, dict[str, Any]] = {}
    labels: Counter[str] = Counter()
    totals = {"model_calls": 0, "tool_attempts": 0, "revisions": 0, "failed_dev_trials": 0,
              "recovered_trials": 0, "measured": 0}
    latency: list[int] = []
    tokens: dict[str, list[float]] = {"prompt_tokens": [], "completion_tokens": [], "total_tokens": []}
    reported_usd: list[float] = []
    charged_chf: list[float] = []
    reserved_chf: list[float] = []
    attempts = attempts_missing_cost = retries = 0
    for item in planned:
        task = per_task.setdefault(item["task_id"], {"succeeded": 0, "trials": 0, "category": None})
        task["trials"] += 1
        if item["trial_id"] not in verification.recorded:
            continue
        try:
            record = load_trial(path, item["trial_id"])
        except BundleError:
            continue
        grades = record.get("grades") or {}
        graded = grades.get("status") in ("graded", "incomplete")
        success = bool(graded and grades.get("success"))
        task["succeeded"] += success
        if graded:
            labels.update(grades.get("labels", []))
        totals["measured"] += 1
        totals["model_calls"] += record.get("model_calls") or 0
        totals["tool_attempts"] += record.get("tool_attempts") or 0
        drafts = record.get("candidate_history", [])
        totals["revisions"] += max(0, len(drafts) - 1)
        if any(_dev_failed(d) for d in drafts):
            totals["failed_dev_trials"] += 1
            totals["recovered_trials"] += success
        if isinstance(record.get("latency_ms"), int):
            latency.append(record["latency_ms"])
        for key, bucket in tokens.items():
            value = (record.get("usage") or {}).get(key)
            if isinstance(value, (int, float)):
                bucket.append(value)
        for attempt in record.get("attempts", []):
            attempts += 1
            retries += bool(attempt.get("retry_index"))
            cost = attempt.get("reported_cost_usd")
            if isinstance(cost, (int, float)):
                reported_usd.append(cost)
            else:
                attempts_missing_cost += 1
            charge = (attempt.get("charge") or {}).get("amount_chf")
            if charge is not None:
                charged_chf.append(float(charge))
            reservation = (attempt.get("reservation") or {}).get("amount_chf")
            if reservation is not None:
                reserved_chf.append(float(reservation))
    counts = summary.counts
    successes = [t["succeeded"] for t in per_task.values()]
    trials_each = {t["trials"] for t in per_task.values()}
    return {
        "headline_eligible": summary.headline_eligible,
        "primary": _ratio(summary.trials_succeeded, summary.trials_planned),
        "trials_incomplete": summary.trials_incomplete,
        "trials_ungraded": summary.trials_ungraded,
        "hidden_checks": {**_ratio(counts.cases_passed, counts.cases_total),
                          "executed": counts.cases_executed},
        "edge_cases": _ratio(counts.edge_cases_passed, counts.edge_cases_total),
        "categories": {name: _ratio(won, total) for name, (won, total) in sorted(summary.categories.items())},
        "per_task": {task: {"succeeded": v["succeeded"], "trials": v["trials"]}
                     for task, v in sorted(per_task.items())},
        "tasks_passing_at_least_one_trial": _ratio(sum(s >= 1 for s in successes), len(successes)),
        "tasks_passing_every_trial": _ratio(
            sum(v["succeeded"] == v["trials"] for v in per_task.values()), len(per_task)),
        "trials_per_task": sorted(trials_each),
        "failure_labels": dict(sorted(labels.items())),
        "trials_measured": totals["measured"],
        "model_calls": totals["model_calls"],
        "tool_attempts": totals["tool_attempts"],
        "revisions": totals["revisions"],
        "recovery": {"trials_with_failed_development_check": totals["failed_dev_trials"],
                     "of_which_final_success": totals["recovered_trials"]},
        "latency_ms": {"total": _sum(latency), "trials_with_latency": len(latency),
                       "mean_per_trial": (sum(latency) / len(latency)) if latency else None},
        "tokens": {key: _sum(values) for key, values in tokens.items()},
        "attempts": {"physical": attempts, "retries": retries,
                     "without_reported_cost": attempts_missing_cost},
        "cost": {"reported_usd": _sum(reported_usd), "charged_chf": _sum(charged_chf),
                 "reserved_chf": _sum(reserved_chf)},
    }


def _identity_differences(baseline: Mapping[str, Any], revised: Mapping[str, Any]) -> list[str]:
    differences = []
    for key in sorted((set(baseline) | set(revised)) - set(VARIANT_SECTIONS)):
        if baseline.get(key) != revised.get(key):
            differences.append(f"identity section {key!r} differs between the runs")
    left, right = baseline.get("experiment", {}), revised.get("experiment", {})
    for key in SAME_EXPERIMENT_FIELDS:
        if left.get(key) != right.get(key):
            differences.append(f"experiment field {key!r} differs between the runs")
    return differences


def compare_runs(baseline_bundle: str | Path, revised_bundle: str | Path,
                 benchmark_path: str | Path, config: ExperimentConfig) -> dict[str, Any]:
    """Both variants' metrics and, only for a comparable pair of headline-eligible runs,
    their per-task differences. Raises `BundleError` for an unreadable bundle or one whose
    benchmark is not the recorded one (as `summarize_bundle` does)."""
    runs: dict[str, dict[str, Any]] = {}
    identities: dict[str, Mapping[str, Any]] = {}
    for name, bundle in ((BASELINE, baseline_bundle), (REVISED, revised_bundle)):
        summary = summarize_bundle(bundle, benchmark_path)
        schedule = verify_schedule(bundle, config, name)
        manifest = load_manifest(bundle)
        identities[name] = manifest.get("identity", {})
        metrics = variant_metrics(bundle, summary)
        metrics["headline_eligible"] = summary.headline_eligible and schedule.ok
        runs[name] = {
            "run_id": manifest.get("run_id"), "bundle": str(bundle),
            "prompt": identities[name].get("prompt"),
            "classification": {"complete": summary.classification.complete,
                               "classes": list(summary.classification.classes),
                               "infrastructure_statuses": list(summary.classification.infrastructure_statuses)},
            "schedule_complete": schedule.ok, "schedule_problems": list(schedule.problems),
            "metrics": metrics}
    reasons = _identity_differences(identities[BASELINE], identities[REVISED])
    for name, run in runs.items():
        if not run["metrics"]["headline_eligible"]:
            reasons.append(f"the {name} run is not headline-eligible (incomplete, ungraded, or "
                           "not matching the schedule)")
    headline = not reasons
    delta = None
    if headline:
        base, rev = runs[BASELINE]["metrics"], runs[REVISED]["metrics"]
        tasks = {t: (base["per_task"][t]["succeeded"], rev["per_task"][t]["succeeded"])
                 for t in base["per_task"]}
        delta = {
            "primary_successes": rev["primary"]["count"] - base["primary"]["count"],
            "primary_rate": rev["primary"]["rate"] - base["primary"]["rate"],
            "gained_tasks": sorted(t for t, (b, r) in tasks.items() if r > b),
            "regressed_tasks": sorted(t for t, (b, r) in tasks.items() if r < b),
            "unchanged_tasks": sorted(t for t, (b, r) in tasks.items() if r == b),
        }
    return {"experiment_id": config.experiment_id, "headline_comparison": headline,
            "reasons_not_headline": reasons, "runs": runs, "delta": delta}


def _fmt(ratio: Mapping[str, Any]) -> str:
    rate = "n/a" if ratio["rate"] is None else f"{ratio['rate']:.1%}"
    return f"{ratio['count']}/{ratio['of']} ({rate})"


def render_comparison(result: Mapping[str, Any]) -> str:
    """Plain-text report of `compare_runs`; counts always come with their rates."""
    lines = [f"experiment {result['experiment_id']}: "
             + ("headline comparison" if result["headline_comparison"] else "NOT a headline comparison")]
    for reason in result["reasons_not_headline"]:
        lines.append(f"  - {reason}")
    for name in (BASELINE, REVISED):
        run = result["runs"][name]
        m = run["metrics"]
        lines += [f"{name}: run {run['run_id']} prompt {(run['prompt'] or {}).get('version')}",
                  f"  primary (successful task trials / planned): {_fmt(m['primary'])}"
                  f"; incomplete trials {m['trials_incomplete']}, ungraded {m['trials_ungraded']}",
                  f"  hidden checks passed: {_fmt(m['hidden_checks'])}; edge cases: {_fmt(m['edge_cases'])}",
                  f"  tasks passing >=1 trial: {_fmt(m['tasks_passing_at_least_one_trial'])}; "
                  f"every trial: {_fmt(m['tasks_passing_every_trial'])}",
                  "  categories: " + ", ".join(f"{k} {_fmt(v)}" for k, v in m["categories"].items()),
                  f"  failure labels: {m['failure_labels'] or 'none'}",
                  f"  model calls {m['model_calls']}, tool attempts {m['tool_attempts']}, "
                  f"revisions {m['revisions']}, recovery {m['recovery']}",
                  f"  latency ms {m['latency_ms']}; tokens {m['tokens']}",
                  f"  attempts {m['attempts']}; cost {m['cost']}"]
    if result["delta"]:
        d = result["delta"]
        lines += [f"difference (revised - baseline): {d['primary_successes']:+d} successful trials "
                  f"({d['primary_rate']:+.1%})",
                  f"  gained tasks: {d['gained_tasks'] or 'none'}",
                  f"  regressed tasks: {d['regressed_tasks'] or 'none'}",
                  f"  unchanged tasks: {len(d['unchanged_tasks'])}"]
    return "\n".join(lines)
