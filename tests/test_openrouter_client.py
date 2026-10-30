import json
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from codegen_eval.ledger import Ledger
from codegen_eval.model_client import (
    REQUEST_REJECTED, TRANSPORT_EXHAUSTED, ModelFailure, ModelRequest, ModelResponse, ToolCall,
)
from codegen_eval.openrouter_client import (
    API_ERROR, BUDGET_CEILING, MALFORMED_RESPONSE, HttpTransport, TransportTimeout,
    input_token_bound,
)
from codegen_eval.openrouter_config import ModelConfig
from codegen_eval.run_checks import TOOL_SCHEMA
from openrouter_support import (
    DISCONNECT, KEY, PRICES, TIMEOUT, FakeTransport, error_reply, ledger_events, make_client,
    reply, tool_call,
)


def req(content="write f", *, tools=(TOOL_SCHEMA,), choice="auto", extra=()):
    return ModelRequest(({"role": "system", "content": "sys"},
                         {"role": "user", "content": content}, *extra), tuple(tools), choice)


# --- configuration on the wire -------------------------------------------------------

def test_request_carries_the_pinned_model_provider_and_fixed_settings(tmp_path):
    transport = FakeTransport(reply())
    client, _, _ = make_client(tmp_path, transport)

    response = client.complete(req())

    sent = transport.calls[0]
    body = sent["body"]
    assert isinstance(response, ModelResponse)
    assert body["model"] == "z-ai/glm-5.3-flash"
    assert body["provider"] == {"order": ["open-inference/fp4"], "only": ["open-inference/fp4"],
                                "allow_fallbacks": False, "require_parameters": True}
    assert (body["temperature"], body["top_p"], body["max_tokens"]) == (0.2, 1.0, 2000)
    assert body["reasoning"] == {"effort": "low"} and body["stream"] is False
    assert body["tools"] == [TOOL_SCHEMA] and body["tool_choice"] == "auto"
    assert sent["timeout"] == 60 and sent["headers"]["Authorization"] == f"Bearer {KEY}"


def test_final_only_call_sends_tool_choice_none_with_definitions_kept(tmp_path):
    transport = FakeTransport(reply())
    client, _, _ = make_client(tmp_path, transport, tool_definitions=(TOOL_SCHEMA,))
    history = ({"role": "assistant", "content": None,
                "tool_calls": [{"id": "c1", "name": "run_checks", "arguments": "{}"}]},
               {"role": "tool", "tool_call_id": "c1", "content": "{}"})

    client.complete(req(tools=(), choice="none", extra=history))

    body = transport.calls[0]["body"]
    assert body["tool_choice"] == "none" and body["tools"] == [TOOL_SCHEMA]
    assert body["messages"][2] == {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "run_checks", "arguments": "{}"}}]}
    assert body["messages"][3] == {"role": "tool", "tool_call_id": "c1", "content": "{}"}


def test_response_is_translated_with_raw_tool_arguments_and_usage(tmp_path):
    transport = FakeTransport(reply(None, tool_calls=[tool_call("{not json")]))
    client, _, _ = make_client(tmp_path, transport)

    response = client.complete(req())

    assert response.content is None and response.truncated is False
    assert response.tool_calls == (ToolCall("call_1", "run_checks", "{not json"),)
    assert response.usage["prompt_tokens"] == 1000


# --- pre-send size check -----------------------------------------------------------

def test_bound_never_undercounts_bytes_and_scales_with_messages():
    assert input_token_bound(b"x" * 100, 0) == 100
    assert input_token_bound(b"x" * 100, 2) == 116
    assert input_token_bound(b"x" * 100, 0, 4) == 25


def test_oversized_request_is_rejected_without_sending_or_reserving(tmp_path):
    transport = FakeTransport()
    client, ledger, sleeps = make_client(tmp_path, transport)

    result = client.complete(req("x" * 13000))

    assert isinstance(result, ModelFailure) and result.kind == REQUEST_REJECTED
    assert transport.calls == [] and not ledger.path.exists() and sleeps == []
    (attempt,) = client.attempts
    assert attempt["outcome"] == "pre_send_rejected" and attempt["sent"] is False
    assert attempt["reservation"] is None and client.trial_retries == 0


def test_request_just_under_the_limit_is_sent(tmp_path):
    transport = FakeTransport(reply())
    client, _, _ = make_client(tmp_path, transport)

    assert isinstance(client.complete(req("x" * 10000)), ModelResponse)


def test_rejection_ends_a_trial_as_no_submission_request_rejected(tmp_path):
    from codegen_eval.trial import run_trial
    from test_agent_trial import TASK

    client, _, _ = make_client(tmp_path, FakeTransport(),
                               config=ModelConfig(max_input_tokens=100))

    result = run_trial(TASK, client)

    assert (result.status, result.label, result.model_calls) == ("no_submission",
                                                                 REQUEST_REJECTED, 1)


# --- retries -----------------------------------------------------------------------

@pytest.mark.parametrize("first", [error_reply(503), error_reply(429), error_reply(408),
                                   TIMEOUT, DISCONNECT, error_reply(502)])
def test_transient_failure_is_retried_once_and_every_attempt_is_reserved(tmp_path, first):
    transport = FakeTransport(first, reply())
    client, ledger, sleeps = make_client(tmp_path, transport)

    response = client.complete(req())

    assert isinstance(response, ModelResponse)
    assert len(transport.calls) == 2 and client.trial_retries == 1 and sleeps == [1.0]
    assert [a["retry_index"] for a in client.attempts] == [0, 1]
    assert [e["event"] for e in ledger_events(ledger)].count("reservation") == 2


def test_rate_limit_retry_after_lengthens_the_bounded_backoff(tmp_path):
    transport = FakeTransport(error_reply(429, headers={"Retry-After": "3"}), reply())
    client, _, sleeps = make_client(tmp_path, transport)
    client.complete(req())
    assert sleeps == [3.0]

    transport = FakeTransport(error_reply(429, headers={"Retry-After": "999"}), reply())
    client, _, sleeps = make_client(tmp_path, transport)
    client.complete(req())
    assert sleeps == [10.0]


def test_a_second_failure_in_one_request_exhausts_the_per_request_retry(tmp_path):
    transport = FakeTransport(error_reply(503), error_reply(503), reply())
    client, _, _ = make_client(tmp_path, transport)

    result = client.complete(req())

    assert isinstance(result, ModelFailure) and result.kind == TRANSPORT_EXHAUSTED
    assert len(transport.calls) == 2 and client.trial_retries == 1


def test_third_transport_failure_in_a_trial_gets_no_retry(tmp_path):
    transport = FakeTransport(TIMEOUT, reply(),              # call 1: one retry used
                              error_reply(500), reply(),     # call 2: second retry used
                              error_reply(500))              # call 3: none left
    client, _, sleeps = make_client(tmp_path, transport)

    assert isinstance(client.complete(req()), ModelResponse)
    assert isinstance(client.complete(req()), ModelResponse)
    result = client.complete(req())

    assert result.kind == TRANSPORT_EXHAUSTED and "2 used in this trial" in result.detail
    assert len(transport.calls) == 5 and client.trial_retries == 2 and len(sleeps) == 2


def test_exhausted_retries_make_the_trial_infrastructure_incomplete(tmp_path):
    from codegen_eval.trial import run_trial
    from test_agent_trial import TASK

    client, _, _ = make_client(tmp_path, FakeTransport(error_reply(503), error_reply(503)))

    result = run_trial(TASK, client)

    assert (result.status, result.infrastructure_status) == ("infrastructure_incomplete",
                                                             TRANSPORT_EXHAUSTED)


def test_non_transient_errors_are_not_retried(tmp_path):
    for bad in (error_reply(400, "bad request"), error_reply(401), error_reply(404, "no endpoints")):
        transport = FakeTransport(bad)
        client, _, sleeps = make_client(tmp_path, transport)

        result = client.complete(req())

        assert result.kind == API_ERROR and len(transport.calls) == 1 and sleeps == []
        assert client.trial_retries == 0


def test_pinned_endpoint_unavailable_fails_without_fallback_and_is_recorded(tmp_path):
    transport = FakeTransport(error_reply(404, "No allowed providers are available"))
    client, _, _ = make_client(tmp_path, transport)

    result = client.complete(req())

    assert result.kind == API_ERROR and len(transport.calls) == 1
    assert transport.calls[0]["body"]["provider"]["allow_fallbacks"] is False
    assert client.attempts[0]["error_class"] == "http_404"


def test_error_inside_a_200_body_is_classified_by_its_code(tmp_path):
    body = json.dumps({"error": {"code": 502, "message": "upstream"}}).encode()
    from codegen_eval.openrouter_client import TransportResponse
    transport = FakeTransport(TransportResponse(200, {}, body), reply())
    client, _, _ = make_client(tmp_path, transport)

    assert isinstance(client.complete(req()), ModelResponse)
    assert client.attempts[0]["error_class"] == "api_error_502" and len(transport.calls) == 2


def test_truncation_refusal_and_malformed_arguments_are_returned_without_retry(tmp_path):
    transport = FakeTransport(reply("def f(", finish="length"),
                              reply(None, finish="stop", refusal="I cannot help"),
                              reply(None, tool_calls=[tool_call('{"source": ')]),
                              reply("  "))
    client, _, sleeps = make_client(tmp_path, transport)

    truncated = client.complete(req())
    refusal = client.complete(req())
    malformed = client.complete(req())
    blank = client.complete(req())

    assert truncated == ModelResponse("def f(", (), True, truncated.usage)
    assert refusal.content is None and refusal.tool_calls == ()
    assert malformed.tool_calls[0].arguments == '{"source": '
    assert blank.content == "  "
    assert len(transport.calls) == 4 and sleeps == [] and client.trial_retries == 0
    assert client.attempts[0]["finish_reason"] == "length" and client.attempts[0]["truncated"]


def test_unusable_envelope_is_not_retried(tmp_path):
    from codegen_eval.openrouter_client import TransportResponse
    for body in (b"<html>", b"[]", json.dumps({"choices": []}).encode(),
                 json.dumps({"choices": [{"message": {"content": 5}}]}).encode()):
        transport = FakeTransport(TransportResponse(200, {}, body))
        client, _, sleeps = make_client(tmp_path, transport)

        result = client.complete(req())

        assert result.kind == MALFORMED_RESPONSE and len(transport.calls) == 1 and sleeps == []


# --- attempt records ---------------------------------------------------------------

def test_attempt_record_has_metadata_usage_cost_reservation_and_no_credential(tmp_path):
    transport = FakeTransport(reply())
    client, ledger, _ = make_client(tmp_path, transport, context={"trial_id": "t1"})

    client.complete(req())

    (a,) = client.attempts
    assert a["requested_model"] == "z-ai/glm-5.3-flash"
    assert a["returned_model"] == "z-ai/glm-5.3-flash-20260826" and a["provider"] == "OpenInference"
    assert a["provider_matches_pin"] is True and a["generation_id"] == "gen-1"
    assert (a["prompt_tokens"], a["completion_tokens"], a["reasoning_tokens"]) == (1000, 100, 40)
    assert a["reported_cost_usd"] == 0.0002 and a["http_status"] == 200
    assert a["settings"]["temperature"] == 0.2 and a["retry_index"] == 0
    assert a["reservation"]["amount_chf"] == str(PRICES.reservation_chf(ModelConfig()))
    assert a["precision"] is None and a["missing_fields"] == ["precision"]
    assert a["started_at"] and a["ended_at"] and isinstance(a["latency_ms"], int)
    assert KEY not in json.dumps(client.attempts) and KEY not in ledger.path.read_text()
    assert KEY not in repr(client)
    assert ledger_events(ledger)[0]["context"]["trial_id"] == "t1"


def test_missing_metadata_is_marked_missing_and_a_foreign_provider_is_flagged(tmp_path):
    from codegen_eval.openrouter_client import TransportResponse
    body = {"choices": [{"finish_reason": "stop", "message": {"content": "x"}}],
            "provider": "SomeoneElse"}
    client, _, _ = make_client(tmp_path, FakeTransport(TransportResponse(
        200, {}, json.dumps(body).encode())))

    client.complete(req())

    a = client.attempts[0]
    assert {"returned_model", "prompt_tokens", "completion_tokens", "reported_cost_usd",
            "generation_id", "precision"} <= set(a["missing_fields"])
    assert a["provider_matches_pin"] is False and a["prompt_tokens"] is None


# --- ledger interplay --------------------------------------------------------------

def test_reservation_is_durable_before_the_request_is_sent(tmp_path):
    seen = []
    holder = {}

    def on_post():
        seen.extend(ledger_events(holder["ledger"]))

    transport = FakeTransport(reply(), on_post=on_post)
    client, ledger, _ = make_client(tmp_path, transport)
    holder["ledger"] = ledger

    client.complete(req())

    assert [e["event"] for e in seen] == ["reservation"]  # nothing settled yet at send time
    assert [e["event"] for e in ledger_events(ledger)] == ["reservation", "settlement"]


def test_reported_cost_is_committed_in_chf_and_the_reservation_released(tmp_path):
    client, ledger, _ = make_client(tmp_path, FakeTransport(reply(usage={
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.0001})))

    client.complete(req())

    state = ledger.state()
    assert state.reserved == 0 and state.committed == Decimal("0.0001") * PRICES.chf_per_usd
    settlement = ledger_events(ledger)[-1]
    assert settlement["basis"] == "reported_cost" and settlement["reported_cost_usd"] == "0.0001"
    assert client.attempts[0]["charge"]["basis"] == "reported_cost"


def test_usage_without_cost_is_committed_as_a_labelled_estimate(tmp_path):
    client, ledger, _ = make_client(tmp_path, FakeTransport(reply(usage={
        "prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100})))

    client.complete(req())

    expected = PRICES.usage_estimate_chf(1000, 100)
    assert ledger.state().committed == expected and ledger.state().reserved == 0
    assert ledger_events(ledger)[-1]["basis"] == "estimated_from_usage"
    assert ledger_events(ledger)[-1]["reported_cost_usd"] is None


@pytest.mark.parametrize("outcome", [TIMEOUT, DISCONNECT, error_reply(503), error_reply(400),
                                     reply(usage=None)])
def test_uncertain_charges_keep_their_reservation(tmp_path, outcome):
    client, ledger, _ = make_client(tmp_path, FakeTransport(outcome, outcome),
                                    config=ModelConfig(max_retries_per_request=0))

    client.complete(req())

    amount = PRICES.reservation_chf(ModelConfig())
    assert ledger.state().reserved == amount and ledger.state().committed == 0
    assert [e["event"] for e in ledger_events(ledger)] == ["reservation", "kept"]


def test_timed_out_attempt_counts_against_the_budget_through_a_retry(tmp_path):
    client, ledger, _ = make_client(tmp_path, FakeTransport(TIMEOUT, reply()))

    client.complete(req())

    amount = PRICES.reservation_chf(ModelConfig())
    assert ledger.state().reserved == amount  # the timed-out attempt's reservation remains
    assert ledger.state().committed > 0


def test_ceiling_blocks_the_send_and_is_reported_as_budget_ceiling(tmp_path):
    amount = PRICES.reservation_chf(ModelConfig())
    ledger = Ledger(tmp_path / "l.jsonl", checkpoint_chf=amount, ceiling_chf=amount * Decimal("1.5"))
    transport = FakeTransport(TIMEOUT, TIMEOUT)
    client, _, _ = make_client(tmp_path, transport, ledger=ledger)

    result = client.complete(req())  # first attempt times out and keeps its reservation

    assert isinstance(result, ModelFailure) and result.kind == BUDGET_CEILING
    assert len(transport.calls) == 1  # the retry's reservation was refused before sending
    assert client.attempts[-1]["outcome"] == "budget_refused"
    assert ledger_events(ledger)[-1]["event"] == "refusal"
    assert client.trial_retries == 0  # the refused retry is not counted as sent


def test_a_ceiling_refusal_stops_the_trial_as_infrastructure_incomplete(tmp_path):
    from codegen_eval.trial import run_trial
    from test_agent_trial import TASK

    amount = PRICES.reservation_chf(ModelConfig())
    ledger = Ledger(tmp_path / "l.jsonl", checkpoint_chf=amount, ceiling_chf=amount)
    ledger.reserve(amount, {})
    client, _, _ = make_client(tmp_path, FakeTransport(), ledger=ledger)

    result = run_trial(TASK, client)

    assert (result.status, result.infrastructure_status) == ("infrastructure_incomplete",
                                                             BUDGET_CEILING)


def test_unexpected_exception_keeps_the_reservation_and_propagates(tmp_path):
    client, ledger, _ = make_client(tmp_path, FakeTransport(RuntimeError("bug")))

    with pytest.raises(RuntimeError):
        client.complete(req())

    assert ledger.state().reserved > 0
    assert client.attempts[0]["error_class"] == "unexpected_RuntimeError"


# --- the real HTTP transport against a loopback server (no external network) ----------

@pytest.fixture
def server():
    behaviours = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            behaviours["received"] = (self.headers.get("Authorization"), self.rfile.read(length))
            if behaviours.get("slow"):
                import time
                time.sleep(2)
                return
            self.send_response(behaviours.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    behaviours["url"] = f"http://127.0.0.1:{httpd.server_port}/v1/chat"
    yield behaviours
    httpd.shutdown()
    httpd.server_close()


def test_http_transport_posts_bytes_and_returns_status_and_body(server):
    server["status"] = 503
    response = HttpTransport().post(server["url"], {"Authorization": "Bearer abc"}, b'{"a":1}', 5)

    assert (response.status, response.body) == (503, b'{"ok": true}')
    assert server["received"] == ("Bearer abc", b'{"a":1}')


def test_http_transport_enforces_the_attempt_deadline_and_maps_connection_errors(server):
    server["slow"] = True
    with pytest.raises(TransportTimeout):
        HttpTransport().post(server["url"], {}, b"{}", 0.3)
    from codegen_eval.openrouter_client import TransportConnectionError
    with pytest.raises(TransportConnectionError):
        HttpTransport().post("http://127.0.0.1:1/x", {}, b"{}", 2)
    with pytest.raises(TransportConnectionError):
        HttpTransport().post("ftp://example.com/x", {}, b"{}", 2)
