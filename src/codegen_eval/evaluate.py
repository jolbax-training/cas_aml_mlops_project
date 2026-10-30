"""Score generated functions while keeping expected answers outside the sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable

from codegen_eval.contract import validate_source
from codegen_eval.sandbox import INFRASTRUCTURE_STATUSES, ExecutionResult, run_case
from codegen_eval.tasks import Case, Task

if TYPE_CHECKING:
    from codegen_eval.trial import TrialResult

# Candidate outcomes that start no container, so the check is not executed.
UNEXECUTED_CANDIDATE_STATUSES = frozenset({"payload_too_large"})


@dataclass(frozen=True)
class CaseResult:
    id: str
    kind: str
    executed: bool
    passed: bool
    failures: tuple[str, ...]
    actual: Any = None


@dataclass(frozen=True)
class TaskResult:
    id: str
    category: str
    passed: bool
    cases: tuple[CaseResult, ...]


@dataclass(frozen=True)
class RunCounts:
    tasks_total: int
    tasks_passed: int
    cases_total: int
    cases_executed: int
    cases_passed: int
    edge_cases_total: int
    edge_cases_passed: int
    infrastructure_failures: int
    tasks_incomplete: int = 0  # graded trials an infrastructure outcome made unreliable

    @property
    def task_pass_rate(self) -> float:
        return self.tasks_passed / self.tasks_total if self.tasks_total else 0.0

    @property
    def case_pass_rate(self) -> float:
        """Use all planned cases, including ones blocked by invalid source."""
        return self.cases_passed / self.cases_total if self.cases_total else 0.0

    @property
    def edge_case_pass_rate(self) -> float:
        return self.edge_cases_passed / self.edge_cases_total if self.edge_cases_total else 0.0

    def complete_for(self, expected_tasks: int) -> bool:
        return (self.tasks_total == expected_tasks and self.infrastructure_failures == 0
                and self.tasks_incomplete == 0)


def _strict_equal(actual: Any, expected: Any) -> bool:
    """Recursive type-aware equality over JSON values: `True` is not `1`, `1.0` is not `1`,
    list order matters, and dictionary key order does not."""
    try:
        return _equal(actual, expected)
    except RecursionError:
        return False  # a value nested deeper than the interpreter allows cannot match


def _equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _equal(actual[key], value) for key, value in expected.items()
        )
    return actual == expected


def score_case(case: Case, execution: ExecutionResult) -> CaseResult:
    """Grade one raw execution outcome against its trusted case (also used to regrade stored outcomes).

    A returned value can carry both `wrong_answer` and `mutated_input`. Every other candidate
    outcome is a single label and counts as executed, including a `timeout`, which is an
    attempted and unsuccessful check. `payload_too_large` starts no container, so that check
    is unexecuted and unsuccessful. Infrastructure outcomes are unexecuted and not candidate
    failures."""
    if execution.status == "returned":
        failures: list[str] = []
        if not _strict_equal(execution.value, case.expected):
            failures.append("wrong_answer")
        if not _strict_equal(execution.args_after, list(case.args)):
            failures.append("mutated_input")
        return CaseResult(case.id, case.kind, True, not failures, tuple(failures), execution.value)

    executed = execution.status not in INFRASTRUCTURE_STATUSES | UNEXECUTED_CANDIDATE_STATUSES
    return CaseResult(case.id, case.kind, executed, False, (execution.status,))


def _unexecuted(task: Task, labels: tuple[str, ...]) -> tuple[CaseResult, ...]:
    return tuple(CaseResult(case.id, case.kind, False, False, labels) for case in task.cases)


def evaluate_task(
    task: Task,
    source: str,
    runner: Callable[[str, Task, Case], ExecutionResult] = run_case,
) -> TaskResult:
    """Validate once, then score all four cases with separate execution calls."""
    issue = validate_source(source, task)
    if issue is not None:
        results = _unexecuted(task, (issue.code,))
    else:
        results = tuple(score_case(case, runner(source, task, case)) for case in task.cases)
    return TaskResult(task.id, task.category, all(case.passed for case in results), results)


@dataclass(frozen=True)
class TrialGrade:
    """Grade of one agent trial's final submission. `cases` always lists the planned checks
    (four), so scores keep their full denominator. An `incomplete` trial reports them as
    unexecuted and unsuccessful with the infrastructure status as the label; it is never a
    complete task (`count_results(...).complete_for` is false) and is not a candidate failure."""

    task_id: str
    category: str
    status: str                       # the trial's terminal state
    labels: tuple[str, ...]           # trial-level labels, e.g. ("no_submission", "request_rejected")
    success: bool
    incomplete: bool                  # an infrastructure outcome made grading unreliable
    infrastructure_status: str | None
    cases: tuple[CaseResult, ...]

    @property
    def passed(self) -> bool:
        return self.success


def grade_trial(
    task: Task,
    trial: "TrialResult",
    runner: Callable[[str, Task, Case], ExecutionResult] = run_case,
) -> TrialGrade:
    """Grade a finished trial's final submission only; tool use, revisions, latency, and
    cost never affect success.

    A submission that fails the source contract (`contract_error`, `syntax_error`) and a
    `no_submission` (with its reason label, such as `request_rejected`) mark all four checks
    unexecuted and unsuccessful. A trial that ended in `infrastructure_incomplete`, or whose
    hidden checks hit an infrastructure outcome, is reported incomplete rather than failed (its
    four checks stay in the planned denominator, unexecuted);
    whether and how an incomplete run is excluded is decided by the run-level classification."""
    from codegen_eval.trial import INFRASTRUCTURE_INCOMPLETE, NO_SUBMISSION, SUBMITTED

    def grade(status, labels, success, incomplete, infrastructure, cases):
        return TrialGrade(task.id, task.category, status, labels, success, incomplete,
                          infrastructure, cases)

    if trial.status == INFRASTRUCTURE_INCOMPLETE:
        status = trial.infrastructure_status or INFRASTRUCTURE_INCOMPLETE
        return grade(trial.status, (), False, True, status, _unexecuted(task, (status,)))
    if trial.status == NO_SUBMISSION:
        labels = ("no_submission",) + ((trial.label,) if trial.label else ())
        return grade(trial.status, labels, False, False, None, _unexecuted(task, labels))
    if trial.status != SUBMITTED or trial.submission is None:
        raise ValueError(f"cannot grade trial with status {trial.status!r}")
    # Re-validate rather than trust a stored verdict: a rebuilt record could be stale.
    issue = trial.contract_issue or validate_source(trial.submission, task)
    if issue is not None:
        labels = (issue.code,)
        return grade(trial.status, labels, False, False, None, _unexecuted(task, labels))

    cases = tuple(score_case(case, runner(trial.submission, task, case)) for case in task.cases)
    infrastructure = next((f for c in cases for f in c.failures if f in INFRASTRUCTURE_STATUSES), None)
    labels = tuple(dict.fromkeys(f for c in cases for f in c.failures))
    return grade(trial.status, labels, infrastructure is None and all(c.passed for c in cases),
                 infrastructure is not None, infrastructure, cases)


def count_results(results: Iterable[TaskResult]) -> RunCounts:
    """Return explicit counts; case-rate denominator policy is decided separately."""
    tasks = tuple(results)
    cases = tuple(case for task in tasks for case in task.cases)
    return RunCounts(
        tasks_total=len(tasks),
        tasks_passed=sum(task.passed for task in tasks),
        cases_total=len(cases),
        cases_executed=sum(case.executed for case in cases),
        cases_passed=sum(case.passed for case in cases),
        edge_cases_total=sum(case.kind == "edge" for case in cases),
        edge_cases_passed=sum(case.kind == "edge" and case.passed for case in cases),
        infrastructure_failures=sum(
            any(failure in INFRASTRUCTURE_STATUSES for failure in case.failures)
            for case in cases
        ),
        tasks_incomplete=sum(getattr(task, "incomplete", False) for task in tasks),
    )
