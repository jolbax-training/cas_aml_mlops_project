"""Deterministic evaluator fixtures: strict comparison (Q23), per-check results, trial success,
and fixed-denominator accounting. Offline cases use stand-in runners; sandbox cases run real
candidates in Podman. Fixtures validate the evaluator, not model quality."""

import os
from pathlib import Path

import pytest

from codegen_eval.contract import ContractIssue
from codegen_eval.evaluate import _strict_equal, count_results, evaluate_task, grade_trial, score_case
from codegen_eval.limits import DEFAULT_LIMITS
from codegen_eval.sandbox import ExecutionResult, execute_check
from codegen_eval.tasks import Case, load_benchmark
from codegen_eval.trial import TrialResult

ROOT = Path(__file__).resolve().parents[1]
TASKS = {task.id: task for task in load_benchmark(ROOT / "data" / "benchmark_v1.json")}
VOWELS = TASKS["strings_01"]
ROTATE = TASKS["lists_02"]
GOOD = (ROOT / "data" / "references_v1" / "strings_01.py").read_text(encoding="utf-8")
HEAD = "def count_vowels(text: str) -> int:\n"
ROTATE_HEAD = "def rotate_left(items: list[int], k: int) -> list[int]:\n"


# --- strict recursive comparison (Q23) -------------------------------------------------

@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (1, True), (True, 1), (0, False), (False, 0),           # bool/int confusion
        (1.0, 1), (1, 1.0), ("1", 1), (1, "1"),                  # numeric and string confusion
        (None, 0), (None, ""), (None, []), (None, {}), (None, False), (0, None),  # null
        ([1, True], [1, 1]), ([[1, 2]], [[1, True]]),            # nested types
        ({"a": 1}, {"a": True}), ({"a": [1, 0]}, {"a": [1, False]}),
        ([1, 2, 3], [3, 2, 1]), ([[1], [2]], [[2], [1]]),        # list order
        ((1, 2), [1, 2]), ([1, 2], (1, 2)),                      # tuple is not list (in-process; the
        # sandbox encoder rejects a returned tuple as serialization_error, see the sandbox fixtures)
        ({"a": 1}, {"a": 1, "b": 2}), ({"a": 1, "b": 2}, {"a": 1}), ({"a": 1}, {"b": 1}),
        ([1], [1, 1]), ([], {}), ({}, []),
    ],
)
def test_strict_equal_rejects_type_and_order_differences(actual, expected):
    assert not _strict_equal(actual, expected)


@pytest.mark.parametrize(
    "value",
    [None, True, False, 0, -1, "", "x", [], [[], [1, [None]]], {}, {"a": {"b": [True, None]}}],
)
def test_strict_equal_accepts_identical_values(value):
    assert _strict_equal(value, value) and _strict_equal(value, __import__("copy").deepcopy(value))


def test_dictionary_key_order_does_not_matter_at_any_depth():
    assert _strict_equal({"a": 1, "b": {"x": [1], "y": None}}, {"b": {"y": None, "x": [1]}, "a": 1})


def test_value_nested_beyond_the_recursion_limit_is_unequal_not_an_error():
    def nest(depth):
        value: object = []
        for _ in range(depth):
            value = [value]
        return value

    # equal-shaped values force the comparison to recurse past the interpreter limit
    assert _strict_equal(nest(5000), nest(5000)) is False
    assert _strict_equal(nest(50), nest(50))


# --- per-check results and failure labels ----------------------------------------------

def returned(case, value=None, args_after=None):
    return ExecutionResult("returned", value=case.expected if value is None else value,
                           args_after=list(case.args) if args_after is None else args_after)


CASE = ROTATE.cases[0]  # args [[1, 2, 3, 4, 5], 2] -> [3, 4, 5, 1, 2]


def test_correct_check_passes_with_no_labels():
    result = score_case(CASE, returned(CASE))
    assert (result.executed, result.passed, result.failures) == (True, True, ())


def test_wrong_answer_and_mutation_are_recorded_together():
    result = score_case(CASE, returned(CASE, value=[1], args_after=[[9], 2]))
    assert (result.executed, result.passed) == (True, False)
    assert result.failures == ("wrong_answer", "mutated_input")


def test_correct_value_with_type_confused_argument_state_is_mutation():
    # args came back as a different type (for example [1] -> [True]) even though equal in Python
    result = score_case(CASE, returned(CASE, args_after=[[True, 2, 3, 4, 5], 2]))
    assert result.failures == ("mutated_input",)


def test_mutation_of_a_nested_argument_is_detected():
    case = TASKS["dictionaries_02"].cases[0]
    result = score_case(case, returned(case, args_after=[{"a": "x", "b": "y", "c": "x", "d": "z"}]))
    assert result.failures == ("mutated_input",)


@pytest.mark.parametrize(
    ("status", "executed"),
    [
        ("exception", True), ("timeout", True), ("output_limit", True), ("serialization_error", True),
        ("protocol_violation", True), ("candidate_crash", True),
        ("payload_too_large", False),
        ("infrastructure_error", False), ("protocol_error", False),
    ],
)
def test_non_returned_outcomes_are_one_unsuccessful_label_with_execution_flag(status, executed):
    result = score_case(CASE, ExecutionResult(status))
    assert (result.executed, result.passed, result.failures) == (executed, False, (status,))


# --- task-level fixtures (offline stand-in runners) ------------------------------------

def runner_for(behaviour):
    def runner(source, task, case):
        return behaviour(case)
    return runner


def test_correct_candidate_passes_all_four_checks():
    result = evaluate_task(VOWELS, GOOD, runner_for(returned))
    counts = count_results([result])
    assert result.passed and (counts.cases_passed, counts.edge_cases_passed, counts.cases_executed) == (4, 2, 4)


@pytest.mark.parametrize(("wrong_id", "kind"), [("strings_01_a", "ordinary"), ("strings_01_d", "edge")])
def test_wrong_ordinary_or_edge_case_fails_the_task_and_stays_visible(wrong_id, kind):
    result = evaluate_task(VOWELS, GOOD, runner_for(
        lambda case: returned(case, value=-1) if case.id == wrong_id else returned(case)))
    counts = count_results([result])
    bad = next(c for c in result.cases if c.id == wrong_id)
    assert not result.passed and bad.kind == kind and bad.failures == ("wrong_answer",)
    assert counts.cases_passed == 3 and counts.edge_cases_passed == (1 if kind == "edge" else 2)


@pytest.mark.parametrize(
    ("source", "label"),
    [
        ("def count_vowels(", "syntax_error"),
        ("", "contract_error"),
        ("```python\n" + GOOD + "```", "contract_error"),
        ("Here is the code:\n" + GOOD, "syntax_error"),
        ("def other(text: str) -> int:\n    return 0\n", "contract_error"),                 # name
        ("def count_vowels(text: str, extra: int) -> int:\n    return 0\n", "contract_error"),  # signature
        ("import numpy\n" + GOOD, "contract_error"),                                          # third party
        ("def helper():\n    pass\n" + GOOD, "contract_error"),                              # helper
        (GOOD + "print(1)\n", "contract_error"),                                              # top level
    ],
)
def test_contract_and_syntax_errors_leave_four_unexecuted_unsuccessful_checks(source, label):
    result = evaluate_task(VOWELS, source, runner_for(lambda case: pytest.fail("must not execute")))
    counts = count_results([result])
    assert not result.passed
    assert all(c.failures == (label,) and not c.executed and not c.passed for c in result.cases)
    assert (counts.cases_total, counts.cases_executed, counts.cases_passed) == (4, 0, 0)


def test_input_mutation_with_correct_values_fails_every_check():
    result = evaluate_task(ROTATE, ROTATE_HEAD + "    return []\n", runner_for(
        lambda case: returned(case, args_after=[[0], 0])))
    assert all("mutated_input" in c.failures for c in result.cases)
    assert not result.passed


def test_timeout_is_attempted_and_unsuccessful_without_hiding_other_checks():
    result = evaluate_task(VOWELS, GOOD, runner_for(
        lambda case: ExecutionResult("timeout") if case.id == "strings_01_c" else returned(case)))
    counts = count_results([result])
    assert result.cases[2].executed and not result.cases[2].passed and result.cases[2].failures == ("timeout",)
    assert (counts.cases_executed, counts.cases_passed, counts.infrastructure_failures) == (4, 3, 0)


def test_exception_and_excessive_output_count_as_candidate_failures():
    statuses = {"strings_01_a": "exception", "strings_01_b": "output_limit"}
    result = evaluate_task(VOWELS, GOOD, runner_for(
        lambda case: ExecutionResult(statuses[case.id]) if case.id in statuses else returned(case)))
    counts = count_results([result])
    assert [c.failures for c in result.cases[:2]] == [("exception",), ("output_limit",)]
    assert counts.infrastructure_failures == 0 and counts.cases_executed == 4


def test_payload_too_large_is_a_candidate_failure_that_is_unexecuted_within_the_denominator():
    result = evaluate_task(VOWELS, GOOD, runner_for(lambda case: ExecutionResult("payload_too_large")))
    counts = count_results([result])
    assert not result.passed and all(c.failures == ("payload_too_large",) for c in result.cases)
    assert (counts.cases_total, counts.cases_executed, counts.infrastructure_failures) == (4, 0, 0)


def test_infrastructure_failure_is_not_a_candidate_failure_and_marks_the_run_incomplete():
    result = evaluate_task(VOWELS, GOOD, runner_for(
        lambda case: ExecutionResult("infrastructure_error") if case.id == "strings_01_b" else returned(case)))
    counts = count_results([result])
    assert counts.infrastructure_failures == 1 and not counts.complete_for(expected_tasks=1)


# --- trial-level grading ---------------------------------------------------------------

def make_trial(status="submitted", *, label=None, submission=None, issue=None, infrastructure=None,
               drafts=(), tool_attempts=0, model_calls=1):
    return TrialResult(status, label, submission, issue, infrastructure, model_calls, tool_attempts,
                       drafts, (), (), "0" * 64, "baseline_agent_v1", "0" * 64)


def test_early_submission_without_tool_use_succeeds():
    grade = grade_trial(VOWELS, make_trial(submission=GOOD), runner_for(returned))
    assert grade.success and grade.passed and not grade.incomplete and grade.labels == ()
    assert count_results([grade]).cases_passed == 4


def test_tool_use_and_revisions_do_not_change_success():
    plain = grade_trial(VOWELS, make_trial(submission=GOOD), runner_for(returned))
    busy = grade_trial(VOWELS, make_trial(submission=GOOD, tool_attempts=3, model_calls=4), runner_for(returned))
    assert (busy.success, busy.cases, busy.labels) == (plain.success, plain.cases, plain.labels)


def test_one_failed_check_fails_the_trial_and_collects_distinct_labels():
    def behaviour(case):
        if case.id == "strings_01_a":
            return returned(case, value=-1, args_after=[""])
        if case.id == "strings_01_b":
            return ExecutionResult("timeout")
        return returned(case)
    grade = grade_trial(VOWELS, make_trial(submission=GOOD), runner_for(behaviour))
    assert not grade.success and not grade.incomplete
    assert grade.labels == ("wrong_answer", "mutated_input", "timeout")
    assert grade.cases[0].failures == ("wrong_answer", "mutated_input")


def test_contract_failure_in_a_trial_is_four_unexecuted_checks():
    trial = make_trial(submission="```x```", issue=ContractIssue("contract_error", "fences"))
    grade = grade_trial(VOWELS, trial, runner_for(lambda case: pytest.fail("must not execute")))
    assert not grade.success and grade.labels == ("contract_error",)
    assert all(not c.executed and c.failures == ("contract_error",) for c in grade.cases)
    assert count_results([grade]).cases_total == 4


def test_no_submission_is_four_unexecuted_checks_with_its_reason():
    for reason in ("request_rejected", "no_final_message", "tool_request_when_disabled", None):
        grade = grade_trial(VOWELS, make_trial("no_submission", label=reason),
                            runner_for(lambda case: pytest.fail("must not execute")))
        expected = ("no_submission",) + ((reason,) if reason else ())
        assert not grade.success and not grade.incomplete and grade.labels == expected
        assert all(not c.executed and not c.passed and c.failures == expected for c in grade.cases)
        counts = count_results([grade])
        assert (counts.cases_total, counts.cases_executed, counts.cases_passed) == (4, 0, 0)
        assert counts.infrastructure_failures == 0


def test_infrastructure_incomplete_trial_is_reported_incomplete_not_failed():
    grade = grade_trial(VOWELS, make_trial("infrastructure_incomplete", infrastructure="transport_exhausted"),
                        runner_for(lambda case: pytest.fail("must not execute")))
    assert grade.incomplete and not grade.success
    assert grade.infrastructure_status == "transport_exhausted"
    # the planned denominator is kept: four unexecuted, unsuccessful checks, never a smaller task
    assert [(c.executed, c.passed, c.failures) for c in grade.cases] == [(False, False, ("transport_exhausted",))] * 4


@pytest.mark.parametrize("status", ["transport_exhausted", "infrastructure_error", None])
def test_incomplete_trial_never_counts_as_a_complete_task(status):
    grade = grade_trial(VOWELS, make_trial("infrastructure_incomplete", infrastructure=status),
                        runner_for(lambda case: pytest.fail("must not execute")))
    counts = count_results([grade])
    assert (counts.tasks_total, counts.cases_total, counts.cases_executed, counts.cases_passed) == (1, 4, 0, 0)
    assert counts.tasks_incomplete == 1 and not counts.complete_for(expected_tasks=1)


def test_one_incomplete_trial_makes_a_run_of_complete_trials_incomplete():
    good = grade_trial(VOWELS, make_trial(submission=GOOD), runner_for(returned))
    bad = grade_trial(VOWELS, make_trial("infrastructure_incomplete", infrastructure="transport_exhausted"),
                      runner_for(returned))
    counts = count_results([good, bad])
    assert counts.complete_for(expected_tasks=2) is False
    assert count_results([good, good]).complete_for(expected_tasks=2) is True


def test_infrastructure_outcome_in_a_hidden_check_makes_the_trial_incomplete():
    grade = grade_trial(VOWELS, make_trial(submission=GOOD), runner_for(
        lambda case: ExecutionResult("protocol_error") if case.id == "strings_01_a" else returned(case)))
    assert grade.incomplete and not grade.success and grade.infrastructure_status == "protocol_error"


def test_payload_too_large_in_a_trial_is_a_candidate_failure_not_incomplete():
    grade = grade_trial(VOWELS, make_trial(submission=GOOD), runner_for(
        lambda case: ExecutionResult("payload_too_large")))
    assert not grade.success and not grade.incomplete
    assert grade.labels == ("payload_too_large",) and all(not c.executed for c in grade.cases)


@pytest.mark.parametrize("submission", ["```python\n" + GOOD + "```", "Here:\n" + GOOD, "def count_vowels(", ""])
def test_grade_trial_revalidates_the_submission_instead_of_trusting_a_stored_verdict(submission):
    trial = make_trial(submission=submission, issue=None)  # stale record: no stored contract issue
    grade = grade_trial(VOWELS, trial, runner_for(lambda case: pytest.fail("must not execute")))
    assert not grade.success and grade.labels in {("contract_error",), ("syntax_error",)}
    assert all(not c.executed for c in grade.cases)


def test_ungradable_trial_status_is_rejected():
    with pytest.raises(ValueError, match="cannot grade"):
        grade_trial(VOWELS, make_trial("unknown"), runner_for(returned))


def test_grading_runs_one_check_per_planned_case():
    seen = []

    def runner(source, task, case):
        seen.append(case.id)
        return returned(case)

    grade_trial(VOWELS, make_trial(submission=GOOD), runner)
    assert seen == [case.id for case in VOWELS.cases]


def test_the_sandbox_boundary_receives_arguments_but_never_expected_answers(monkeypatch):
    from codegen_eval import sandbox

    calls = []

    def fake_execute(source, function_name, args, limits):
        calls.append((source, function_name, args, limits))
        return ExecutionResult("returned", value=0, args_after=list(args))

    monkeypatch.setattr(sandbox, "execute_check", fake_execute)
    case = Case("c1", "edge", ("input",), "SECRET-EXPECTED-ANSWER")
    sandbox.run_case(GOOD, VOWELS, case)

    assert len(calls) == 1
    assert "SECRET-EXPECTED-ANSWER" not in repr(calls)
    assert calls[0][2] == ("input",)


# --- real candidates in the sandbox ----------------------------------------------------

SANDBOX_FIXTURES = {
    "correct": (GOOD, True, [()] * 4, 4),
    "wrong_ordinary": (HEAD + "    return 0\n", False, [("wrong_answer",), ("wrong_answer",), (), ("wrong_answer",)], 4),
    "exception": (HEAD + "    raise ValueError('x')\n", False, [("exception",)] * 4, 4),
    "timeout": (HEAD + "    while True:\n        pass\n", False, [("timeout",)] * 4, 4),
    "tuple_return": (HEAD + "    return tuple([0])\n", False, [("serialization_error",)] * 4, 4),
    "excessive_output": (HEAD + "    print('x' * 100000)\n    return 0\n", False, [("output_limit",)] * 4, 4),
}


@pytest.mark.sandbox
@pytest.mark.skipif(os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM")
@pytest.mark.parametrize("name", sorted(SANDBOX_FIXTURES))
def test_sandbox_fixture_accounting(name):
    source, success, failures, executed = SANDBOX_FIXTURES[name]
    fast = lambda s, task, case: execute_check(s, task.function_name, case.args, DEFAULT_LIMITS.with_deadline(3.0))
    result = evaluate_task(VOWELS, source, fast)
    assert result.passed is success
    assert [c.failures for c in result.cases] == failures
    assert count_results([result]).cases_executed == executed
    assert count_results([result]).infrastructure_failures == 0


@pytest.mark.sandbox
@pytest.mark.skipif(os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM")
def test_sandbox_mutation_and_payload_limit_fixtures():
    mutate = (ROTATE_HEAD + "    result = [items[(i + k) % len(items)] for i in range(len(items))]\n"
              "    items.append(0)\n    return result\n")
    mutated = evaluate_task(ROTATE, mutate)
    assert not mutated.passed
    assert [c.failures for c in mutated.cases] == [("mutated_input",)] * 4

    big = GOOD + "# " + "x" * 70_000 + "\n"
    oversized = evaluate_task(VOWELS, big)
    assert [c.failures for c in oversized.cases] == [("payload_too_large",)] * 4
    assert count_results([oversized]).cases_executed == 0


# --- recorded agent-trial fixtures graded end to end ------------------------------------

@pytest.mark.parametrize(
    ("scenario", "labels", "executed"),
    [
        ("request_rejected_on_call_3", ("no_submission", "request_rejected"), 0),
        ("no_final_message", ("no_submission", "no_final_message"), 0),
        ("tool_request_on_call_4", ("no_submission", "tool_request_when_disabled"), 0),
        ("fenced_final_source", ("contract_error",), 0),
        ("blank_final_message", ("contract_error",), 0),
    ],
)
def test_recorded_trials_without_a_valid_submission_grade_as_four_unexecuted_checks(
        scenario, labels, executed, inprocess_runner):
    grade = grade_recorded(scenario, inprocess_runner)
    assert not grade.success and not grade.incomplete and grade.labels == labels
    assert [c.executed for c in grade.cases] == [False] * 4 and executed == 0


def test_recorded_trials_with_a_valid_submission_grade_on_the_final_source_only(inprocess_runner):
    early = grade_recorded("early_submission", inprocess_runner)
    revised = grade_recorded("tool_use_and_revision", inprocess_runner)
    # The recorded final source is a naive lowercase scan: it passes "hello" and the empty string
    # but misses the accented cases, which the benchmark's hidden checks must expose.
    assert early.cases == revised.cases and not early.success
    assert [c.passed for c in early.cases] == [True, False, True, False]
    assert early.labels == ("wrong_answer",)


@pytest.mark.parametrize(
    ("scenario", "status"),
    [("transport_exhausted_on_call_2", "transport_exhausted"), ("container_unavailable", "infrastructure_error")],
)
def test_recorded_infrastructure_trials_are_incomplete(scenario, status, inprocess_runner):
    def failing(source, function_name, args, limits=None):
        return ExecutionResult("infrastructure_error", detail="podman unavailable")

    grade = grade_recorded(scenario, failing if scenario == "container_unavailable" else inprocess_runner)
    assert grade.incomplete and not grade.success and grade.infrastructure_status == status


def grade_recorded(scenario, inprocess_runner):
    from codegen_eval.model_client import FixtureClient, load_fixtures
    from codegen_eval.trial import run_trial

    scenarios = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")
    trial = run_trial(VOWELS, FixtureClient.from_data(scenarios[scenario]), runner=inprocess_runner)
    return grade_trial(VOWELS, trial, lambda source, task, case: inprocess_runner(source, task.function_name, case.args))
