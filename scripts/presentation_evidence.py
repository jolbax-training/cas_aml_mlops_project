#!/usr/bin/env python3
"""Evidence summary, drift check and manifest for the presentation and the report.

    PYTHONPATH=src .venv/bin/python scripts/presentation_evidence.py collect --bundles run_bundles
    .venv/bin/python scripts/render_charts.py
    .venv/bin/python scripts/presentation_evidence.py manifest
    .venv/bin/python scripts/presentation_evidence.py check              # offline, also in CI
    PYTHONPATH=src .venv/bin/python scripts/presentation_evidence.py check --bundles run_bundles
    .venv/bin/python scripts/presentation_evidence.py check --staleness  # read-only report

`collect` reads the retained bundles read-only through the evaluator's own comparison and bundle
code. Every number in the summary comes from there or from a committed document: a document
value is computed from a verbatim quote by a declared extraction (the table below), never typed.
Nothing here reads the spending ledger; `codegen_eval` is imported lazily, only by `collect` and
`check --bundles`, after the ledger location is redirected to a path that does not exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_charts  # noqa: E402  (sibling script; summary-only, standard library)

SUMMARY_REL = "presentation/evidence/summary.json"
MANIFEST_REL = "presentation/manifest.json"
CHARTS_REL = "presentation/charts"
SCHEMA_VERSION = 1
BASELINE, REVISED = "baseline", "revised"
VARIANTS = (BASELINE, REVISED)
STORY_TASKS = ("lists_02", "strings_01")
BUNDLE_SECTIONS = ("comparison", "efficiency", "stories", "smoke")
HEADLINE = "A trustworthy, reproducible, budget-safe evaluation pipeline for a coding agent"
DATE_PLACEHOLDER = "[DATE: fill in]"
LEDGER_ENV = "CODEGEN_EVAL_LEDGER"
COMPARE_COMMAND = ("PYTHONPATH=src .venv/bin/python -m codegen_eval.experiment_cli compare "
                   "--baseline {baseline} --revised {revised} --bundles <bundles> --json")
VERIFY_COMMAND = ("PYTHONPATH=src .venv/bin/python -m codegen_eval.trace_inspect "
                  "--bundles <bundles> verify {run_id}")

PC = "docs/prompt_comparison.md"
CE = "docs/comparison_evidence.md"
CI = "docs/ci_evidence.md"
PR = "docs/progress.md"


class EvidenceError(Exception):
    """A source, summary, or consistency problem; the message is the diagnostic."""


# --- document-derived values --------------------------------------------------------------

def _entry(field: str, file: str, start: str, pattern: str, *, cell: int | None = None,
           group: int = 1, kind: str = "str", lines: int = 1) -> dict[str, Any]:
    return {"field": field, "file": file, "start": start, "lines": lines, "cell": cell,
            "pattern": pattern, "group": group, "kind": kind}


def _pair(name: str, start: str, pattern: str, *, kind: str = "int", group: int = 1,
          file: str = PC) -> list[dict[str, Any]]:
    return [_entry(f"{name}.{variant}", file, start, pattern, cell=cell, group=group, kind=kind)
            for variant, cell in ((BASELINE, 2), (REVISED, 3))]


WORD_INTS = {"no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10}
PROBE_ASSET_ROWS = ("| Hidden expected answers", "| Credentials, API keys", "| Tracking services",
                    "| Podman control", "| Score integrity")
CATEGORIES = ("dictionaries", "lists", "numeric_logic", "parsing_formatting", "strings")
LIMITS = ("Small n.", "Benchmark-informed tuning.", "Single model and provider.",
          "Fixed sampling, no repeated runs.", "Provider precision not returned.",
          "Evaluator revision differs.", "Benchmark reviewed by models only")
# (key, start of the run's source line or block, lines, per-field cell and pattern)
CI_RUNS = {
    "r1": {"file": PR, "start": "- **First GitHub run (run 41124321745", "lines": 1, "fields": {
        "run": (None, r"run (\d+),", "str"), "commit": (None, r"commit (\w+)\)", "str"),
        "offline": (None, r"`offline` (\w+);", "str")}},
    "r2": {"file": CI, "start": "| [41124321745]", "lines": 1, "fields": {
        "run": (1, r"\[(\d+)\]", "str"), "commit": (2, r"`(\w+)`", "str"),
        "podman": (3, r"`podman` (failed)", "str")}},
    "r3": {"file": CI, "start": "| [41126346781]", "lines": 1, "fields": {
        "run": (1, r"\[(\d+)\]", "str"), "commit": (2, r"`(\w+)`", "str"),
        "podman": (3, r"`podman`: \d+ of \d+ (failed)", "str"),
        "podman_failed": (3, r"(\d+) of \d+ failed", "int"),
        "podman_tests": (3, r"\d+ of (\d+) failed", "int")}},
    "r4": {"file": CI, "start": "| Run | [41128433037]", "lines": 4, "fields": {
        "run": (None, r"\[(\d+)\]", "str"), "commit": (None, r"/ `(\w+)`", "str"),
        "offline": (None, r"`offline` \| (\w+) \|", "str"),
        "podman": (None, r"`podman` \| (\w+):", "str"),
        "podman_tests": (None, r"(\d+) tests", "int")}},
    "r5": {"file": CI, "start": "| [41128978798]", "lines": 1, "fields": {
        "run": (1, r"\[(\d+)\]", "str"), "commit": (2, r"/ `(\w+)`$", "str"),
        "offline": (4, r"(failed|success)", "str"), "podman": (5, r"(failed|success)", "str"),
        "podman_tests": (5, r"(\d+) tests", "int")}},
    "r6": {"file": CI, "start": "| [41128979150]", "lines": 1, "fields": {
        "run": (1, r"\[(\d+)\]", "str"), "commit": (2, r"/ `(\w+)`$", "str"),
        "offline": (4, r"(failed|success)", "str"), "podman": (5, r"\*\*(failed)\*\*", "str"),
        "podman_tests": (5, r"of (\d+)", "int"), "podman_failed": (5, r"(\d+) of", "int")}},
    "r7": {"file": CI, "start": "| Run | [41131517803]", "lines": 4, "fields": {
        "run": (None, r"\[(\d+)\]", "str"), "commit": (None, r"/ `(\w+)`", "str"),
        "offline": (None, r"`offline` \| (\w+) \|", "str"),
        "podman": (None, r"`podman` \| (\w+):", "str"),
        "podman_tests": (None, r"(\d+) tests", "int")}},
    "r8": {"file": PR, "start": "- **Observed tests (2026-11-03, local macOS, this branch)",
           "lines": 1, "fields": {
               "run": (None, r"CI run (\d+) success", "str"),
               "offline": (None, r"CI run \d+ (success)", "str"),
               "offline_tests": (None, r"\(offline (\d+) tests", "int"),
               "podman": (None, r"CI run \d+ (success)", "str"),
               "podman_tests": (None, r"podman (\d+),", "int")}},
}


def document_table() -> list[dict[str, Any]]:
    """Every document-derived value: file, where the quote starts, and how the value is read."""
    t: list[dict[str, Any]] = []
    t += _pair("primary", "| Successful task trials / 30 (primary)", r"^(\d+)/30")
    t += _pair("hidden_checks", "| Hidden checks passed / 120", r"^(\d+)/120")
    t += _pair("edge_cases", "| Edge cases passed / 60", r"^(\d+)/60")
    t += _pair("tasks_any", "| Tasks passing at least one trial / 10", r"^(\d+)/10")
    t += _pair("tasks_all", "| Tasks passing every trial / 10", r"^(\d+)/10")
    t += _pair("model_calls", "| Model calls (", r"^(\d+)$")
    t += _pair("tool_attempts", "| Tool attempts |", r"^(\d+)$")
    t += _pair("revisions", "| Revisions |", r"^(\d+)$")
    for group, key in ((1, "prompt_tokens"), (2, "completion_tokens"), (3, "total_tokens")):
        t += _pair(f"tokens.{key}", "| Prompt / completion / total tokens |",
                   r"^([\d,]+) / ([\d,]+) / ([\d,]+)$", group=group)
    t += _pair("latency_total_ms", "| Model latency, total (mean per trial) |",
               r"^([\d,]+) ms \(([\d,]+) ms\)$")
    t += _pair("latency_mean_ms", "| Model latency, total (mean per trial) |",
               r"^([\d,]+) ms \(([\d,]+) ms\)$", group=2)
    t += _pair("wall_total_ms", "| Trial wall clock, total (mean per trial) |",
               r"^([\d,]+) ms \(([\d,]+) ms\)$")
    t += _pair("cost_usd", "| Reported cost (USD) |", r"^([\d.]+)$", kind="float")
    t += _pair("cost_charged_chf", "| Charged (CHF) |", r"^([\d.]+)$", kind="float")
    t += _pair("cost_reserved_chf", "| Reserved before send (CHF) |", r"^([\d.]+)$", kind="float")
    for label in ("syntax_error", "contract_error"):
        t.append(_entry(f"failure_label.{label}.baseline", PC, "| Failure labels |",
                        rf"`{label}` (\d+)", cell=2, kind="int"))
    t.append(_entry("failure_label.wrong_answer.revised", PC, "| Failure labels |",
                    r"`wrong_answer` (\d+)", cell=3, kind="int"))
    for category in CATEGORIES:
        for variant, group in ((BASELINE, 1), (REVISED, 2)):
            t.append(_entry(f"category.{category}.{variant}", PC,
                            "Categories (successful trials of six):",
                            rf"{category} (\d)/6(?: \([\d.]+%\))? and (\d)/6", group=group,
                            kind="int"))
    t.append(_entry("task.gained", PC, "Per task: gained", r"gained `(\w+)`"))
    t.append(_entry("task.regressed", PC, "Per task: gained", r"regressed `(\w+)`"))
    t += _pair("bundle_digest", "| Bundle digest (sha256 of `manifest.json`)",
               r"`([0-9a-f]{64})`", kind="str")
    t += _pair("run_id", "| Run ID |", r"`([^`]+)`", kind="str")
    t += _pair("prompt", "| Prompt |", r"`(baseline_agent_v\d)`", kind="str")
    t += _pair("mlflow_run", "| MLflow run (", r"`([0-9a-f]{32})`", kind="str")
    t += _pair("planned_trials", "| Completeness (`trace_inspect verify`)", r"(\d+) of \d+ planned",
               kind="int")
    t += _pair("ledger_chf", "| Ledger (CHF) |", r"^(.+)$", kind="str")
    for i, title in enumerate(LIMITS):
        t.append(_entry(f"limit.{i}", PC, f"- **{title}", r"^- \*\*(.+?)\*\*"))
    t.append(_entry("non_claim", PC, "3. With 30 trials per variant",
                    r"(not a claim of improvement)"))
    experiment = "- Experiment `prompt_comparison_v1`"
    budget, cut = "- **Budget:** One ledger across all paid calls.", "**Cut order and buffer (task 3.2).**"
    t += [
        _entry("protocol.tasks", PC, experiment, r"(\w+) tasks x (\w+) trials", kind="wordint"),
        _entry("protocol.trials_per_task", PC, experiment, r"(\w+) tasks x (\w+) trials", group=2,
               kind="wordint"),
        _entry("protocol.planned_per_variant", PR, cut, r"(\d+) trials per variant \((\d+) in total\)",
               kind="int"),
        _entry("protocol.planned_total", PR, cut, r"(\d+) trials per variant \((\d+) in total\)",
               group=2, kind="int"),
        _entry("protocol.checkpoint_chf", PR, budget, r"CHF (\d+) checkpoint", kind="int"),
        _entry("protocol.ceiling_chf", PR, budget, r"CHF (\d+) ceiling", kind="int"),
        _entry("protocol.ledger_total_chf", PC, "| Ledger (CHF) |", r"-> ([\d.]+)$", cell=3),
        _entry("protocol.probes_passed", PR, cut, r"the (\d+) probes", kind="int")]
    gain, regression = "**Gain, `lists_02`", "**Regression, `strings_01`"
    gain_pattern = r"all (\w+) `lists_02` trials made (\w+) model call, (\w+) tool attempt"
    t += [
        _entry("story.lists_02.revised_trials", PC, gain, gain_pattern, kind="wordint"),
        _entry("story.lists_02.revised_model_calls", PC, gain, gain_pattern, group=2, kind="wordint"),
        _entry("story.lists_02.revised_tool_attempts", PC, gain, gain_pattern, group=3, kind="wordint"),
        _entry("story.strings_01.failed_check", PC, regression, r"edge check `(\w+)` failed \(actual (\d+)\)"),
        _entry("story.strings_01.failed_actual", PC, regression,
               r"edge check `(\w+)` failed \(actual (\d+)\)", group=2, kind="int")]
    for i, row in enumerate(PROBE_ASSET_ROWS):
        t.append(_entry(f"protocol.probe_category.{i}", "docs/threat_model.md", row, r"^(.+)$", cell=1))
    for key, run in CI_RUNS.items():
        for name, (cell, pattern, kind) in run["fields"].items():
            t.append(_entry(f"ci.{key}.{name}", run["file"], run["start"], pattern, cell=cell,
                            kind=kind, lines=run["lines"]))
    return t


def find_quote(root: Path, file: str, start: str, lines: int) -> str:
    path = root / file
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise EvidenceError(f"cannot read {file}: {error}") from error
    rows = text.split("\n")
    hits = [i for i, row in enumerate(rows) if row.startswith(start)]
    if len(hits) != 1:
        raise EvidenceError(f"{file}: expected exactly one line starting {start!r}, found {len(hits)}")
    return "\n".join(rows[hits[0]:hits[0] + lines])


def extract_value(quote: str, cell: int | None, pattern: str, group: int, kind: str) -> Any:
    text = quote
    if cell is not None:
        cells = [c.strip() for c in quote.strip().strip("|").split("|")]
        if not 1 <= cell <= len(cells):
            raise EvidenceError(f"quote has no cell {cell}: {quote[:80]!r}")
        text = cells[cell - 1]
    match = re.search(pattern, text, re.S)
    if not match:
        raise EvidenceError(f"pattern {pattern!r} does not match {text[:80]!r}")
    raw = match.group(group)
    if kind == "int":
        return int(raw.replace(",", ""))
    if kind == "float":
        return float(raw)
    if kind == "wordint":
        if raw.lower() not in WORD_INTS:
            raise EvidenceError(f"{raw!r} is not a number word")
        return WORD_INTS[raw.lower()]
    return raw


def build_documents(root: Path) -> list[dict[str, Any]]:
    documents = []
    for entry in document_table():
        quote = find_quote(root, entry["file"], entry["start"], entry["lines"])
        value = extract_value(quote, entry["cell"], entry["pattern"], entry["group"], entry["kind"])
        documents.append({**entry, "quote": quote, "value": value})
    return documents


def doc_values(documents: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {d["field"]: d["value"] for d in documents}


def assemble_doc_sections(documents: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Sections that are pure views of the quote table (so a stored copy cannot drift from it)."""
    v = doc_values(documents)
    runs: dict[str, dict[str, Any]] = {}
    for key in CI_RUNS:  # one run can be described by two documents; merge by run id
        record = {name.split(".", 2)[2]: val for name, val in v.items()
                  if name.startswith(f"ci.{key}.")}
        runs.setdefault(record["run"], {}).update(record)
    return {
        "protocol": {
            "tasks": v["protocol.tasks"], "trials_per_task": v["protocol.trials_per_task"],
            "planned_trials_per_variant": v["protocol.planned_per_variant"],
            "planned_trials_total": v["protocol.planned_total"],
            "checkpoint_chf": v["protocol.checkpoint_chf"], "ceiling_chf": v["protocol.ceiling_chf"],
            "ledger_total_chf": v["protocol.ledger_total_chf"],
            "probes_passed": v["protocol.probes_passed"],
            "probe_categories": [v[f"protocol.probe_category.{i}"] for i in range(len(PROBE_ASSET_ROWS))],
            "source": "quoted from committed documents (see documents); the ledger is never read"},
        "ci_runs": list(runs.values()),
        "mlflow_runs": {variant: v[f"mlflow_run.{variant}"] for variant in VARIANTS},
        "ledger_quotes": {variant: v[f"ledger_chf.{variant}"] for variant in VARIANTS},
        "limits": {"items": [v[f"limit.{i}"] for i in range(len(LIMITS))],
                   "non_claim": v["non_claim"],
                   "statement": "A comparison of two prompts on ten tasks with one model; the decision "
                                "is a reasoned keep, not a measured improvement or breakthrough."},
    }


# --- bundle-derived sections ----------------------------------------------------------------

METRIC_KEYS = ("primary", "hidden_checks", "edge_cases", "categories", "per_task",
               "tasks_passing_at_least_one_trial", "tasks_passing_every_trial", "failure_labels",
               "trials_per_task", "headline_eligible")
EFFICIENCY_KEYS = ("model_calls", "tool_attempts", "revisions", "recovery", "tokens",
                   "model_latency_ms", "trial_wall_clock_ms", "attempts", "cost")


def final_form(trial: Mapping[str, Any]) -> str:
    """The final message's form, from recorded grade labels and contract issue only."""
    labels = set(trial.get("labels") or [])
    if "syntax_error" in labels:
        return "prose before code"
    if "contract_error" in labels:
        return "fenced reply"
    return "bare function" if trial.get("contract_issue_code") is None else "other contract issue"


def story_trial(record: Mapping[str, Any]) -> dict[str, Any]:
    """The few recorded fields a story needs from one trial record."""
    grades = record.get("grades") or {}
    issue = record.get("contract_issue") or {}
    dev_failed = any(
        not (d.get("result") or {}).get("ok")
        or any(not c.get("passed") for c in (d.get("result") or {}).get("checks", []))
        for d in record.get("candidate_history", []))
    return {
        "trial_id": record["trial_id"], "success": bool(grades.get("success")),
        "labels": list(grades.get("labels") or []), "contract_issue_code": issue.get("code"),
        "model_calls": record["model_calls"], "tool_attempts": record["tool_attempts"],
        "dev_check_failed": dev_failed,
        "failed_checks": [{"id": c["id"], "actual": c.get("actual")}
                          for c in grades.get("checks", []) if not c.get("passed")]}


def assemble_bundle_sections(live: Mapping[str, Any]) -> dict[str, Any]:
    compare = live["compare"]
    runs = compare["runs"]
    comparison = {"experiment_id": compare["experiment_id"],
                  "headline_comparison": compare["headline_comparison"],
                  "caveats": compare["caveats"], "delta": compare["delta"]}
    efficiency = {}
    for variant in VARIANTS:
        metrics = runs[variant]["metrics"]
        comparison[variant] = {key: metrics[key] for key in METRIC_KEYS}
        efficiency[variant] = {key: metrics[key] for key in EFFICIENCY_KEYS}
    stories = {}
    for task in STORY_TASKS:
        stories[task] = {}
        for variant in VARIANTS:
            trials = []
            for record in live["story_trials"][task][variant]:
                trial = dict(record)
                trial["final_form"] = final_form(trial)
                trials.append(trial)
            stories[task][variant] = trials
    smoke = dict(live["smoke"])
    smoke["source"] = {"file": "docs/smoke_evidence.md",
                       "command": "trace_inspect show <run_id> on the retained bundle"}
    return {"comparison": comparison, "efficiency": efficiency, "stories": stories, "smoke": smoke}


def assemble_runs(live: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> dict[str, Any]:
    v = doc_values(documents)
    runs = {}
    for variant in VARIANTS:
        run = live["runs"][variant]
        prompt = live["compare"]["runs"][variant]["prompt"]
        runs[variant] = {
            "run_id": run["run_id"], "bundle": f"run_bundles/{run['run_id']}",
            "bundle_digest": run["bundle_digest"], "prompt": prompt,
            "completeness": {"complete": run["complete"], "recorded": run["recorded"],
                             "planned": run["planned"]},
            "mlflow_run_id": v[f"mlflow_run.{variant}"]}
    smoke = live["smoke"]
    runs["smoke_forced_pass"] = {"run_id": smoke["run_id"],
                                 "bundle": f"run_bundles/{smoke['run_id']}",
                                 "bundle_digest": smoke["bundle_digest"]}
    return runs


def archive_listing(root: Path) -> list[dict[str, str]]:
    archive = root / "openspec" / "changes" / "archive"
    items = []
    for path in sorted(archive.iterdir()) if archive.is_dir() else []:
        match = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)$", path.name)
        if path.is_dir() and match:
            items.append({"date": match.group(1), "name": match.group(2)})
    return items


def engineering_section(live: Mapping[str, Any], root: Path, ci_runs: list[Any]) -> dict[str, Any]:
    items = archive_listing(root)
    by_date: dict[str, int] = {}
    for item in items:
        by_date[item["date"]] = by_date.get(item["date"], 0) + 1
    specs = root / "openspec" / "specs"
    return {
        "tests": {**live["tests"],
                  "note": "collected by pytest --collect-only at the recorded commit; not pass counts"},
        "ci": {"runs": ci_runs, "source": "committed documents (see documents)"},
        "changes_archived": {"count": len(items), "items": items, "by_date": by_date},
        "specs": {"count": len([p for p in specs.iterdir() if p.is_dir()]) if specs.is_dir() else 0}}


def assemble(live: Mapping[str, Any], root: Path = REPO_ROOT, *,
             script_sha: str | None = None) -> dict[str, Any]:
    documents = build_documents(root)
    doc_sections = assemble_doc_sections(documents)
    bundle_sections = assemble_bundle_sections(live)
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "generated_by": {"script": "scripts/presentation_evidence.py",
                             "sha256": script_sha or sha256_file(Path(__file__))},
            "commit": live["commit"],
            "commands": [COMPARE_COMMAND.format(baseline=live["runs"][BASELINE]["run_id"],
                                                revised=live["runs"][REVISED]["run_id"]),
                         VERIFY_COMMAND.format(run_id="<run_id> (each of the three runs)"),
                         "pytest --collect-only -q (-m 'not sandbox' and -m sandbox)"],
            "runs": assemble_runs(live, documents)},
        **bundle_sections,
        "engineering": engineering_section(live, root, doc_sections["ci_runs"]),
        "protocol": doc_sections["protocol"],
        "ledger_quotes": {**doc_sections["ledger_quotes"],
                          "source": "quoted from docs/prompt_comparison.md; the ledger is never read"},
        "limits": doc_sections["limits"],
        "documents": documents,
    }
    return summary


# --- reading the live evidence (lazy codegen_eval import) --------------------------------------

def guard_ledger() -> str:
    """Point the ledger at a path that cannot exist before any evaluator code is imported."""
    path = str(Path(tempfile.mkdtemp(prefix="presentation-no-ledger-")) / "absent.jsonl")
    os.environ[LEDGER_ENV] = path
    return path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    return result.stdout.strip() or "unknown"


def _collect_count(root: Path, marker: str) -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker],
                            cwd=root, capture_output=True, text=True,
                            env={**os.environ, "RUN_SANDBOX_TESTS": "", "PYTHONPATH": ""})
    match = re.search(r"(?:(\d+)/)?(\d+) tests? collected", result.stdout)
    if not match:
        raise EvidenceError(f"cannot read the collected count for -m {marker!r}")
    return int(match.group(1) or match.group(2))


def load_live(bundles: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    guard_ledger()
    sys.path.insert(0, str(root / "src"))
    from codegen_eval.bundle import (BundleError, load_manifest, load_trial, resolve_bundle,
                                     verify_bundle)
    from codegen_eval.comparison import compare_runs
    from codegen_eval.experiment import DEFAULT_BENCHMARK, DEFAULT_CONFIG, load_config
    try:
        ids = {BASELINE: "20261103T053309Z-280182", REVISED: "20261103T095324Z-d25905"}
        smoke_id = "20261103T050806Z-30949f"
        dirs = {name: resolve_bundle(bundles, run_id) for name, run_id in ids.items()}
        compare = compare_runs(dirs[BASELINE], dirs[REVISED], DEFAULT_BENCHMARK,
                               load_config(DEFAULT_CONFIG))
        if not compare["headline_comparison"]:
            raise EvidenceError("the pair is not a headline comparison: "
                                + "; ".join(compare["reasons_not_headline"]))
        for name in VARIANTS:  # no absolute path may reach the summary
            compare["runs"][name]["bundle"] = f"run_bundles/{ids[name]}"
        runs, stories = {}, {}
        for name in VARIANTS:
            check = verify_bundle(dirs[name])
            runs[name] = {"run_id": ids[name], "bundle_digest": check.bundle_digest,
                          "complete": check.complete, "recorded": len(check.recorded),
                          "planned": len(check.planned)}
        for task in STORY_TASKS:
            stories[task] = {name: [story_trial(load_trial(dirs[name], f"{task}-t{n}"))
                                    for n in (1, 2, 3)] for name in VARIANTS}
        smoke_dir = resolve_bundle(bundles, smoke_id)
        smoke_manifest = load_manifest(smoke_dir)
        smoke_check = verify_bundle(smoke_dir)
        trial = load_trial(smoke_dir, smoke_manifest["planned"][0]["trial_id"])
        smoke = {"run_id": smoke_id, "bundle_digest": smoke_check.bundle_digest,
                 "status": smoke_manifest.get("status"), "task_id": trial["task_id"],
                 "model_calls": trial["model_calls"], "tool_attempts": trial["tool_attempts"],
                 "mode": (smoke_manifest["identity"].get("smoke") or {}).get("mode")}
    except BundleError as error:
        raise EvidenceError(f"bundle problem: {error}") from error
    return {"compare": compare, "runs": runs, "story_trials": stories, "smoke": smoke,
            "commit": _git_commit(root),
            "tests": {"offline_collected": _collect_count(root, "not sandbox"),
                      "sandbox_collected": _collect_count(root, "sandbox"),
                      "commit": _git_commit(root)}}


# --- canonical JSON, schema, consistency --------------------------------------------------------

def canonical(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_summary(root: Path = REPO_ROOT) -> dict[str, Any]:
    try:
        return json.loads((root / SUMMARY_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise EvidenceError(f"cannot read {SUMMARY_REL}: {error}") from error


def validate_structure(summary: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if summary.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("provenance", "comparison", "efficiency", "stories", "smoke", "engineering",
                "ledger_quotes", "limits", "documents", "protocol"):
        if key not in summary:
            problems.append(f"missing section {key!r}")
    if problems:
        return problems
    for variant in VARIANTS:
        for section, keys in (("comparison", METRIC_KEYS), ("efficiency", EFFICIENCY_KEYS)):
            block = summary[section].get(variant)
            if not isinstance(block, dict):
                problems.append(f"{section}.{variant}: missing")
                continue
            for key in keys:
                if key not in block:
                    problems.append(f"{section}.{variant}.{key}: missing")
        for task in STORY_TASKS:
            trials = summary["stories"].get(task, {}).get(variant)
            if not isinstance(trials, list) or len(trials) != 3:
                problems.append(f"stories.{task}.{variant}: expected three trials")
        run = summary["provenance"]["runs"].get(variant, {})
        for key in ("run_id", "bundle", "bundle_digest", "prompt", "completeness", "mlflow_run_id"):
            if key not in run:
                problems.append(f"provenance.runs.{variant}.{key}: missing")
        if str(run.get("bundle", "")).startswith("/"):
            problems.append(f"provenance.runs.{variant}.bundle must be relative")
    for key in ("offline_collected", "sandbox_collected", "commit"):
        if key not in summary["engineering"].get("tests", {}):
            problems.append(f"engineering.tests.{key}: missing")
    if not summary["limits"].get("items") or not summary["limits"].get("non_claim"):
        problems.append("limits: the limits and the non-claim are required")
    return problems


def check_arithmetic(summary: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for variant in VARIANTS:
        m = summary["comparison"][variant]
        for key in ("primary", "hidden_checks", "edge_cases", "tasks_passing_at_least_one_trial",
                    "tasks_passing_every_trial"):
            r = m[key]
            if not 0 <= r["count"] <= r["of"]:
                problems.append(f"comparison.{variant}.{key}: {r['count']} of {r['of']} is impossible")
        if sum(v["succeeded"] for v in m["per_task"].values()) != m["primary"]["count"]:
            problems.append(f"comparison.{variant}: per-task successes do not sum to the primary count")
        if sum(v["count"] for v in m["categories"].values()) != m["primary"]["count"]:
            problems.append(f"comparison.{variant}: category successes do not sum to the primary count")
        if any(v["succeeded"] > v["trials"] for v in m["per_task"].values()):
            problems.append(f"comparison.{variant}: a task has more successes than trials")
        tokens = summary["efficiency"][variant]["tokens"]
        if tokens["prompt_tokens"] + tokens["completion_tokens"] != tokens["total_tokens"]:
            problems.append(f"efficiency.{variant}: token parts do not sum to the total")
        for task in STORY_TASKS:
            story = summary["stories"][task][variant]
            if sum(t["success"] for t in story) != m["per_task"][task]["succeeded"]:
                problems.append(f"stories.{task}.{variant}: successes disagree with per_task")
    return problems


def _same_number(doc: Any, actual: Any, doc_text: str | None = None) -> bool:
    if isinstance(doc, float) or isinstance(actual, float):
        decimals = len(doc_text.split(".")[1]) if doc_text and "." in doc_text else 12
        return round(float(actual), decimals) == round(float(doc), decimals)
    return doc == actual


def cross_check(summary: Mapping[str, Any]) -> list[str]:
    """Bundle-derived headline numbers against the reviewed lines of the comparison document."""
    v = doc_values(summary["documents"])
    problems: list[str] = []

    def expect(field: str, actual: Any, round_to: int | None = None) -> None:
        doc = v.get(field)
        ok = (round(float(actual)) == doc if round_to == 0
              else _same_number(doc, actual, str(doc)) if round_to is None
              else round(float(actual), round_to) == round(float(doc), round_to))
        if not ok:
            problems.append(f"{field}: summary has {actual!r}, {PC} has {doc!r}")

    for variant in VARIANTS:
        c, e = summary["comparison"][variant], summary["efficiency"][variant]
        expect(f"primary.{variant}", c["primary"]["count"])
        expect(f"hidden_checks.{variant}", c["hidden_checks"]["count"])
        expect(f"edge_cases.{variant}", c["edge_cases"]["count"])
        expect(f"tasks_any.{variant}", c["tasks_passing_at_least_one_trial"]["count"])
        expect(f"tasks_all.{variant}", c["tasks_passing_every_trial"]["count"])
        expect(f"model_calls.{variant}", e["model_calls"])
        expect(f"tool_attempts.{variant}", e["tool_attempts"])
        expect(f"revisions.{variant}", e["revisions"])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            expect(f"tokens.{key}.{variant}", e["tokens"][key])
        expect(f"latency_total_ms.{variant}", e["model_latency_ms"]["total"])
        expect(f"latency_mean_ms.{variant}", e["model_latency_ms"]["mean_per_trial"], 0)
        expect(f"wall_total_ms.{variant}", e["trial_wall_clock_ms"]["total"])
        for field, key in (("cost_usd", "reported_usd"), ("cost_charged_chf", "charged_chf"),
                           ("cost_reserved_chf", "reserved_before_send_chf")):
            expect(f"{field}.{variant}", e["cost"][key], len(str(v[f"{field}.{variant}"]).split(".")[1]))
        for category in CATEGORIES:
            expect(f"category.{category}.{variant}", c["categories"][category]["count"])
        run = summary["provenance"]["runs"][variant]
        for field, actual in ((f"bundle_digest.{variant}", run["bundle_digest"]),
                              (f"run_id.{variant}", run["run_id"]),
                              (f"prompt.{variant}", run["prompt"]["version"]),
                              (f"planned_trials.{variant}", run["completeness"]["recorded"])):
            if v[field] != actual:
                problems.append(f"{field}: summary has {actual!r}, document has {v[field]!r}")
        if not run["completeness"]["complete"]:
            problems.append(f"provenance.runs.{variant}: the run is not complete")
    for label, variant in (("syntax_error", BASELINE), ("contract_error", BASELINE),
                           ("wrong_answer", REVISED)):
        actual = summary["comparison"][variant]["failure_labels"].get(label, 0)
        if v[f"failure_label.{label}.{variant}"] != actual:
            problems.append(f"failure_label.{label}.{variant}: summary has {actual}")
    protocol = summary["protocol"]
    base = summary["comparison"]["baseline"]
    if protocol["tasks"] != len(base["per_task"]):
        problems.append(f"protocol.tasks: {protocol['tasks']} but the comparison has {len(base['per_task'])} tasks")
    if protocol["trials_per_task"] != base["trials_per_task"][0]:
        problems.append("protocol.trials_per_task differs from the comparison")
    if protocol["planned_trials_per_variant"] != base["primary"]["of"] \
            or protocol["planned_trials_total"] != 2 * base["primary"]["of"]:
        problems.append("protocol planned trials differ from the comparison denominators")
    if protocol["tasks"] * protocol["trials_per_task"] != protocol["planned_trials_per_variant"]:
        problems.append("protocol: tasks x trials per task is not the planned trials per variant")
    if not summary["ledger_quotes"][REVISED].endswith(protocol["ledger_total_chf"]):
        problems.append("protocol.ledger_total_chf is not the end of the revised ledger quote")
    lists = summary["stories"]["lists_02"]["revised"]
    if len(lists) != v["story.lists_02.revised_trials"] or any(
            t["model_calls"] != v["story.lists_02.revised_model_calls"]
            or t["tool_attempts"] != v["story.lists_02.revised_tool_attempts"] for t in lists):
        problems.append("stories.lists_02.revised: model calls or tool attempts differ from "
                        f"{PC} (all revised trials made {v['story.lists_02.revised_model_calls']} call(s), "
                        f"{v['story.lists_02.revised_tool_attempts']} tool attempt(s))")
    failed = [c for t in summary["stories"]["strings_01"]["revised"] for c in t["failed_checks"]]
    if failed != [{"id": v["story.strings_01.failed_check"], "actual": v["story.strings_01.failed_actual"]}]:
        problems.append(f"stories.strings_01.revised: the failed checks {failed!r} differ from {PC}")
    delta = summary["comparison"]["delta"]
    if [v["task.gained"]] != delta["gained_tasks"] or [v["task.regressed"]] != delta["regressed_tasks"]:
        problems.append("gained/regressed tasks differ from the comparison document")
    return problems


def check_documents(summary: Mapping[str, Any], root: Path) -> list[str]:
    """Quote in file, value derived from the quote, and the stored table equals the script's."""
    problems: list[str] = []
    stored = summary["documents"]
    try:
        fresh = build_documents(root)
    except EvidenceError as error:
        return [str(error)]
    if [d["field"] for d in stored] != [d["field"] for d in fresh]:
        problems.append("documents: the stored table differs from the script's quote table")
        return problems
    for have, want in zip(stored, fresh):
        field = have["field"]
        try:
            derived = extract_value(have["quote"], have["cell"], have["pattern"], have["group"],
                                    have["kind"])
        except EvidenceError as error:
            problems.append(f"{field}: {error}")
            continue
        if derived != have["value"]:
            problems.append(f"{field}: stored value {have['value']!r} is not what its quote gives "
                            f"({derived!r})")
        if have["quote"] != want["quote"]:
            problems.append(f"{field}: the quote no longer occurs in {have['file']}: "
                            f"{have['quote'][:70]!r}")
        elif have != want:
            problems.append(f"{field}: stored entry differs from the script's table")
    doc_sections = assemble_doc_sections(stored)
    for key, name in (("limits", "limits"), ("ledger_quotes", "ledger_quotes"), ("protocol", "protocol")):
        if {k: v for k, v in summary[key].items() if k in doc_sections[name]} != doc_sections[name]:
            problems.append(f"{key}: differs from the quote table")
    if summary["engineering"]["ci"]["runs"] != doc_sections["ci_runs"]:
        problems.append("engineering.ci.runs: differs from the quote table")
    for variant in VARIANTS:
        if summary["provenance"]["runs"][variant]["mlflow_run_id"] != doc_sections["mlflow_runs"][variant]:
            problems.append(f"provenance.runs.{variant}.mlflow_run_id: differs from the quote table")
    return problems


FORBIDDEN_TEXT = (re.compile(r"/Users/"), re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
                  re.compile(r"(?i)authorization\s*:"), re.compile(r"spend_ledger"),
                  re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{12,}"))


def scan_text(name: str, text: str, extra: tuple[str, ...] = ()) -> list[str]:
    problems = [f"{name}: matches {p.pattern!r}" for p in FORBIDDEN_TEXT if p.search(text)]
    problems += [f"{name}: contains {token!r}" for token in extra if token and token in text]
    return problems


# --- manifest ------------------------------------------------------------------------------------

DIAGRAMS = (
    ("diagram-architecture-logical", "docs/architecture_logical.drawio.svg", "architecture",
     "Logical architecture: components, data flow, trust boundary.",
     "Boxes for the agent controller, sandbox, grader, bundles and tracking, with arrows for data flow."),
    ("diagram-architecture-physical", "docs/architecture_physical.drawio.svg", "architecture",
     "Physical architecture: laptop, Podman containers and trust boundaries.",
     "Deployment view of the host, the candidate containers and the local MLflow service."),
    ("diagram-run-flow-activity", "docs/run_flow_activity.drawio.svg", "run-flow",
     "Run flow as an activity diagram.", "Activity diagram of one evaluation run from schedule to bundle."),
    ("diagram-run-flow-sequence", "docs/run_flow_sequence.drawio.svg", "run-flow",
     "Run flow as a sequence diagram.", "Sequence diagram of the controller, model, tool and grader messages."),
    ("diagram-work-log-architecture", "docs/work_log_architecture.svg", "architecture",
     "Goal architecture: bounded agent, hidden grading, local evidence.",
     "Figure of implemented, built-offline and pending components."),
)
SCREENSHOTS = (
    ("shot-mlflow-experiment-runs", "mlflow-experiment-runs.png",
     "MLflow experiment codegen-eval-runs with the two comparison runs.",
     "Experiment codegen-eval-runs, runs table",
     "both comparison runs by name and ID, success_rate, tags"),
    ("shot-mlflow-run-baseline", "mlflow-run-baseline.png", "MLflow overview of the baseline run.",
     "Baseline run overview (parameters, metrics, tags)",
     "run 930a188254d34d279a88a7613ea55518 and the bundle digest tag"),
    ("shot-mlflow-run-revised", "mlflow-run-revised.png", "MLflow overview of the revised run.",
     "Revised run overview", "run bcddf5c9561c43129504555b020a7557"),
    ("shot-mlflow-compare", "mlflow-compare.png", "MLflow comparison of the two runs side by side.",
     "Two-run comparison view", "both runs side by side with success_rate"),
    ("shot-mlflow-trace-lists02-baseline", "mlflow-trace-lists02-baseline.png",
     "MLflow trace of a baseline lists_02 trial.",
     "A lists_02 baseline trace (explanation after a failed check)", "AGENT, CHAT_MODEL and TOOL spans"),
    ("shot-mlflow-trace-lists02-revised", "mlflow-trace-lists02-revised.png",
     "MLflow trace of a revised lists_02 trial.", "A lists_02 revised trace",
     "one model call and the final submission"),
    ("shot-mlflow-trace-strings01-t2-revised", "mlflow-trace-strings01-t2-revised.png",
     "MLflow trace of strings_01-t2 of the revised run.", "strings_01-t2 of the revised run",
     "the final source"),
    ("shot-report-local-architecture", "report-local-architecture.png",
     "The local HTML work log opened from disk, architecture figure.",
     "report/index.html architecture figure", "implemented and planned legend"),
    ("shot-report-local-results", "report-local-results.png",
     "The local HTML work log, results and comparison section.",
     "report/index.html results section", "counts and limits"),
)
LOGO = ("zhaw-logo", "presentation/assets/zhaw_rgb.jpg", "presentation/assets/zhaw_rgb.jpg.source.txt",
        "ZHAW logo for the title slide.")
CAST_REL = "presentation/recording/demo.cast"
PLAYER_REL = "presentation/recording/player.html"
REVIEW_REL = "presentation/recording/review.txt"
USER_TEXT_REL = "presentation/user_text.toml"
USER_TEXT_SLOTS = ("motivation", "takeaways")
USER_TEXT_KEYS = ("deck", "report")


def read_user_text(root: Path) -> dict[str, Any]:
    path = root / USER_TEXT_REL
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise EvidenceError(f"cannot read {USER_TEXT_REL}: {error}") from error


def user_text_entry(root: Path) -> dict[str, Any]:
    """Where the user's words live and which slots are still empty; this never writes the file."""
    data = read_user_text(root)
    slots = {slot: {key: ("filled" if str(data.get(slot, {}).get(key, "")).strip() else "empty")
                    for key in USER_TEXT_KEYS} for slot in USER_TEXT_SLOTS}
    return {"path": USER_TEXT_REL, "owner": "user", "slots": slots,
            "alt": "Text the user writes for the deck and the report; empty slots show a placeholder.",
            "note": "tools never fill these slots; consumers show a visible placeholder for an empty one"}


def build_manifest(root: Path = REPO_ROOT) -> dict[str, Any]:
    figures = []
    for meta in render_charts.CHART_META:
        figures.append({
            "id": meta["id"], "path": f"{CHARTS_REL}/{meta['id']}.svg", "format": "svg",
            "caption": meta["caption"], "alt": meta["alt"], "uses": ["deck", "report"],
            "variant": "full", "full_size": None,
            "viewbox": render_charts.VIEWBOX, "min_render_mm": 160,
            "min_font_units": render_charts.MIN_FONT, "elements": "work-log set",
            "source_keys": meta["source_keys"]})
    for meta in render_charts.COMPACT_META:
        figures.append({
            "id": meta["id"], "path": f"{CHARTS_REL}/{meta['id']}.svg", "format": "svg",
            "caption": meta["caption"], "alt": meta["alt"], "uses": ["report"],
            "variant": "compact", "full_size": meta["full_size"],
            "viewbox": render_charts.COMPACT_VIEWBOX, "min_render_mm": render_charts.COMPACT_MIN_MM,
            "min_font_units": render_charts.COMPACT_MIN_FONT, "elements": "work-log set",
            "source_keys": meta["source_keys"]})
    diagrams = [{"id": i, "path": p, "format": "svg", "caption": c, "alt": a, "role": role,
                 "status": "present" if (root / p).is_file() else "pending"}
                for i, p, role, c, a in DIAGRAMS]
    for meta in render_charts.DIAGRAM_META:
        diagrams.append({
            "id": meta["id"], "path": f"{CHARTS_REL}/{meta['id']}.svg", "format": "svg",
            "caption": meta["caption"], "alt": meta["alt"], "role": meta["role"],
            "uses": ["deck", "report"], "viewbox": render_charts.VIEWBOX, "min_render_mm": 160,
            "min_font_units": render_charts.MIN_FONT, "elements": "work-log set", "status": "present"})
    screenshots = [{"id": i, "path": f"presentation/screenshots/{name}", "format": "png",
                    "caption": caption, "alt": f"Screenshot: {shows}.", "shows": shows,
                    "must_display": must, "owner": "coordinator",
                    "status": "present" if (root / "presentation" / "screenshots" / name).is_file()
                    else "pending"}
                   for i, name, caption, shows, must in SCREENSHOTS]
    logo_id, logo_path, note_path, logo_caption = LOGO
    logo_file = root / logo_path
    asset = {"id": logo_id, "path": logo_path, "format": "jpg", "caption": logo_caption,
             "alt": "ZHAW logo: the blue lowercase letters zh above aw", "source_note": note_path,
             "sha256": sha256_file(logo_file) if logo_file.is_file() else None,
             "status": "present" if logo_file.is_file() else "pending"}
    cast = root / CAST_REL
    status = ("pending" if not cast.is_file()
              else "approved" if (root / REVIEW_REL).is_file() else "unreviewed")
    return {
        "schema_version": SCHEMA_VERSION,
        "title": {"author": "Jose Luis Barahona", "course": "CAS Applied Machine Learning (ZHAW)",
                  "date": None, "date_placeholder": DATE_PLACEHOLDER, "headline": HEADLINE},
        "summary": SUMMARY_REL, "figures": figures, "diagrams": diagrams,
        "screenshots": screenshots, "assets": [asset], "user_text": user_text_entry(root),
        "recording": {"cast": CAST_REL, "player_template": PLAYER_REL,
                      "built_player": "report/demo.html", "status": status,
                      "note": "kept for interested viewers; not part of the talk"}}


def check_manifest(manifest: Mapping[str, Any], root: Path) -> list[str]:
    problems: list[str] = []
    if manifest.get("title", {}).get("date") is not None:
        problems.append("manifest title.date must stay null (the user fills it in)")
    ids = {e["id"] for e in manifest["figures"]}
    for entry in manifest["figures"]:
        if entry.get("variant") == "compact" and entry.get("full_size") not in ids:
            problems.append(f"figures {entry['id']}: full_size {entry.get('full_size')!r} is not a figure")
        if entry.get("variant") == "full" and entry.get("full_size") is not None:
            problems.append(f"figures {entry['id']}: a full-size figure has no full_size")
    for chart_id, _ in ((m["full_size"], m) for m in render_charts.COMPACT_META):
        if not any(e["id"] == f"{chart_id}-compact" for e in manifest["figures"]):
            problems.append(f"figures: no compact variant of {chart_id}")
    entries = ([("figures", e) for e in manifest["figures"]]
               + [("diagrams", e) for e in manifest["diagrams"]]
               + [("screenshots", e) for e in manifest["screenshots"]]
               + [("assets", e) for e in manifest["assets"]])
    for kind, entry in entries:
        if not str(entry.get("alt", "")).strip():
            problems.append(f"{kind} {entry['id']}: alt text is required")
        present = (root / entry["path"]).is_file()
        if not present and entry.get("status") != "pending":
            problems.append(f"{kind} {entry['id']}: {entry['path']} is missing and not pending")
        if present and entry.get("status") == "pending":
            problems.append(f"{kind} {entry['id']}: file exists but is marked pending")
    user_text = manifest.get("user_text")
    if not user_text or not (root / user_text.get("path", "")).is_file():
        problems.append("manifest user_text: the user-text file is missing")
    elif not str(user_text.get("alt", "")).strip():
        problems.append("manifest user_text: alt text is required")
    for entry in manifest["assets"]:
        note = root / entry.get("source_note", "")
        if entry["status"] == "present":
            text = note.read_text(encoding="utf-8") if note.is_file() else ""
            if entry["sha256"] not in text or "https://www.zhaw.ch/" not in text:
                problems.append(f"asset {entry['id']}: the source note must name the URL and digest")
            if sha256_file(root / entry["path"]) != entry["sha256"]:
                problems.append(f"asset {entry['id']}: digest differs from the file")
    return problems


# --- commands --------------------------------------------------------------------------------------

def cmd_collect(args: argparse.Namespace) -> int:
    root = Path(args.root)
    live = load_live(Path(args.bundles), root)
    summary = assemble(live, root)
    problems = validate_structure(summary) + check_arithmetic(summary) + cross_check(summary)
    if problems:
        raise EvidenceError("refusing to write an inconsistent summary:\n  " + "\n  ".join(problems))
    text = canonical(summary)
    problems = scan_text(SUMMARY_REL, text, (str(Path.home()), str(root)))
    if problems:
        raise EvidenceError("\n  ".join(problems))
    out = root / SUMMARY_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {SUMMARY_REL}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    root = Path(args.root)
    out = root / MANIFEST_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(build_manifest(root)), encoding="utf-8")
    print(f"wrote {MANIFEST_REL}")
    return 0


def check_all(root: Path, bundles: Path | None = None) -> list[str]:
    summary = load_summary(root)
    problems = validate_structure(summary)
    if problems:
        return problems
    problems += check_arithmetic(summary)
    problems += check_documents(summary, root)
    problems += cross_check(summary)
    problems += scan_text(SUMMARY_REL, canonical(summary), (str(Path.home()), str(root)))
    if canonical(summary) != (root / SUMMARY_REL).read_text(encoding="utf-8"):
        problems.append(f"{SUMMARY_REL} is not in canonical form")
    problems += render_charts.check_charts(summary, root / CHARTS_REL)
    try:
        manifest = json.loads((root / MANIFEST_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return problems + [f"cannot read {MANIFEST_REL}: {error}"]
    if manifest != build_manifest(root):
        problems.append(f"{MANIFEST_REL} differs from a fresh build (run the manifest command)")
    problems += check_manifest(manifest, root)
    if bundles is not None and not problems:
        live = load_live(bundles, root)
        fresh = assemble(live, root)
        for key in BUNDLE_SECTIONS:
            if fresh[key] != summary[key]:
                problems.append(f"{key}: differs from the bundles ({_first_difference(summary[key], fresh[key])})")
        if fresh["provenance"]["runs"] != summary["provenance"]["runs"]:
            problems.append("provenance.runs: differs from the bundles")
        for key in ("generated_by", "commit"):
            print(f"note: provenance.{key} is reported, not compared "
                  f"(summary {summary['provenance'][key]!r}, now {fresh['provenance'][key]!r})")
    return problems


def _first_difference(a: Any, b: Any, path: str = "") -> str:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return _first_difference(a.get(key), b.get(key), f"{path}.{key}" if path else key)
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return _first_difference(x, y, f"{path}[{i}]")
    return f"{path}: {a!r} != {b!r}"


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if args.staleness:
        return staleness(root)
    problems = check_all(root, Path(args.bundles) if args.bundles else None)
    if problems:
        print("presentation evidence check FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    mode = "with bundles" if args.bundles else "offline"
    print(f"presentation evidence check passed ({mode})")
    return 0


def staleness(root: Path) -> int:
    """Read-only: compare the engineering snapshot with the repository; never fatal."""
    summary = load_summary(root)
    eng = summary["engineering"]
    now_items = archive_listing(root)
    notes = []
    if len(now_items) != eng["changes_archived"]["count"]:
        notes.append(f"archived changes: summary {eng['changes_archived']['count']}, now {len(now_items)}")
    for key, marker in (("offline_collected", "not sandbox"), ("sandbox_collected", "sandbox")):
        try:
            now = _collect_count(root, marker)
        except EvidenceError as error:
            notes.append(str(error))
            continue
        if now != eng["tests"][key]:
            notes.append(f"{key}: summary {eng['tests'][key]}, now {now}")
    head = _git_commit(root)
    if head != eng["tests"]["commit"]:
        notes.append(f"snapshot commit {eng['tests']['commit'][:8]}, HEAD {head[:8]}")
    print("engineering snapshot is current" if not notes
          else "engineering snapshot is older than the repository:\n  " + "\n  ".join(notes))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="write summary.json from the retained bundles (read-only)")
    collect.add_argument("--bundles", required=True, help="bundle storage directory (never written)")
    sub.add_parser("manifest", help="write presentation/manifest.json")
    check = sub.add_parser("check", help="verify the summary, charts and manifest")
    check.add_argument("--bundles", help="also recompute the bundle-derived sections")
    check.add_argument("--staleness", action="store_true",
                       help="read-only report on whether the engineering snapshot is current")
    args = parser.parse_args(argv)
    try:
        return {"collect": cmd_collect, "manifest": cmd_manifest, "check": cmd_check}[args.command](args)
    except EvidenceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
