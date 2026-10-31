import json
import os
from pathlib import Path

import pytest

from codegen_eval.agent_config import AgentLimits
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.run_checks import TOOL_SCHEMA
from codegen_eval.sandbox import ExecutionResult
from sandbox_support import generous_limits
from codegen_eval.tasks import Case, Task, load_tasks
from codegen_eval.trial import run_trial

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = load_fixtures(Path(__file__).parent / "fixtures" / "agent" / "trials.json")
BASE = load_tasks(ROOT / "data" / "pilot_tasks.json", {"strings": 1, "lists": 1, "dictionaries": 1})[0]
# Hidden data that must never reach the model, the tool, or the trace.
HIDDEN = Case("hidden_01", "edge", ("HIDDEN-INPUT-7f3a",), 987654321)
TASK = Task(BASE.id, BASE.category, BASE.function_name, BASE.signature, BASE.instruction, (HIDDEN,))


def trial(name, runner, **kwargs):
    client = FixtureClient.from_data(SCENARIOS[name])
    return run_trial(TASK, client, runner=runner, **kwargs), client


def tool_feedback(client, call):
    """Parsed content of the tool message(s) the controller sent on a given 1-based call."""
    messages = client.requests[call - 1].messages
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


def test_early_submission_without_tools_is_graded_normally(inprocess_runner):
    result, client = trial("early_submission", inprocess_runner)

    assert result.status == "submitted" and result.contract_valid
    assert result.model_calls == 1 and result.tool_attempts == 0 and result.drafts == ()
    assert result.submission == SCENARIOS["early_submission"]["responses"][0]["content"]
    assert len(client.requests) == 1


def test_trial_starts_from_instruction_signature_and_versioned_prompt_only(inprocess_runner):
    result, client = trial("early_submission", inprocess_runner)
    first = client.requests[0]

    assert [m["role"] for m in first.messages] == ["system", "user"]
    assert BASE.instruction in first.messages[1]["content"]
    assert f"def {BASE.signature}" in first.messages[1]["content"]
    assert first.tools == (TOOL_SCHEMA,) and first.tool_choice == "auto"
    assert result.prompt_version == "baseline_agent_v1" and len(result.limits_hash) == 64


def test_two_trials_do_not_share_conversation_state(inprocess_runner):
    first, _ = trial("tool_use_and_revision", inprocess_runner)
    second, client = trial("early_submission", inprocess_runner)

    assert len(first.drafts) == 2 and second.drafts == ()
    assert len(client.requests[0].messages) == 2


def test_tool_use_and_revision_keeps_both_drafts_in_one_trial(inprocess_runner):
    result, client = trial("tool_use_and_revision", inprocess_runner)

    assert result.status == "submitted" and result.model_calls == 3 and result.tool_attempts == 2
    assert [d.attempt for d in result.drafts] == [1, 2]
    first = tool_feedback(client, 2)[0]
    assert first["ok"] and [c["passed"] for c in first["checks"]] == [False, True]
    assert first["checks"][0]["actual"] == "0"
    second = tool_feedback(client, 3)[1]
    assert [c["passed"] for c in second["checks"]] == [True, True]


def test_malformed_arguments_consume_an_attempt_then_recover(inprocess_runner):
    result, client = trial("malformed_then_recovery", inprocess_runner)

    assert result.tool_attempts == 2 and result.status == "submitted"
    assert tool_feedback(client, 2)[0]["ok"] is False
    assert tool_feedback(client, 3)[1]["ok"] is True
    assert len(result.drafts) == 1  # the malformed attempt had no source to retain


def test_oversized_batch_runs_nothing_and_consumes_the_attempt():
    def runner(*args):
        raise AssertionError("no check may execute")

    result, client = trial("oversized_batch", runner)

    assert result.tool_attempts == 1 and result.drafts == ()
    feedback = tool_feedback(client, 2)[0]
    assert not feedback["ok"] and "none were run" in feedback["error"]


def test_fourth_call_is_sent_with_tools_disabled_and_may_submit(inprocess_runner):
    result, client = trial("fourth_call_submission", inprocess_runner)

    assert result.status == "submitted" and result.model_calls == 4 and result.tool_attempts == 3
    assert [r.tool_choice for r in client.requests] == ["auto", "auto", "auto", "none"]
    assert [bool(r.tools) for r in client.requests] == [True, True, True, False]


def test_tool_request_on_call_four_is_no_submission_and_nothing_runs(inprocess_runner):
    result, client = trial("tool_request_on_call_4", inprocess_runner)

    assert result.status == "no_submission" and result.label == "tool_request_when_disabled"
    assert result.contract_issue is None and result.submission is None
    assert result.model_calls == 4 and result.tool_attempts == 3 and len(result.drafts) == 3
    assert len(client.requests) == 4
    assert result.messages[-1]["tool_calls"][0]["id"] == "t4"  # retained for inspection


def test_absent_final_message_is_no_submission(inprocess_runner):
    result, _ = trial("no_final_message", inprocess_runner)

    assert result.status == "no_submission" and result.label == "no_final_message"


def test_blank_final_message_is_a_contract_failure(inprocess_runner):
    result, client = trial("blank_final_message", inprocess_runner)

    assert result.status == "submitted" and result.contract_issue.code == "contract_error"
    assert len(client.requests) == 1


def test_transport_exhaustion_is_infrastructure_incomplete_with_the_trace_kept(inprocess_runner):
    result, client = trial("transport_exhausted_on_call_2", inprocess_runner)

    assert result.status == "infrastructure_incomplete"
    assert result.infrastructure_status == "transport_exhausted"
    assert result.submission is None and result.contract_issue is None
    assert result.model_calls == 2 and result.tool_attempts == 1 and len(result.drafts) == 1
    assert len(result.messages) == 4 and len(client.requests) == 2
    failed = [e for e in result.events if e["event"] == "model_call"][-1]
    assert failed["outcome"] == "transport_exhausted" and "retries used up" in failed["detail"]


def test_truncation_and_usage_are_visible_in_the_trace_and_never_retried(inprocess_runner):
    result, client = trial("truncated_final_source", inprocess_runner)

    call = next(e for e in result.events if e["event"] == "model_call")
    assert call["truncated"] is True and call["usage"] == {"completion_tokens": 2000}
    assert result.status == "submitted" and result.contract_issue.code == "syntax_error"
    assert len(client.requests) == 1


def test_rejection_detail_is_recorded(inprocess_runner):
    result, _ = trial("request_rejected_on_call_3", inprocess_runner)

    call = [e for e in result.events if e["event"] == "model_call"][-1]
    assert call["outcome"] == "request_rejected" and "12,000" in call["detail"]


def test_oversized_raw_arguments_are_rejected_before_parsing(inprocess_runner):
    def runner(*args):
        raise AssertionError("no check may execute")

    result, client = trial("oversized_arguments", runner)

    assert result.tool_attempts == 1 and result.drafts == ()
    feedback = tool_feedback(client, 2)[0]
    assert not feedback["ok"] and "payload limit" in feedback["error"]


def test_pre_send_rejection_ends_the_trial_as_candidate_side_no_submission(inprocess_runner):
    result, client = trial("request_rejected_on_call_3", inprocess_runner)

    assert result.status == "no_submission" and result.label == "request_rejected"
    assert result.infrastructure_status is None
    assert result.model_calls == 3 and len(client.requests) == 3  # rejected call consumed, none after
    assert len(result.drafts) == 2


def test_multiple_tool_calls_count_as_one_attempt_and_run_only_the_first(inprocess_runner):
    executed = []

    def runner(source, name, args, limits=None):
        executed.append(list(args))
        return inprocess_runner(source, name, args, limits)

    result, client = trial("multiple_tool_calls", runner)

    assert result.tool_attempts == 1 and executed == [["hello"]]
    feedback = tool_feedback(client, 2)
    assert [f["ok"] for f in feedback] == [True, False, False]
    assert "not run" in feedback[1]["error"] and "unknown tool" in feedback[2]["error"]
    event = next(e for e in result.events if e["event"] == "tool_attempt")
    assert event["calls_in_response"] == 3 and event["executed"] == "t1"
    assert event["rejected_extras"] == ["t2", "t3"]
    assert result.status == "submitted"


def test_content_alongside_a_tool_call_is_not_a_submission(inprocess_runner):
    result, client = trial("content_with_tool_call", inprocess_runner)

    assert result.tool_attempts == 1 and result.model_calls == 2
    assert result.messages[2]["content"] is not None  # the early content is kept in the trace
    assert result.status == "submitted" and len(client.requests) == 2


@pytest.mark.parametrize("name, code", [
    ("fenced_final_source", "contract_error"),
    ("prose_final_message", "syntax_error"),
    ("disallowed_construct_final", "contract_error"),
])
def test_invalid_final_source_is_a_recorded_contract_failure_without_repair(name, code, inprocess_runner):
    result, client = trial(name, inprocess_runner)

    assert result.status == "submitted" and not result.contract_valid
    assert result.contract_issue.code == code
    assert result.submission == SCENARIOS[name]["responses"][0]["content"]  # unchanged
    assert len(client.requests) == 1  # no regeneration


def test_candidate_exception_feedback_allows_recovery(inprocess_runner):
    result, client = trial("candidate_exception", inprocess_runner)

    failing = tool_feedback(client, 2)[0]["checks"][0]
    assert not failing["passed"] and "AttributeError" in failing["detail"]
    assert result.status == "submitted" and result.contract_valid and result.tool_attempts == 2


def test_invalid_tool_source_consumes_an_attempt_and_is_retained(inprocess_runner):
    result, client = trial("invalid_source_in_tool", inprocess_runner)

    assert result.tool_attempts == 1 and len(result.drafts) == 1
    assert "syntax_error" in tool_feedback(client, 2)[0]["error"]


@pytest.mark.parametrize("status", ["infrastructure_error", "protocol_error"])
def test_container_or_protocol_failure_is_infrastructure_incomplete(status):
    def runner(source, name, args, limits=None):
        return ExecutionResult(status, detail="podman unavailable")

    result, client = trial("container_unavailable", runner)

    assert result.status == "infrastructure_incomplete" and result.infrastructure_status == status
    assert result.submission is None and result.contract_issue is None
    assert result.tool_attempts == 1 and len(result.drafts) == 1 and len(client.requests) == 1
    assert result.events[-1]["infrastructure_status"] == status


def test_candidate_side_execution_statuses_are_not_infrastructure(inprocess_runner):
    def runner(source, name, args, limits=None):
        return ExecutionResult("timeout")

    result, _ = trial("tool_use_and_revision", runner)

    assert result.status == "submitted"


def test_limits_are_configurable_and_recorded(inprocess_runner):
    limits = AgentLimits(max_model_calls=2, max_tool_attempts=1, max_checks_per_request=4)
    result, client = trial("tool_use_and_revision", inprocess_runner, limits=limits)

    # call 2 is the last call, so tools are disabled and the scripted tool request ends the trial
    assert [r.tool_choice for r in client.requests] == ["auto", "none"]
    assert result.status == "no_submission" and result.model_calls == 2
    assert result.limits_hash == limits.config_hash() != AgentLimits().config_hash()


def test_tools_are_disabled_once_the_tool_allowance_is_spent(inprocess_runner):
    limits = AgentLimits(max_model_calls=4, max_tool_attempts=1)
    result, client = trial("fourth_call_submission", inprocess_runner, limits=limits)

    assert [r.tool_choice for r in client.requests] == ["auto", "none"]
    assert result.status == "no_submission"


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_hidden_acceptance_data_never_reaches_the_model_or_the_trace(name, inprocess_runner):
    result, client = trial(name, inprocess_runner)
    seen = json.dumps([[dict(m) for m in r.messages] + [list(r.tools)] for r in client.requests])
    seen += json.dumps(result.messages) + json.dumps(result.events)

    for secret in ("HIDDEN-INPUT-7f3a", "987654321", "hidden_01"):
        assert secret not in seen


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_trial_stays_within_the_limits(name, inprocess_runner):
    result, client = trial(name, inprocess_runner)

    assert result.model_calls <= 4 and result.tool_attempts <= 3
    assert len(client.requests) == result.model_calls
    assert all(len(d.result.get("checks", [])) <= 4 for d in result.drafts)


@pytest.mark.skipif(os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM")
@pytest.mark.sandbox
def test_development_checks_run_through_the_real_container_path():
    client = FixtureClient.from_data(SCENARIOS["tool_use_and_revision"])
    result = run_trial(TASK, client, execution_limits=generous_limits())

    assert result.status == "submitted" and result.contract_valid
    first = tool_feedback(client, 2)[0]
    assert [c["passed"] for c in first["checks"]] == [False, True]
    assert [c["passed"] for c in tool_feedback(client, 3)[1]["checks"]] == [True, True]
