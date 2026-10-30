"""The `run_checks` development tool: agent-authored checks executed in the sandbox.

Only the function name and signature of the task are used here; hidden acceptance cases
are never read, so they cannot appear in feedback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from codegen_eval.agent_config import AgentLimits, DEFAULT_AGENT_LIMITS
from codegen_eval.contract import validate_source
from codegen_eval.evaluate import _strict_equal
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.sandbox import INFRASTRUCTURE_STATUSES, ExecutionResult, execute_check
from codegen_eval.tasks import Task

TOOL_NAME = "run_checks"
TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Run your candidate function on example checks you write yourself and "
                       "see whether it returns the values you expect.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Candidate Python source."},
                "checks": {
                    "type": "array",
                    "description": "Example checks, run independently.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "arguments": {"type": "array", "description": "Positional arguments."},
                            "expected": {"description": "Expected return value (JSON)."},
                        },
                        "required": ["arguments", "expected"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["source", "checks"],
            "additionalProperties": False,
        },
    },
}

MAX_VALUE_CHARS = 300   # per reported actual value
MAX_DETAIL_CHARS = 300  # per diagnostic
MAX_ERROR_CHARS = 300

# Statuses where the candidate (not the container) is at fault, reported to the agent.
_CANDIDATE_MESSAGES = {
    "exception": "the function raised {detail}",
    "timeout": "the check exceeded the execution deadline",
    "payload_too_large": "source and arguments exceed the payload limit",
    "output_limit": "the function printed too much output",
    "serialization_error": "the return value or arguments cannot be serialised to JSON",
    "protocol_violation": "the function interfered with the worker's report",
    "candidate_crash": "the function crashed the worker (for example by exhausting memory)",
}


@dataclass(frozen=True)
class CheckFeedback:
    index: int
    passed: bool
    actual: str | None = None  # bounded JSON text of the returned value
    failures: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class ToolResult:
    """Outcome of one attempted run_checks call."""

    ok: bool                       # request was valid and checks were run
    error: str = ""                # argument or source error (nothing executed for argument errors)
    checks: tuple[CheckFeedback, ...] = ()
    infrastructure: str | None = None  # infrastructure status that stopped the call, if any
    source: str | None = None      # candidate source when it was text, retained as a draft

    def feedback(self) -> dict[str, Any]:
        """JSON-ready, bounded feedback for the model."""
        if self.error:
            return {"ok": False, "error": self.error[:MAX_ERROR_CHARS]}
        if self.infrastructure:
            return {"ok": False, "infrastructure": self.infrastructure,
                    "checks": [{"index": c.index, "passed": c.passed} for c in self.checks]}
        return {
            "ok": True,
            "checks": [
                {"index": c.index, "passed": c.passed,
                 **({"actual": c.actual} if c.actual is not None else {}),
                 **({"failures": list(c.failures)} if c.failures else {}),
                 **({"detail": c.detail} if c.detail else {})}
                for c in self.checks
            ],
        }


def _bounded(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _argument_error(message: str, source: str | None = None) -> ToolResult:
    return ToolResult(False, error=message, source=source)


def parse_request(raw_arguments: str, limits: AgentLimits,
                  max_bytes: int) -> tuple[str, list[dict[str, Any]]] | str:
    """Validate raw tool arguments. Returns (source, checks) or an error message."""
    if len(raw_arguments.encode("utf-8", "replace")) > max_bytes:
        return f"arguments exceed the {max_bytes}-byte payload limit; none were run"
    try:
        data = json.loads(raw_arguments)
    except (ValueError, RecursionError):
        return "arguments are not valid JSON"
    if not isinstance(data, dict) or set(data) != {"source", "checks"}:
        return "arguments must be an object with exactly 'source' and 'checks'"
    if not isinstance(data["source"], str):
        return "'source' must be a string"
    checks = data["checks"]
    if not isinstance(checks, list) or not checks:
        return "'checks' must be a non-empty list"
    if len(checks) > limits.max_checks_per_request:
        return (f"too many checks: {len(checks)} requested, at most "
                f"{limits.max_checks_per_request} are allowed; none were run")
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or set(check) != {"arguments", "expected"}:
            return f"check {index} must be an object with exactly 'arguments' and 'expected'"
        if not isinstance(check["arguments"], list):
            return f"check {index}: 'arguments' must be a list"
    return data["source"], checks


def run_checks(
    raw_arguments: str,
    task: Task,
    runner: Callable[..., ExecutionResult] = execute_check,
    limits: AgentLimits = DEFAULT_AGENT_LIMITS,
    execution_limits: ExecutionLimits = DEFAULT_LIMITS,
) -> ToolResult:
    """Validate one tool request and run its checks, comparing in trusted code.

    `runner` has the signature of `execute_check` (source, function_name, args, limits)."""
    parsed = parse_request(raw_arguments, limits, execution_limits.payload_bytes)
    if isinstance(parsed, str):
        return _argument_error(parsed)
    source, checks = parsed

    issue = validate_source(source, task)
    if issue is not None:
        return _argument_error(f"{issue.code}: {issue.detail}", source)

    feedback: list[CheckFeedback] = []
    for index, check in enumerate(checks):
        args = check["arguments"]
        execution = runner(source, task.function_name, args, execution_limits)
        if execution.status in INFRASTRUCTURE_STATUSES:
            return ToolResult(False, checks=tuple(feedback), infrastructure=execution.status, source=source)
        feedback.append(_check_feedback(index, args, check["expected"], execution))
    return ToolResult(True, checks=tuple(feedback), source=source)


def _check_feedback(index: int, args: Sequence[Any], expected: Any, execution: ExecutionResult) -> CheckFeedback:
    if execution.status != "returned":
        template = _CANDIDATE_MESSAGES.get(execution.status, "the check failed: {detail}")
        detail = _bounded(template.format(detail=execution.detail or execution.status), MAX_DETAIL_CHARS)
        return CheckFeedback(index, False, failures=(execution.status,), detail=detail)
    failures = []
    if not _strict_equal(execution.value, expected):
        failures.append("wrong_answer")
    if not _strict_equal(execution.args_after, list(args)):
        failures.append("mutated_input")
    actual = _bounded(json.dumps(execution.value, ensure_ascii=False), MAX_VALUE_CHARS)
    return CheckFeedback(index, not failures, actual, tuple(failures))
