import json
from pathlib import Path

import pytest

from codegen_eval.tasks import load_tasks


PILOT = Path(__file__).resolve().parents[1] / "data" / "pilot_tasks.json"
EXPECTED_CATEGORIES = {"strings": 1, "lists": 1, "dictionaries": 1}


def test_pilot_has_three_tasks_and_twelve_cases():
    tasks = load_tasks(PILOT, EXPECTED_CATEGORIES)

    assert len(tasks) == 3
    assert sum(len(task.cases) for task in tasks) == 12
    assert all({case.kind for case in task.cases} == {"ordinary", "edge"} for task in tasks)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data[1].update(id=data[0]["id"]), "duplicate task id"),
        (lambda data: data[1]["cases"][0].update(id=data[0]["cases"][0]["id"]), "duplicate case id"),
        (lambda data: data[0]["cases"][0].update(kind="edge"), "two ordinary and two edge"),
        (lambda data: data[0].update(signature="different(text: str) -> int"), "signature and function_name"),
    ],
)
def test_invalid_benchmark_is_rejected(tmp_path, change, message):
    data = json.loads(PILOT.read_text(encoding="utf-8"))
    change(data)
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_tasks(broken, EXPECTED_CATEGORIES)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data[0]["cases"][0].update(args=["a", "b"]), "has 2 args but the signature takes 1"),
        (lambda data: data[0]["cases"][0].update(args=[5]), "argument 'text' does not match"),
        (lambda data: data[1]["cases"][0].update(args=[[1, True]]), "argument 'items' does not match"),
        (lambda data: data[1]["cases"][0].update(args=[[1, 2.0]]), "argument 'items' does not match"),
        (lambda data: data[0]["cases"][0].update(expected=True), "expected value does not match"),
        (lambda data: data[0]["cases"][0].update(expected=2.0), "expected value does not match"),
        (lambda data: data[2]["cases"][0].update(expected={"a": "2"}), "expected value does not match"),
        (lambda data: data[0].update(signature="count_vowels(*texts: str) -> int"), "plain positional"),
        (lambda data: data[0].update(signature="count_vowels(text: bytes) -> int"), "unsupported annotation"),
    ],
)
def test_case_values_must_match_the_signature(tmp_path, change, message):
    data = json.loads(PILOT.read_text(encoding="utf-8"))
    change(data)
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_tasks(broken, EXPECTED_CATEGORIES)
