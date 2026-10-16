"""Check generated source without executing it."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass

from codegen_eval.tasks import Task


@dataclass(frozen=True)
class ContractIssue:
    code: str
    detail: str


def _same_ast(left: ast.AST | None, right: ast.AST | None) -> bool:
    if left is None or right is None:
        return left is right
    return ast.dump(left) == ast.dump(right)


def validate_source(source: str, task: Task) -> ContractIssue | None:
    """Return a syntax or contract issue, or None for structurally valid source."""
    if not isinstance(source, str) or not source.strip():
        return ContractIssue("contract_error", "empty or non-text response")
    if "```" in source:
        return ContractIssue("contract_error", "Markdown fences are disallowed")
    try:
        module = ast.parse(source)
    except SyntaxError as error:
        return ContractIssue("syntax_error", str(error))

    functions = [node for node in module.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        return ContractIssue("contract_error", "expected exactly one top-level function")
    if any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)) for node in module.body):
        return ContractIssue("contract_error", "top-level statements may only be imports or the function")

    function = functions[0]
    if function.decorator_list:
        return ContractIssue("contract_error", "decorators are disallowed")
    if function.name != task.function_name:
        return ContractIssue("contract_error", "function name does not match the task")
    expected = ast.parse(f"def {task.signature}:\n    pass\n").body[0]
    if not _same_ast(function.args, expected.args) or not _same_ast(function.returns, expected.returns):
        return ContractIssue("contract_error", "function signature does not match the task")

    for node in ast.walk(module):
        if node is not function and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return ContractIssue("contract_error", "helper functions and async functions are disallowed")
        if isinstance(node, ast.ClassDef):
            return ContractIssue("contract_error", "classes are disallowed")
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return ContractIssue("contract_error", "relative imports are disallowed")
            roots = [(node.module or "").split(".", 1)[0]]
        else:
            continue
        if any(root not in sys.stdlib_module_names for root in roots):
            return ContractIssue("contract_error", "third-party imports are disallowed")

    return None
