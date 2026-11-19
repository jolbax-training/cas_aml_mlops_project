"""Offline analysis of the at-scale prompt comparison (baseline, revised, baseline repeat).

Reads retained bundles only: no model client, no sandbox, no ledger, no network, and it writes
nothing. For each run it reports the metrics of `experiment_cli compare`, the successes out of
n per task, a Wilson 95% interval for the overall success rate and the charged CHF; for the
pairs baseline/revised and baseline/repeat it reports the differences. The intervals are
descriptive: no significance claim is computed, and interval overlap is not a test.

    python -m codegen_eval.scale_analysis --config experiments/prompt_comparison_v2.json \\
        --bundles RUN_BUNDLES_V2 --baseline RUN_1 [--revised RUN_2] [--repeat RUN_3] [--json]

Exit status 3 when the charged CHF summed over the given runs exceeds `--charged-limit-chf`
(the coordinator's stop rule between runs)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from codegen_eval.bundle import DEFAULT_BUNDLE_ROOT, BundleError, load_manifest, resolve_bundle
from codegen_eval.comparison import _identity_differences, variant_metrics
from codegen_eval.experiment import (
    BASELINE, DEFAULT_BENCHMARK, DEFAULT_CONFIG, REVISED, ExperimentConfig, ExperimentError,
    load_config, verify_schedule,
)
from codegen_eval.summary import summarize_bundle

Z_95 = 1.959964
CHARGED_LIMIT_CHF = "1"
EXIT_OVER_LIMIT = 3
# (name, first run, second run); differences are second minus first.
PAIRS = (("baseline_vs_revised", "baseline", "revised"),
         ("baseline_vs_repeat", "baseline", "repeat"))
VARIANT_OF = {"baseline": BASELINE, "revised": REVISED, "repeat": BASELINE}


def wilson_interval(successes: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for `successes` of `total`, to four decimals, clamped to [0, 1]."""
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError(f"need 0 <= successes <= total and total > 0, got {successes} of {total}")
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def charged_total(runs: Mapping[str, Mapping[str, Any]]) -> Decimal:
    """Charged CHF summed over the runs; a run with no charge records counts as zero."""
    return sum((Decimal(str(run["charged_chf"])) for run in runs.values()
                if run["charged_chf"] is not None), Decimal(0))


def analyse_run(label: str, bundle: Path, benchmark_path: str | Path,
                config: ExperimentConfig) -> dict[str, Any]:
    variant = VARIANT_OF[label]
    summary = summarize_bundle(bundle, benchmark_path)
    schedule = verify_schedule(bundle, config, variant)
    manifest = load_manifest(bundle)
    metrics = variant_metrics(bundle, summary)
    metrics["headline_eligible"] = summary.headline_eligible and schedule.ok
    primary = metrics["primary"]
    low, high = wilson_interval(primary["count"], primary["of"]) if primary["of"] else (None, None)
    charged = metrics["cost"]["charged_chf"]
    return {
        "label": label, "variant": variant, "run_id": manifest.get("run_id"), "bundle": str(bundle),
        "started_at": manifest.get("started_at"),
        "prompt": manifest.get("identity", {}).get("prompt"),
        "headline_eligible": metrics["headline_eligible"],
        "schedule_problems": list(schedule.problems),
        "primary": primary,
        "wilson_95": {"lower": low, "upper": high, "method": "wilson", "z": Z_95,
                      "note": "trials treated as independent"},
        "per_task": {task: {"succeeded": v["succeeded"], "trials": v["trials"]}
                     for task, v in metrics["per_task"].items()},
        "charged_chf": None if charged is None else round(charged, 8),
        "metrics": metrics,
        "identity": manifest.get("identity", {}),
    }


def compare_pair(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    """Second minus first, under the rules of `compare_runs`; a pair that differs in more than
    the intended prompt, or that includes a run that is not headline-eligible, has no
    difference computed."""
    reasons, caveats = _identity_differences(first["identity"], second["identity"])
    if first["variant"] == second["variant"] and first["prompt"] != second["prompt"]:
        reasons.append("the two runs are meant to use the same prompt but record different prompts")
    for run in (first, second):
        if not run["headline_eligible"]:
            reasons.append(f"the {run['label']} run is not headline-eligible (incomplete, "
                           "ungraded, or not matching the schedule)")
    result: dict[str, Any] = {"first": first["label"], "second": second["label"],
                              "comparable": not reasons, "reasons": reasons, "caveats": caveats,
                              "delta": None}
    if reasons:
        return result
    tasks = {t: (first["per_task"][t]["succeeded"], second["per_task"][t]["succeeded"])
             for t in first["per_task"]}
    low1, high1 = first["wilson_95"]["lower"], first["wilson_95"]["upper"]
    low2, high2 = second["wilson_95"]["lower"], second["wilson_95"]["upper"]
    result["delta"] = {
        "primary_successes": second["primary"]["count"] - first["primary"]["count"],
        "primary_rate": round(second["primary"]["rate"] - first["primary"]["rate"], 6),
        "gained_tasks": sorted(t for t, (a, b) in tasks.items() if b > a),
        "regressed_tasks": sorted(t for t, (a, b) in tasks.items() if b < a),
        "unchanged_tasks": sorted(t for t, (a, b) in tasks.items() if b == a),
        "per_task": {t: {"first": a, "second": b} for t, (a, b) in sorted(tasks.items())},
        "intervals_overlap": low1 <= high2 and low2 <= high1,
        "interval_note": "overlap is a descriptive aid, not a test",
    }
    return result


def analyse(config: ExperimentConfig, bundles: str | Path, runs: Mapping[str, str],
            benchmark_path: str | Path = DEFAULT_BENCHMARK,
            charged_limit_chf: str | Decimal = CHARGED_LIMIT_CHF) -> dict[str, Any]:
    """`runs` maps a label (baseline, revised, repeat) to a run id under `bundles`."""
    analysed = {label: analyse_run(label, resolve_bundle(bundles, run), benchmark_path, config)
                for label, run in runs.items()}
    pairs = {name: compare_pair(analysed[a], analysed[b]) for name, a, b in PAIRS
             if a in analysed and b in analysed}
    total = charged_total(analysed)
    limit = Decimal(charged_limit_chf)
    for run in analysed.values():
        del run["identity"]
    return {"experiment_id": config.experiment_id, "runs": analysed, "pairs": pairs,
            "charged_chf_total": str(total),
            "charged_limit_chf": str(limit), "charged_limit_exceeded": total > limit}


def _fmt(ratio: Mapping[str, Any]) -> str:
    rate = "n/a" if ratio["rate"] is None else f"{ratio['rate']:.1%}"
    return f"{ratio['count']}/{ratio['of']} ({rate})"


def render(result: Mapping[str, Any]) -> str:
    lines = [f"experiment {result['experiment_id']}: at-scale analysis (descriptive; no significance claim)"]
    for run in result["runs"].values():
        m, w = run["metrics"], run["wilson_95"]
        lines += [f"{run['label']} ({run['variant']}): run {run['run_id']} prompt "
                  f"{(run['prompt'] or {}).get('version')}"
                  + ("" if run["headline_eligible"] else "  [NOT headline-eligible]"),
                  f"  primary: {_fmt(run['primary'])}; Wilson 95% interval "
                  f"[{w['lower']}, {w['upper']}] (trials treated as independent)",
                  "  per task: " + ", ".join(f"{t} {v['succeeded']}/{v['trials']}"
                                             for t, v in run["per_task"].items()),
                  f"  hidden checks: {_fmt(m['hidden_checks'])}; edge cases: {_fmt(m['edge_cases'])}; "
                  f"tasks passing every trial: {_fmt(m['tasks_passing_every_trial'])}",
                  f"  failure labels: {m['failure_labels'] or 'none'}",
                  f"  model calls {m['model_calls']}, tool attempts {m['tool_attempts']}, "
                  f"revisions {m['revisions']}; tokens {m['tokens']}",
                  f"  charged CHF {run['charged_chf']}; cost {m['cost']}"]
        for problem in run["schedule_problems"]:
            lines.append(f"  schedule: {problem}")
    for name, pair in result["pairs"].items():
        lines.append(f"{name} ({pair['second']} - {pair['first']}): "
                     + ("comparable" if pair["comparable"] else "NOT comparable"))
        lines += [f"  - {reason}" for reason in pair["reasons"]]
        lines += [f"  note: {caveat}" for caveat in pair["caveats"]]
        if pair["delta"]:
            d = pair["delta"]
            lines += [f"  difference: {d['primary_successes']:+d} successful trials "
                      f"({d['primary_rate']:+.1%}); intervals overlap: {d['intervals_overlap']} "
                      "(descriptive aid, not a test)",
                      f"  gained tasks: {d['gained_tasks'] or 'none'}; "
                      f"regressed tasks: {d['regressed_tasks'] or 'none'}; "
                      f"unchanged: {len(d['unchanged_tasks'])}"]
    lines.append(f"charged CHF over these runs: {result['charged_chf_total']} "
                 f"(limit CHF {result['charged_limit_chf']}: "
                 + ("EXCEEDED, stop and ask the user" if result["charged_limit_exceeded"]
                    else "not exceeded") + ")")
    return "\n".join(lines)


def _decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except ArithmeticError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline analysis of the at-scale prompt comparison.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--baseline", required=True, help="run id of the first baseline run")
    parser.add_argument("--revised", help="run id of the revised run")
    parser.add_argument("--repeat", help="run id of the baseline repeat")
    parser.add_argument("--charged-limit-chf", type=_decimal, default=Decimal(CHARGED_LIMIT_CHF))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    runs = {label: run for label, run in (("baseline", args.baseline), ("revised", args.revised),
                                          ("repeat", args.repeat)) if run}
    try:
        result = analyse(load_config(args.config), args.bundles, runs, args.benchmark,
                         args.charged_limit_chf)
    except (ExperimentError, BundleError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else render(result))
    return EXIT_OVER_LIMIT if result["charged_limit_exceeded"] else 0


if __name__ == "__main__":
    sys.exit(main())
