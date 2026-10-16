from pathlib import Path

from codegen_eval.evaluate import count_results, evaluate_task
from codegen_eval.sandbox import ExecutionResult
from codegen_eval.tasks import load_tasks


PILOT = Path(__file__).resolve().parents[1] / "data" / "pilot_tasks.json"
TASKS = load_tasks(PILOT, {"strings": 1, "lists": 1, "dictionaries": 1})
VOWELS = "def count_vowels(text: str) -> int:\n    return 0\n"
UNIQUE = "def unique_in_order(items: list[int]) -> list[int]:\n    return []\n"


def correct_runner(source, task, case):
    return ExecutionResult("returned", value=case.expected, args_after=list(case.args))


def test_known_correct_result_passes_every_case():
    result = evaluate_task(TASKS[0], VOWELS, correct_runner)

    assert result.passed
    assert count_results([result]).cases_passed == 4
    assert count_results([result]).edge_cases_passed == 2


def test_ordinary_failure_remains_visible_alongside_passing_cases():
    def runner(source, task, case):
        value = -1 if case.id == "strings_01_a" else case.expected
        return ExecutionResult("returned", value=value, args_after=list(case.args))

    result = evaluate_task(TASKS[0], VOWELS, runner)

    assert not result.passed
    assert result.cases[0].failures == ("wrong_answer",)
    assert count_results([result]).cases_passed == 3
    assert count_results([result]).edge_cases_passed == 2


def test_mutation_and_wrong_answer_can_both_be_recorded():
    def runner(source, task, case):
        if case.id == "lists_01_a":
            return ExecutionResult("returned", value=[], args_after=[[999]])
        return ExecutionResult("returned", value=case.expected, args_after=list(case.args))

    result = evaluate_task(TASKS[1], UNIQUE, runner)

    assert not result.passed
    assert result.cases[0].failures == ("wrong_answer", "mutated_input")


def test_syntax_error_marks_all_cases_unexecuted_without_calling_runner():
    def forbidden_runner(source, task, case):
        raise AssertionError("invalid source must not execute")

    result = evaluate_task(TASKS[0], "def count_vowels(", forbidden_runner)
    counts = count_results([result])

    assert not result.passed
    assert counts.cases_total == 4
    assert counts.cases_executed == 0
    assert counts.case_pass_rate == 0.0
    assert all(case.failures == ("syntax_error",) for case in result.cases)


def test_exception_and_timeout_are_distinct_failure_types():
    def runner(source, task, case):
        if case.id == "strings_01_a":
            return ExecutionResult("exception", detail="ValueError")
        if case.id == "strings_01_b":
            return ExecutionResult("timeout")
        return ExecutionResult("returned", value=case.expected, args_after=list(case.args))

    result = evaluate_task(TASKS[0], VOWELS, runner)

    assert result.cases[0].failures == ("exception",)
    assert result.cases[1].failures == ("timeout",)
    assert count_results([result]).cases_executed == 4


def test_infrastructure_failure_is_counted_separately():
    def runner(source, task, case):
        if case.id == "strings_01_a":
            return ExecutionResult("infrastructure_error")
        return ExecutionResult("returned", value=case.expected, args_after=list(case.args))

    result = evaluate_task(TASKS[0], VOWELS, runner)
    counts = count_results([result])

    assert counts.infrastructure_failures == 1
    assert counts.cases_executed == 3
    assert not counts.complete_for(expected_tasks=1)
