"""Fixed-denominator run summaries and incomplete-run classification.

Completeness is decided by `bundle.verify_bundle` (record level); this module only classifies
the problems it reports and builds counts from the stored grades. Missing, unreadable, pending
or infrastructure-stopped trials stay in the planned denominators as unexecuted, unsuccessful
checks, and the run is excluded from headline comparison rather than rescored on fewer trials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from codegen_eval.bundle import (
    GRADE_INCOMPLETE,
    GRADE_GRADED,
    INFRASTRUCTURE_STOP,
    MISSING_RECORD,
    NOT_FINALIZED,
    BundleError,
    Verification,
    load_manifest,
    load_trial,
    verify_bundle,
)
from codegen_eval.evaluate import CaseResult, RunCounts, TrialGrade, _unexecuted, count_results
from codegen_eval.model_client import TRANSPORT_EXHAUSTED
from codegen_eval.replay import _check_benchmark_identity
from codegen_eval.tasks import Task, load_benchmark

INFRASTRUCTURE = "infrastructure"                # container unavailable, worker protocol broken
EXHAUSTED_TRANSPORT = "exhausted_transport"      # API transport retries used up
FAILED_COMPLETENESS = "failed_completeness"      # record-level check failed for any other reason


@dataclass(frozen=True)
class RunClassification:
    run_id: str | None
    complete: bool                     # the run-evidence verdict (`verify_bundle`), unchanged
    classes: tuple[str, ...]           # empty when complete; otherwise every applicable class
    infrastructure_statuses: tuple[str, ...]
    verification: Verification

    @property
    def headline_eligible(self) -> bool:
        """Complete record-level verdict and every planned trial graded: a pending grade is
        no outcome, so a complete-but-ungraded run is not a headline figure."""
        return self.complete and not self.verification.grades_pending


@dataclass(frozen=True)
class RunSummary:
    classification: RunClassification
    counts: RunCounts
    trials_planned: int
    trials_succeeded: int
    trials_incomplete: int             # infrastructure outcomes and trials with no usable record
    trials_ungraded: int               # intact records whose grade is still pending
    categories: Mapping[str, tuple[int, int]]   # category -> (trials succeeded, trials planned)

    @property
    def headline_eligible(self) -> bool:
        return (self.classification.headline_eligible
                and self.counts.complete_for(self.classification.verification))

    @property
    def trial_success_rate(self) -> float:
        return self.trials_succeeded / self.trials_planned if self.trials_planned else 0.0


def _infrastructure_status(bundle_dir: Path, trial_id: str) -> str | None:
    try:
        record = load_trial(bundle_dir, trial_id)
    except BundleError:  # an unreadable record is already a problem of its own
        return None
    grades = record.get("grades")
    status = grades.get("infrastructure_status") if isinstance(grades, dict) else None
    return status or record.get("infrastructure_status")


def classify_run(bundle_dir: str | Path, verification: Verification | None = None) -> RunClassification:
    """Classify a bundle from the result of `verify_bundle` (run here unless supplied).

    `run_not_finalized` is implied by any other problem (the writer stores `incomplete`
    whenever verification found one), so it counts as `failed_completeness` only when it is
    the sole problem, for example a run that crashed or is still in progress."""
    path = Path(bundle_dir)
    result = verification or verify_bundle(path)
    if result.complete:
        return RunClassification(result.run_id, True, (), (), result)
    problems = [p for p in result.problems if p.kind != NOT_FINALIZED] or list(result.problems)
    classes: list[str] = []
    statuses: list[str] = []
    for problem in problems:
        if problem.kind == INFRASTRUCTURE_STOP and problem.trial_id:
            status = _infrastructure_status(path, problem.trial_id) or "unknown"
            statuses.append(status)
            classes.append(EXHAUSTED_TRANSPORT if status == TRANSPORT_EXHAUSTED else INFRASTRUCTURE)
        else:
            classes.append(FAILED_COMPLETENESS)
    return RunClassification(result.run_id, False, tuple(dict.fromkeys(classes)),
                             tuple(dict.fromkeys(statuses)), result)


def _unusable(task: Task, record: Mapping, label: str, infrastructure: str | None = None) -> TrialGrade:
    """A trial with no outcome to trust: four planned checks, unexecuted and unsuccessful."""
    return TrialGrade(task.id, task.category, record.get("status", label), (label,), False, True,
                      infrastructure, _unexecuted(task, (label,)))


def _grade_from_record(task: Task, record: Mapping, problem_kinds: set[str]) -> TrialGrade:
    """Read a stored grade only when `verify_bundle` accepted it (an infrastructure stop is
    accepted: its per-check evidence is retained). Anything else is not trusted."""
    if problem_kinds - {INFRASTRUCTURE_STOP}:
        return _unusable(task, record, sorted(problem_kinds - {INFRASTRUCTURE_STOP})[0])
    grades = record.get("grades") if record else None
    status = grades.get("status") if isinstance(grades, dict) else None
    if status in (GRADE_GRADED, GRADE_INCOMPLETE):
        cases = tuple(CaseResult(c["id"], c.get("kind", ""), c["executed"], c["passed"],
                                 tuple(c["failures"]), c.get("actual")) for c in grades["checks"])
        return TrialGrade(task.id, task.category, grades["trial_status"], tuple(grades["labels"]),
                          grades["success"], grades["incomplete"], grades["infrastructure_status"], cases)
    infra = record.get("infrastructure_status") if record else None
    return _unusable(task, record or {}, infra or "grade_pending", infra)


def summarize_bundle(bundle_dir: str | Path, benchmark_path: str | Path) -> RunSummary:
    """Counts and rates over every planned trial, whatever the run's completeness.

    The benchmark must be the one the bundle recorded (hash and freeze, as for replay), since
    the planned denominators come from its tasks."""
    path = Path(bundle_dir)
    verification = verify_bundle(path)
    classification = classify_run(path, verification)
    manifest = load_manifest(path)
    _check_benchmark_identity(manifest, Path(benchmark_path))
    by_id = {task.id: task for task in load_benchmark(benchmark_path)}
    unknown = sorted({p["task_id"] for p in manifest["planned"]} - set(by_id))
    if unknown:
        raise BundleError(f"planned tasks are not in the benchmark: {', '.join(unknown)}")
    kinds: dict[str, set[str]] = {}
    for problem in verification.problems:
        if problem.trial_id:
            kinds.setdefault(problem.trial_id, set()).add(problem.kind)
    stopped = {t for t, k in kinds.items() if INFRASTRUCTURE_STOP in k}
    grades = []
    for planned in manifest["planned"]:
        trial_id = planned["trial_id"]
        record = load_trial(path, trial_id) if trial_id in verification.recorded else {}
        grades.append(_grade_from_record(by_id[planned["task_id"]], record, kinds.get(trial_id, set())))
    ungraded = [t for t in verification.grades_pending if t not in stopped]
    counts = count_results(grades)
    categories: dict[str, tuple[int, int]] = {}
    for grade in grades:
        won, total = categories.get(grade.category, (0, 0))
        categories[grade.category] = (won + grade.success, total + 1)
    return RunSummary(classification, counts, len(grades), sum(g.success for g in grades),
                      sum(g.incomplete for g in grades) - len(ungraded), len(ungraded), categories)
