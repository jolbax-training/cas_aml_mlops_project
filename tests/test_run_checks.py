import json
from pathlib import Path

from codegen_eval.agent_config import AgentLimits
from codegen_eval.run_checks import MAX_VALUE_CHARS, TOOL_SCHEMA, run_checks
from codegen_eval.sandbox import ExecutionResult
from codegen_eval.tasks import Case, Task, load_tasks

PILOT = Path(__file__).resolve().parents[1] / "data" / "pilot_tasks.json"
TASK = load_tasks(PILOT, {"strings": 1, "lists": 1, "dictionaries": 1})[0]
GOOD = "def count_vowels(text: str) -> int:\n    return sum(1 for ch in text.lower() if ch in 'aeiou')\n"


def request(source=GOOD, checks=({"arguments": ["hello"], "expected": 2},)):
    return json.dumps({"source": source, "checks": list(checks)})


def test_passing_and_failing_checks_report_actual_values(inprocess_runner):
    result = run_checks(request(checks=[{"arguments": ["hello"], "expected": 2},
                                        {"arguments": ["hello"], "expected": 3}]),
                        TASK, inprocess_runner)

    assert result.ok
    assert [c.passed for c in result.checks] == [True, False]
    assert result.checks[1].actual == "2" and result.checks[1].failures == ("wrong_answer",)


def test_comparison_is_strict_and_detects_mutation(inprocess_runner):
    mutating = ("def count_vowels(text: str) -> int:\n    return True\n")
    result = run_checks(request(mutating, [{"arguments": ["a"], "expected": 1}]), TASK, inprocess_runner)
    assert result.checks[0].failures == ("wrong_answer",)  # True is not 1

    def mutator(source, name, args, limits=None):
        return ExecutionResult("returned", value=1, args_after=["changed"])
    result = run_checks(request(checks=[{"arguments": ["a"], "expected": 1}]), TASK, mutator)
    assert result.checks[0].failures == ("mutated_input",)


def test_candidate_exception_is_bounded_feedback(inprocess_runner):
    source = "def count_vowels(text: str) -> int:\n    return text.nope()\n"
    result = run_checks(request(source), TASK, inprocess_runner)

    assert result.ok and not result.checks[0].passed
    assert "AttributeError" in result.checks[0].detail


def test_request_validation_runs_nothing():
    calls = []

    def runner(*args):
        calls.append(args)
        return ExecutionResult("returned", value=0, args_after=[])

    bad_requests = [
        "{not json", "[]", json.dumps({"source": GOOD}), json.dumps({"source": 1, "checks": []}),
        request(checks=[]),
        request(checks=[{"arguments": ["a"], "expected": 0}] * 5),
        request(checks=[{"arguments": "a", "expected": 0}]),
        request(checks=[{"arguments": ["a"]}]),
    ]
    for raw in bad_requests:
        result = run_checks(raw, TASK, runner)
        assert not result.ok and result.error and not result.checks
    assert calls == []


def test_oversized_batch_message_states_nothing_ran():
    result = run_checks(request(checks=[{"arguments": ["a"], "expected": 0}] * 5), TASK,
                        lambda *a: None, AgentLimits(max_checks_per_request=4))

    assert "none were run" in result.error


def test_invalid_source_is_reported_without_execution_and_kept_as_a_draft():
    result = run_checks(request("```python\n" + GOOD + "```"), TASK, lambda *a: 1 / 0)

    assert not result.ok and "contract_error" in result.error
    assert result.source is not None


def test_infrastructure_status_stops_the_call():
    runs = []

    def runner(source, name, args, limits=None):
        runs.append(args)
        return ExecutionResult("infrastructure_error", detail="podman missing")

    result = run_checks(request(checks=[{"arguments": ["a"], "expected": 0}] * 2), TASK, runner)

    assert result.infrastructure == "infrastructure_error"
    assert len(runs) == 1


def test_actual_values_and_diagnostics_are_bounded():
    def runner(source, name, args, limits=None):
        return ExecutionResult("returned", value="x" * 10_000, args_after=list(args))

    result = run_checks(request(checks=[{"arguments": ["a"], "expected": 0}]), TASK, runner)
    assert len(result.checks[0].actual) < MAX_VALUE_CHARS + 50

    def noisy(source, name, args, limits=None):
        return ExecutionResult("output_limit", detail="y" * 10_000)
    result = run_checks(request(checks=[{"arguments": ["a"], "expected": 0}]), TASK, noisy)
    assert len(json.dumps(result.feedback())) < 1_000


def test_hidden_cases_never_appear_in_feedback_or_tool_schema(inprocess_runner):
    hidden = Case("secret_case", "edge", ("HIDDEN-INPUT-7f3a",), 987654321)
    task = Task(TASK.id, TASK.category, TASK.function_name, TASK.signature, TASK.instruction, (hidden,))

    result = run_checks(request(checks=[{"arguments": ["hello"], "expected": 3}]), task, inprocess_runner)
    text = json.dumps(result.feedback()) + json.dumps(TOOL_SCHEMA)

    assert "HIDDEN-INPUT-7f3a" not in text and "987654321" not in text and "secret_case" not in text
