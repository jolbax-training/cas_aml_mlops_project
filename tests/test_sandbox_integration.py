import os
from pathlib import Path

import pytest

from codegen_eval.evaluate import count_results, evaluate_task
from codegen_eval.sandbox import run_case
from codegen_eval.tasks import load_tasks


pytestmark = [pytest.mark.sandbox, pytest.mark.skipif(
    os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM"
)]
PILOT = Path(__file__).resolve().parents[1] / "data" / "pilot_tasks.json"
TASKS = load_tasks(PILOT, {"strings": 1, "lists": 1, "dictionaries": 1})


def test_restricted_container_returns_a_value():
    source = "def count_vowels(text: str) -> int:\n    return 2\n"
    result = run_case(source, TASKS[0], TASKS[0].cases[0])

    assert result.status == "returned"
    assert result.value == 2
    assert result.args_after == ["hello"]


def test_complete_task_uses_trusted_scoring_after_container_calls():
    source = '''import unicodedata

def count_vowels(text: str) -> int:
    normalized = unicodedata.normalize("NFD", text).casefold()
    return sum(char in "aeiou" for char in normalized)
'''
    result = evaluate_task(TASKS[0], source)

    assert result.passed
    assert count_results([result]).cases_passed == 4
    assert count_results([result]).edge_cases_passed == 2


def test_wrong_candidate_keeps_per_case_failure_evidence():
    source = "def count_vowels(text: str) -> int:\n    return 0\n"
    result = evaluate_task(TASKS[0], source)

    assert not result.passed
    assert [case.failures for case in result.cases] == [
        ("wrong_answer",), ("wrong_answer",), (), ("wrong_answer",)
    ]


def test_mutation_is_observable_outside_the_container():
    source = "def unique_in_order(items: list[int]) -> list[int]:\n    items.pop()\n    return []\n"
    result = run_case(source, TASKS[1], TASKS[1].cases[0])

    assert result.status == "returned"
    assert result.args_after == [[3, 1, 3, 2]]


def test_correct_return_does_not_hide_input_mutation():
    source = '''def unique_in_order(items: list[int]) -> list[int]:
    items[:] = list(dict.fromkeys(items))
    return items
'''
    result = evaluate_task(TASKS[1], source)

    assert not result.passed
    assert result.cases[0].failures == ("mutated_input",)
    assert result.cases[1].failures == ("mutated_input",)
    assert result.cases[2].passed
    assert result.cases[3].failures == ("mutated_input",)


def test_container_cannot_read_project_or_host_environment_or_reach_network():
    source = '''import os
import socket

def count_vowels(text: str) -> int:
    project_file = "/Users/jolbax/Developer/devspace/cas_aml_mlops_project/data/pilot_tasks.json"
    if os.path.exists(project_file) or "CODEGEN_EVAL_TEST_SECRET" in os.environ:
        return -1
    try:
        open("/etc/codegen-eval-probe", "w")
    except OSError:
        pass
    else:
        return -3
    try:
        socket.create_connection(("1.1.1.1", 80), timeout=0.2)
    except OSError:
        return 2
    return -2
'''
    result = run_case(source, TASKS[0], TASKS[0].cases[0])

    assert result.status == "returned"
    assert result.value == 2


def test_infinite_loop_is_stopped_by_timeout():
    source = "def count_vowels(text: str) -> int:\n    while True:\n        pass\n"
    result = run_case(source, TASKS[0], TASKS[0].cases[0], timeout_seconds=1.0)

    assert result.status == "timeout"


def test_large_print_output_is_bounded():
    source = "def count_vowels(text: str) -> int:\n    print('x' * 40000)\n    return 2\n"
    result = run_case(source, TASKS[0], TASKS[0].cases[0])

    assert result.status == "output_limit"
