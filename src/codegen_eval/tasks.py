"""Load and validate the benchmark before it is used for scoring."""

from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    args: tuple[Any, ...]
    expected: Any


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    function_name: str
    signature: str
    instruction: str
    cases: tuple[Case, ...]


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must have exactly these fields: {sorted(keys)}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _check_signature(signature: str, function_name: str) -> None:
    try:
        module = ast.parse(f"def {signature}:\n    pass\n")
    except SyntaxError as error:
        raise ValueError(f"invalid signature {signature!r}") from error
    if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
        raise ValueError(f"invalid signature {signature!r}")
    if module.body[0].name != function_name:
        raise ValueError("signature and function_name disagree")


def load_tasks(path: str | Path, expected_categories: Mapping[str, int]) -> tuple[Task, ...]:
    """Load a benchmark and check its structure, counts, and identifiers."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("benchmark must be a list of tasks")

    tasks: list[Task] = []
    task_ids: set[str] = set()
    case_ids: set[str] = set()
    categories: Counter[str] = Counter()
    task_keys = {"id", "category", "function_name", "signature", "instruction", "cases"}
    case_keys = {"id", "kind", "args", "expected"}

    for raw_task in raw:
        item = _object(raw_task, task_keys, "task")
        task_id = _text(item["id"], "task id")
        if task_id in task_ids:
            raise ValueError(f"duplicate task id: {task_id}")
        task_ids.add(task_id)

        category = _text(item["category"], "category")
        function_name = _text(item["function_name"], "function name")
        if not function_name.isidentifier():
            raise ValueError(f"invalid function name: {function_name}")
        signature = _text(item["signature"], "signature")
        _check_signature(signature, function_name)
        instruction = _text(item["instruction"], "instruction")

        raw_cases = item["cases"]
        if not isinstance(raw_cases, list) or len(raw_cases) != 4:
            raise ValueError(f"{task_id} must have four cases")
        cases: list[Case] = []
        kinds: Counter[str] = Counter()
        for raw_case in raw_cases:
            case = _object(raw_case, case_keys, "case")
            case_id = _text(case["id"], "case id")
            if case_id in case_ids:
                raise ValueError(f"duplicate case id: {case_id}")
            case_ids.add(case_id)
            kind = case["kind"]
            if kind not in {"ordinary", "edge"}:
                raise ValueError(f"invalid case kind: {kind!r}")
            if not isinstance(case["args"], list):
                raise ValueError(f"{case_id} args must be a list")
            cases.append(Case(case_id, kind, tuple(case["args"]), case["expected"]))
            kinds[kind] += 1
        if kinds != Counter({"ordinary": 2, "edge": 2}):
            raise ValueError(f"{task_id} needs two ordinary and two edge cases")

        categories[category] += 1
        tasks.append(Task(task_id, category, function_name, signature, instruction, tuple(cases)))

    if categories != Counter(expected_categories):
        raise ValueError(f"category counts {dict(categories)} differ from {dict(expected_categories)}")
    return tuple(tasks)
