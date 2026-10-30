from pathlib import Path

import pytest

from codegen_eval.agent_config import AgentLimits, DEFAULT_AGENT_LIMITS, load_prompt
from codegen_eval.model_client import (
    FixtureClient, FixtureExhausted, ModelFailure, ModelRequest, ModelResponse, ToolCall,
    load_fixtures,
)

FIXTURES = Path(__file__).parent / "fixtures" / "agent" / "trials.json"


def request():
    return ModelRequest(({"role": "user", "content": "x"},), (), "none")


def test_fixture_client_replays_responses_in_order_and_records_requests():
    client = FixtureClient([ModelResponse("a"), ModelFailure("request_rejected", "big")])

    assert client.complete(request()) == ModelResponse("a")
    assert client.complete(request()) == ModelFailure("request_rejected", "big")
    assert len(client.requests) == 2


def test_fixture_client_fails_loudly_when_the_script_runs_out():
    client = FixtureClient([ModelResponse("a")])
    client.complete(request())

    with pytest.raises(FixtureExhausted):
        client.complete(request())


def test_recorded_requests_are_snapshots():
    client = FixtureClient([ModelResponse("a")])
    messages = [{"role": "user", "content": "x"}]
    client.complete(ModelRequest(tuple(messages), (), "auto"))
    messages[0]["content"] = "changed"

    assert client.requests[0].messages[0]["content"] == "x"


def test_fixture_file_loads_into_responses_with_raw_or_structured_arguments():
    scenarios = load_fixtures(FIXTURES)
    client = FixtureClient.from_data(scenarios["malformed_then_recovery"])
    first, second, final = client.responses

    assert first.tool_calls == (ToolCall("t1", "run_checks", "{not json"),)
    assert second.tool_calls[0].arguments.startswith('{"source"')
    assert final.content.startswith("def count_vowels")
    assert FixtureClient.from_data(scenarios["request_rejected_on_call_3"]).responses[2] == ModelFailure(
        "request_rejected", "rendered request exceeds the 12,000 input-token limit")


def test_default_limits_are_the_agreed_values_and_hash_tracks_changes():
    assert DEFAULT_AGENT_LIMITS.to_dict() == {
        "max_model_calls": 4, "max_tool_attempts": 3, "max_checks_per_request": 4}
    assert DEFAULT_AGENT_LIMITS.config_hash() == AgentLimits().config_hash()
    assert AgentLimits(max_tool_attempts=2).config_hash() != DEFAULT_AGENT_LIMITS.config_hash()
    assert AgentLimits.from_dict(DEFAULT_AGENT_LIMITS.to_dict()) == DEFAULT_AGENT_LIMITS


@pytest.mark.parametrize("bad", [{"max_model_calls": 0}, {"max_tool_attempts": -1},
                                 {"max_checks_per_request": 1.5}, {"max_model_calls": True}])
def test_invalid_agent_limits_are_rejected(bad):
    with pytest.raises(ValueError):
        AgentLimits(**bad)


def test_from_dict_requires_exactly_the_known_fields():
    with pytest.raises(ValueError):
        AgentLimits.from_dict({"max_model_calls": 4})


def test_baseline_prompt_is_versioned_and_hashed():
    prompt = load_prompt()

    assert prompt.version == "baseline_agent_v1"
    assert "run_checks" in prompt.text and len(prompt.sha256) == 64
    with pytest.raises(ValueError):
        load_prompt("../baseline_agent_v1")
