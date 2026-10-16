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
