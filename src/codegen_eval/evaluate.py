"""Score generated functions while keeping expected answers outside the sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from codegen_eval.contract import validate_source
from codegen_eval.sandbox import ExecutionResult, run_case
from codegen_eval.tasks import Case, Task


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
        return self.tasks_total == expected_tasks and self.infrastructure_failures == 0


def _strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _strict_equal(actual[key], value) for key, value in expected.items()
        )
    return actual == expected


def _score_case(case: Case, execution: ExecutionResult) -> CaseResult:
    if execution.status == "returned":
        failures: list[str] = []
        if not _strict_equal(execution.value, case.expected):
            failures.append("wrong_answer")
        if not _strict_equal(execution.args_after, list(case.args)):
            failures.append("mutated_input")
        return CaseResult(case.id, case.kind, True, not failures, tuple(failures), execution.value)

    infrastructure = execution.status in {"infrastructure_error", "protocol_error"}
    return CaseResult(case.id, case.kind, not infrastructure, False, (execution.status,))


def evaluate_task(
    task: Task,
    source: str,
    runner: Callable[[str, Task, Case], ExecutionResult] = run_case,
) -> TaskResult:
    """Validate once, then score all four cases with separate execution calls."""
    issue = validate_source(source, task)
    if issue is not None:
        results = tuple(CaseResult(case.id, case.kind, False, False, (issue.code,))
                        for case in task.cases)
    else:
        results = tuple(_score_case(case, runner(source, task, case)) for case in task.cases)
    return TaskResult(task.id, task.category, all(case.passed for case in results), results)


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
            any(failure in {"infrastructure_error", "protocol_error"} for failure in case.failures)
            for case in cases
        ),
    )
