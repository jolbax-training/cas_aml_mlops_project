"""Load and validate the benchmark before it is used for scoring."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


BENCHMARK_SCHEMA_VERSION = 1
BENCHMARK_CATEGORIES = {
    "strings": 2,
    "lists": 2,
    "dictionaries": 2,
    "numeric_logic": 2,
    "parsing_formatting": 2,
}


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


def _matches(value: Any, annotation: ast.expr | None) -> bool:
    """Check a JSON value against a signature annotation, keeping bool and int distinct."""
    if isinstance(annotation, ast.Constant) and annotation.value is None:
        return value is None
    if isinstance(annotation, ast.Name):
        if annotation.id == "bool":
            return isinstance(value, bool)
        if annotation.id == "int":
            return isinstance(value, int) and not isinstance(value, bool)
        if annotation.id == "str":
            return isinstance(value, str)
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        container, inner = annotation.value.id, annotation.slice
        if container == "list":
            return isinstance(value, list) and all(_matches(item, inner) for item in value)
        if container == "dict" and isinstance(inner, ast.Tuple) and len(inner.elts) == 2:
            key_type, value_type = inner.elts
            return isinstance(value, dict) and all(
                _matches(key, key_type) and _matches(item, value_type) for key, item in value.items()
            )
    raise ValueError(f"unsupported annotation: {ast.unparse(annotation) if annotation else None}")


def _check_case_shape(case_id: str, signature: str, args: list[Any], expected: Any) -> None:
    function = ast.parse(f"def {signature}:\n    pass\n").body[0]
    parameters = function.args.args
    if (function.args.posonlyargs or function.args.vararg or function.args.kwarg
            or function.args.kwonlyargs or function.args.defaults):
        raise ValueError(f"{signature!r} may only use plain positional parameters")
    if len(args) != len(parameters):
        raise ValueError(f"{case_id} has {len(args)} args but the signature takes {len(parameters)}")
    for parameter, value in zip(parameters, args):
        if parameter.annotation is None:
            raise ValueError(f"{signature!r} parameter {parameter.arg!r} must have an annotation")
        if not _matches(value, parameter.annotation):
            raise ValueError(f"{case_id} argument {parameter.arg!r} does not match its annotation")
    if function.returns is None:
        raise ValueError(f"{signature!r} must have a return annotation")
    if not _matches(expected, function.returns):
        raise ValueError(f"{case_id} expected value does not match the return annotation")


def load_tasks(path: str | Path, expected_categories: Mapping[str, int]) -> tuple[Task, ...]:
    """Load a benchmark and check its structure, counts, and identifiers."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return _build_tasks(raw, expected_categories)


def load_benchmark(path: str | Path) -> tuple[Task, ...]:
    """Load the versioned ten-task benchmark: five categories, two tasks each, four cases each."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    envelope = _object(raw, {"schema_version", "benchmark_version", "tasks"}, "benchmark")
    if envelope["schema_version"] != BENCHMARK_SCHEMA_VERSION:
        raise ValueError(f"unsupported benchmark schema version: {envelope['schema_version']!r}")
    _text(envelope["benchmark_version"], "benchmark version")
    return _build_tasks(envelope["tasks"], BENCHMARK_CATEGORIES)


def _build_tasks(raw: Any, expected_categories: Mapping[str, int]) -> tuple[Task, ...]:
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
            _check_case_shape(case_id, signature, case["args"], case["expected"])
            cases.append(Case(case_id, kind, tuple(case["args"]), case["expected"]))
            kinds[kind] += 1
        if kinds != Counter({"ordinary": 2, "edge": 2}):
            raise ValueError(f"{task_id} needs two ordinary and two edge cases")

        categories[category] += 1
        tasks.append(Task(task_id, category, function_name, signature, instruction, tuple(cases)))

    if categories != Counter(expected_categories):
        raise ValueError(f"category counts {dict(categories)} differ from {dict(expected_categories)}")
    return tuple(tasks)


FREEZE_FILE = "data/benchmark_v1.freeze.json"
FROZEN_PATTERNS = ("data/benchmark_v1.json", "data/references_v1/**/*", "docs/benchmark_review.md")


def frozen_files(root: str | Path) -> list[str]:
    """Repository-relative paths covered by the benchmark content hash, sorted."""
    root = Path(root)
    return sorted({path.relative_to(root).as_posix() for pattern in FROZEN_PATTERNS
                   for path in root.glob(pattern)
                   if path.is_file() and "__pycache__" not in path.parts})


def freeze_manifest(root: str | Path) -> dict[str, Any]:
    """Version, per-file SHA-256, and one content hash over the benchmark, references, and review.

    The content hash is the SHA-256 of one `<path>\\t<file sha256>\\n` line per file, in path
    order, so it changes when any file is edited, added, or removed. The manifest itself is
    not hashed; it records the result."""
    root = Path(root)
    benchmark = json.loads((root / "data" / "benchmark_v1.json").read_text(encoding="utf-8"))
    files = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in frozen_files(root)}
    canonical = "".join(f"{path}\t{digest}\n" for path, digest in files.items())
    return {
        "schema_version": benchmark["schema_version"],
        "benchmark_version": benchmark["benchmark_version"],
        "files": files,
        "content_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def check_freeze(root: str | Path) -> None:
    """Raise ValueError naming the differences if the recorded freeze no longer matches the files."""
    root = Path(root)
    recorded = json.loads((root / FREEZE_FILE).read_text(encoding="utf-8"))
    current = freeze_manifest(root)
    if recorded == current:
        return
    changed = sorted(path for path in set(recorded["files"]) | set(current["files"])
                     if recorded["files"].get(path) != current["files"].get(path))
    raise ValueError(
        f"benchmark content differs from the recorded freeze ({recorded['content_hash']}); "
        f"changed files: {changed or 'none (version fields differ)'}; create a new benchmark "
        "version and re-record the freeze instead of editing a frozen version"
    )
