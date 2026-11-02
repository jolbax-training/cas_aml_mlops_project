"""Run one bounded agent trial: a fresh conversation, an optional development tool,
and one explicit final submission that is validated but never repaired.

Terminal states: `submitted` (final message present; it may still fail the source
contract), `no_submission`, and `infrastructure_incomplete`."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from codegen_eval.agent_config import (
    DEFAULT_AGENT_LIMITS, AgentLimits, AgentPrompt, load_prompt,
)
from codegen_eval.contract import ContractIssue, validate_source
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.model_client import (
    REQUEST_REJECTED, ModelClient, ModelFailure, ModelRequest, ModelResponse, ToolCall,
)
from codegen_eval.run_checks import TOOL_NAME, TOOL_SCHEMA, ToolResult, run_checks
from codegen_eval.sandbox import ExecutionResult, execute_check
from codegen_eval.tasks import Task

SUBMITTED = "submitted"
NO_SUBMISSION = "no_submission"
INFRASTRUCTURE_INCOMPLETE = "infrastructure_incomplete"


@dataclass(frozen=True)
class Draft:
    """A candidate sent to run_checks, kept with the attempt that produced it."""

    attempt: int
    source: str
    result: dict[str, Any]


@dataclass(frozen=True)
class TrialResult:
    status: str
    label: str | None                     # e.g. "request_rejected" for a no_submission
    submission: str | None                # final message exactly as returned
    contract_issue: ContractIssue | None  # set when a submission failed the source contract
    infrastructure_status: str | None
    model_calls: int                      # logical calls consumed, including a rejected one
    tool_attempts: int
    drafts: tuple[Draft, ...]
    messages: tuple[dict[str, Any], ...]  # full conversation, retained for inspection
    events: tuple[dict[str, Any], ...]    # controller trace: calls, tool handling, terminal state
    limits_hash: str
    prompt_version: str
    prompt_sha256: str

    @property
    def contract_valid(self) -> bool:
        return self.status == SUBMITTED and self.contract_issue is None


@dataclass
class _State:
    messages: list[dict[str, Any]]
    events: list[dict[str, Any]] = field(default_factory=list)
    drafts: list[Draft] = field(default_factory=list)
    model_calls: int = 0
    tool_attempts: int = 0


def _initial_messages(task: Task, prompt: AgentPrompt, user_suffix: str = "") -> list[dict[str, Any]]:
    # Instruction and typed signature only; hidden cases are never read here. The optional
    # suffix is for the smoke command only; experiment runs never pass one.
    user = f"{task.instruction}\n\nFunction signature: def {task.signature}"
    if user_suffix:
        user += f"\n\n{user_suffix}"
    return [{"role": "system", "content": prompt.text}, {"role": "user", "content": user}]


def _assistant_message(response: ModelResponse) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": response.content}
    if response.tool_calls:
        message["tool_calls"] = [{"id": c.id, "name": c.name, "arguments": c.arguments}
                                 for c in response.tool_calls]
    return message


def _tool_message(call: ToolCall, feedback: dict[str, Any]) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call.id, "content": json.dumps(feedback)}


def run_trial(
    task: Task,
    client: ModelClient,
    *,
    prompt: AgentPrompt | None = None,
    limits: AgentLimits = DEFAULT_AGENT_LIMITS,
    execution_limits: ExecutionLimits = DEFAULT_LIMITS,
    runner: Callable[..., ExecutionResult] = execute_check,
    user_suffix: str = "",
) -> TrialResult:
    """Run one trial. `runner` executes one development check (see `execute_check`);
    `user_suffix` (smoke only) is appended to the first user message."""
    prompt = prompt or load_prompt()
    state = _State(_initial_messages(task, prompt, user_suffix))

    def finish(status: str, *, label: str | None = None, submission: str | None = None,
               issue: ContractIssue | None = None, infrastructure: str | None = None) -> TrialResult:
        state.events.append({"event": "trial_end", "status": status, "label": label,
                             "infrastructure_status": infrastructure})
        return TrialResult(status, label, submission, issue, infrastructure, state.model_calls,
                           state.tool_attempts, tuple(state.drafts),
                           tuple(state.messages), tuple(state.events), limits.config_hash(),
                           prompt.version, prompt.sha256)

    while state.model_calls < limits.max_model_calls:
        state.model_calls += 1
        # The last call is reserved for final submission; so is any call once the
        # tool allowance is spent.
        tools_enabled = (state.model_calls < limits.max_model_calls
                         and state.tool_attempts < limits.max_tool_attempts)
        request = ModelRequest(tuple(state.messages), (TOOL_SCHEMA,) if tools_enabled else (),
                               "auto" if tools_enabled else "none")
        response = client.complete(request)
        event: dict[str, Any] = {"event": "model_call", "call": state.model_calls,
                                 "tools_enabled": tools_enabled, "outcome": _outcome(response)}
        if isinstance(response, ModelFailure):
            event["detail"] = response.detail
        else:
            event["truncated"] = response.truncated
            event["usage"] = response.usage
        state.events.append(event)

        if isinstance(response, ModelFailure):
            if response.kind == REQUEST_REJECTED:
                # The rejected call is consumed; no further calls are made.
                return finish(NO_SUBMISSION, label=REQUEST_REJECTED)
            # Any other failure (for example exhausted transport retries) is
            # infrastructure, not agent performance; partial evidence is kept.
            return finish(INFRASTRUCTURE_INCOMPLETE, infrastructure=response.kind)

        state.messages.append(_assistant_message(response))

        if response.tool_calls:
            if not tools_enabled:
                # Tool request despite tools being disabled: no explicit submission.
                return finish(NO_SUBMISSION, label="tool_request_when_disabled")
            stop = _handle_tool_calls(response, state, task, limits, execution_limits, runner)
            if stop is not None:
                return finish(INFRASTRUCTURE_INCOMPLETE, infrastructure=stop)
            continue

        if response.content is None:
            return finish(NO_SUBMISSION, label="no_final_message")

        issue = validate_source(response.content, task)
        if issue is not None:
            state.events.append({"event": "contract_failure", "code": issue.code})
        return finish(SUBMITTED, submission=response.content, issue=issue)

    raise AssertionError("unreachable: the last call always ends the trial")


def _outcome(response: ModelResponse | ModelFailure) -> str:
    if isinstance(response, ModelFailure):
        return response.kind
    return "tool_calls" if response.tool_calls else "message"


def _handle_tool_calls(response: ModelResponse, state: _State, task: Task, limits: AgentLimits,
                       execution_limits: ExecutionLimits,
                       runner: Callable[..., ExecutionResult]) -> str | None:
    """Apply the multi-part rule; returns an infrastructure status if the trial must stop.

    One response is one attempted tool call, however many calls it carries. Only the first
    `run_checks` call executes; every other call gets argument-error feedback in the same
    turn. Content alongside tool calls is not a final submission."""
    state.tool_attempts += 1
    executing = next((c for c in response.tool_calls if c.name == TOOL_NAME), None)
    extras = [c for c in response.tool_calls if c is not executing]
    state.events.append({"event": "tool_attempt", "attempt": state.tool_attempts,
                         "calls_in_response": len(response.tool_calls),
                         "executed": executing.id if executing else None,
                         "rejected_extras": [c.id for c in extras]})

    result: ToolResult | None = None
    if executing is not None:
        result = run_checks(executing.arguments, task, runner, limits, execution_limits)
        if result.source is not None:
            state.drafts.append(Draft(state.tool_attempts, result.source, result.feedback()))

    for call in response.tool_calls:
        if call is executing:
            if result.infrastructure:
                continue  # the trial ends; no feedback is sent
            state.messages.append(_tool_message(call, result.feedback()))
        elif call.name != TOOL_NAME:
            state.messages.append(_tool_message(call, {"ok": False,
                                                       "error": f"unknown tool {call.name[:50]!r}"}))
        else:
            state.messages.append(_tool_message(call, {
                "ok": False, "error": "only one run_checks call per response is executed; "
                                      "this call was not run"}))
    return result.infrastructure if result is not None else None
