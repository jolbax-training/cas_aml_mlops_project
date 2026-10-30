import copy
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from codegen_eval.contract import validate_source
from codegen_eval.evaluate import _strict_equal, count_results, evaluate_task
from codegen_eval.tasks import (
    BENCHMARK_CATEGORIES, FREEZE_FILE, check_freeze, load_benchmark, load_tasks,
)


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
REFERENCES = ROOT / "data" / "references_v1"
TASKS = load_benchmark(BENCHMARK)


def test_benchmark_has_ten_tasks_in_five_balanced_categories_and_forty_cases():
    assert len(TASKS) == 10
    assert Counter(task.category for task in TASKS) == Counter(BENCHMARK_CATEGORIES)
    assert sum(len(task.cases) for task in TASKS) == 40
    assert sum(case.kind == "edge" for task in TASKS for case in task.cases) == 20
    assert len({case.id for task in TASKS for case in task.cases}) == 40


def test_pilot_tasks_are_reused_with_unchanged_cases():
    pilot = load_tasks(ROOT / "data" / "pilot_tasks.json", {"strings": 1, "lists": 1, "dictionaries": 1})
    reviewed = {task.id: task for task in TASKS}

    assert [reviewed[task.id].cases for task in pilot] == [task.cases for task in pilot]
    # lists_01 and dictionaries_01 instructions were reviewed and kept; strings_01 was corrected.
    assert [reviewed[task.id].instruction == task.instruction for task in pilot] == [False, True, True]


def _write(tmp_path, change):
    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _drop_task(data):
    data["tasks"].pop()


def _swap_category(data):
    data["tasks"][0]["category"] = "lists"


def _extra_task(data):
    extra = copy.deepcopy(data["tasks"][0])
    extra["id"] = "strings_03"
    for case in extra["cases"]:
        case["id"] = case["id"].replace("strings_01", "strings_03")
    data["tasks"].append(extra)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_drop_task, "category counts"),
        (_swap_category, "category counts"),
        (_extra_task, "category counts"),
        (lambda data: data["tasks"][1].update(id=data["tasks"][0]["id"]), "duplicate task id"),
        (lambda data: data["tasks"][1]["cases"][0].update(id=data["tasks"][0]["cases"][0]["id"]), "duplicate case id"),
        (lambda data: data["tasks"][3]["cases"].pop(), "must have four cases"),
        (lambda data: data["tasks"][3]["cases"][2].update(kind="ordinary"), "two ordinary and two edge"),
        (lambda data: data["tasks"][3]["cases"][2].update(kind="hard"), "invalid case kind"),
        (lambda data: data["tasks"][3]["cases"][0].update(args=[[1], 2, 3]), "has 3 args"),
        (lambda data: data["tasks"][3]["cases"][0].update(args=[[1], "2"]), "argument 'k' does not match"),
        (lambda data: data["tasks"][3]["cases"][0].update(expected=[1.5]), "expected value does not match"),
        (lambda data: data["tasks"][3].update(function_name="other"), "signature and function_name"),
        (lambda data: data.update(schema_version=2), "unsupported benchmark schema version"),
        (lambda data: data.update(benchmark_version=""), "benchmark version"),
        (lambda data: data.pop("benchmark_version"), "benchmark must have exactly these fields"),
        (lambda data: data["tasks"][0].pop("instruction"), "task must have exactly these fields"),
    ],
)
def test_invalid_benchmark_is_rejected_with_a_diagnostic(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        load_benchmark(_write(tmp_path, change))


def test_every_task_has_one_reference_solution():
    assert {path.stem for path in REFERENCES.glob("*.py")} == {task.id for task in TASKS}


@pytest.mark.parametrize("task", TASKS, ids=lambda task: task.id)
def test_reference_satisfies_the_source_contract_and_all_four_cases(task):
    source = (REFERENCES / f"{task.id}.py").read_text(encoding="utf-8")
    assert validate_source(source, task) is None

    namespace: dict = {}
    exec(compile(source, f"{task.id}.py", "exec"), namespace)  # trusted reference code
    function = namespace[task.function_name]
    for case in task.cases:
        args = copy.deepcopy(list(case.args))
        actual = function(*args)
        assert _strict_equal(actual, case.expected), case.id
        assert _strict_equal(args, list(case.args)), f"{case.id} mutated its input"


@pytest.mark.sandbox
@pytest.mark.skipif(os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM")
def test_references_pass_every_case_in_the_sandbox():
    results = [
        evaluate_task(task, (REFERENCES / f"{task.id}.py").read_text(encoding="utf-8")) for task in TASKS
    ]

    counts = count_results(results)
    assert all(result.passed for result in results)
    assert (counts.tasks_passed, counts.cases_passed, counts.edge_cases_passed) == (10, 40, 20)
    assert counts.infrastructure_failures == 0


def test_recorded_freeze_matches_the_benchmark_and_review_files():
    check_freeze(ROOT)
    manifest = json.loads((ROOT / FREEZE_FILE).read_text(encoding="utf-8"))
    assert manifest["benchmark_version"] == "1" and len(manifest["content_hash"]) == 64
    assert set(manifest["files"]) == {
        "data/benchmark_v1.json", "docs/benchmark_review.md",
        *(f"data/references_v1/{task.id}.py" for task in TASKS),
    }


def _copy_frozen_tree(tmp_path):
    for relative in [FREEZE_FILE, *json.loads((ROOT / FREEZE_FILE).read_text())["files"]]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    return tmp_path


@pytest.mark.parametrize(
    "edit",
    [
        lambda root: _append(root / "data" / "benchmark_v1.json", " "),
        lambda root: _append(root / "data" / "references_v1" / "lists_02.py", "# edited\n"),
        lambda root: _append(root / "docs" / "benchmark_review.md", "\n"),
        lambda root: (root / "data" / "references_v1" / "lists_02.py").unlink(),
        lambda root: (root / "data" / "references_v1" / "extra.py").write_text("x = 1\n"),
    ],
)
def test_any_edit_to_a_frozen_file_is_reported(tmp_path, edit):
    root = _copy_frozen_tree(tmp_path)
    check_freeze(root)
    edit(root)
    with pytest.raises(ValueError, match="differs from the recorded freeze"):
        check_freeze(root)


def _append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")
