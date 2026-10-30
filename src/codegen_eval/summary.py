"""Fixed-denominator run summaries and incomplete-run classification.

Completeness is decided by `bundle.verify_bundle` (record level); this module only classifies
the problems it reports and builds counts from the stored grades. Missing, unreadable, pending
or infrastructure-stopped trials stay in the planned denominators as unexecuted, unsuccessful
checks, and the run is excluded from headline comparison rather than rescored on fewer trials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from codegen_eval.bundle import (
    GRADE_GRADED,
    INFRASTRUCTURE_STOP,
    MISSING_RECORD,
    Verification,
    load_manifest,
    load_trial,
    verify_bundle,
)
from codegen_eval.evaluate import CaseResult, RunCounts, TrialGrade, _unexecuted, count_results
from codegen_eval.model_client import TRANSPORT_EXHAUSTED
from codegen_eval.tasks import Task

INFRASTRUCTURE = "infrastructure"                # container unavailable, worker protocol broken
EXHAUSTED_TRANSPORT = "exhausted_transport"      # API transport retries used up
FAILED_COMPLETENESS = "failed_completeness"      # record-level check failed for any other reason


@dataclass(frozen=True)
class RunClassification:
    run_id: str | None
    complete: bool
    classes: tuple[str, ...]           # empty when complete; otherwise every applicable class
    infrastructure_statuses: tuple[str, ...]
    verification: Verification

    @property
    def headline_eligible(self) -> bool:
        return self.complete


@dataclass(frozen=True)
class RunSummary:
    classification: RunClassification
    counts: RunCounts
    trials_planned: int
    trials_succeeded: int
    trials_incomplete: int
    categories: Mapping[str, tuple[int, int]]   # category -> (trials succeeded, trials planned)

    @property
    def headline_eligible(self) -> bool:
        return self.classification.headline_eligible

    @property
    def trial_success_rate(self) -> float:
        return self.trials_succeeded / self.trials_planned if self.trials_planned else 0.0


def _infrastructure_status(bundle_dir: Path, trial_id: str) -> str | None:
    try:
        record = load_trial(bundle_dir, trial_id)
    except Exception:  # unreadable records are already problems of their own
        return None
    grades = record.get("grades") if isinstance(record, dict) else None
    status = (grades or {}).get("infrastructure_status") if isinstance(grades, dict) else None
    return status or (record.get("infrastructure_status") if isinstance(record, dict) else None)


def classify_run(bundle_dir: str | Path, verification: Verification | None = None) -> RunClassification:
    """Classify a bundle from the result of `verify_bundle` (run here unless supplied)."""
    path = Path(bundle_dir)
    result = verification or verify_bundle(path)
    if result.complete:
        return RunClassification(result.run_id, True, (), (), result)
    classes: list[str] = []
    statuses: list[str] = []
    for problem in result.problems:
        if problem.kind == INFRASTRUCTURE_STOP and problem.trial_id:
            status = _infrastructure_status(path, problem.trial_id) or "unknown"
            statuses.append(status)
            classes.append(EXHAUSTED_TRANSPORT if status == TRANSPORT_EXHAUSTED else INFRASTRUCTURE)
        else:
            classes.append(FAILED_COMPLETENESS)
    return RunClassification(result.run_id, False, tuple(dict.fromkeys(classes)),
                             tuple(dict.fromkeys(statuses)), result)


def _grade_from_record(task: Task, record: Mapping, problem_kind: str | None) -> TrialGrade:
    grades = record.get("grades") if record else None
    if isinstance(grades, dict) and grades.get("status") == GRADE_GRADED:
        cases = tuple(CaseResult(c["id"], c.get("kind", ""), c["executed"], c["passed"],
                                 tuple(c["failures"]), c.get("actual")) for c in grades["checks"])
        return TrialGrade(task.id, task.category, grades["trial_status"], tuple(grades["labels"]),
                          grades["success"], False, None, cases)
    infra = grades.get("infrastructure_status") if isinstance(grades, dict) else None
    label = infra or problem_kind or "grade_pending"
    return TrialGrade(task.id, task.category, record.get("status", label) if record else label,
                      (label,), False, True, infra, _unexecuted(task, (label,)))


def summarize_bundle(bundle_dir: str | Path, tasks: Iterable[Task]) -> RunSummary:
    """Counts and rates over every planned trial, whatever the run's completeness."""
    path = Path(bundle_dir)
    by_id = {task.id: task for task in tasks}
    verification = verify_bundle(path)
    classification = classify_run(path, verification)
    manifest = load_manifest(path)
    flawed = {p.trial_id: p.kind for p in verification.problems if p.trial_id}
    grades = []
    for planned in manifest["planned"]:
        task = by_id[planned["task_id"]]
        trial_id = planned["trial_id"]
        record: Mapping = {}
        if trial_id in verification.recorded:
            record = load_trial(path, trial_id)
        kind = flawed.get(trial_id)
        grades.append(_grade_from_record(task, record, "missing_record" if kind == MISSING_RECORD else kind)
                      if kind or not record else _grade_from_record(task, record, None))
    counts = count_results(grades)
    categories: dict[str, tuple[int, int]] = {}
    for grade in grades:
        won, total = categories.get(grade.category, (0, 0))
        categories[grade.category] = (won + grade.success, total + 1)
    return RunSummary(classification, counts, len(grades), sum(g.success for g in grades),
                      sum(g.incomplete for g in grades), categories)
