"""Test doubles for the OpenRouter client: a scripted transport and wire-reply builders."""

import json
from decimal import Decimal

from codegen_eval.ledger import Ledger
from codegen_eval.openrouter_client import (
    OpenRouterClient, TransportConnectionError, TransportResponse, TransportTimeout,
)
from codegen_eval.openrouter_config import ModelConfig, PriceInputs

KEY = "sk-or-test-SECRETKEY-123456"

PRICES = PriceInputs.from_dict({
    "input_usd_per_million": "0.0052", "output_usd_per_million": "0.1985",
    "prices_checked_on": "2026-10-30 (test)", "prices_source": "test",
    "chf_per_usd": "0.80", "fx_date": "2026-10-30", "fx_source": "test",
    "safety_margin": "0.25", "fixed_fee_chf": "0"})


class FakeTransport:
    """Replays scripted replies (a TransportResponse or an exception) and records each call."""

    def __init__(self, *replies, on_post=None):
        self.replies = list(replies)
        self.calls = []
        self.on_post = on_post

    def post(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": json.loads(body),
                           "timeout": timeout})
        if self.on_post:
            self.on_post()
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def reply(content="def f(x):\n    return x\n", *, tool_calls=None, finish="stop", usage="default",
          status=200, headers=None, **extra):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    body = {"id": "gen-1", "model": "z-ai/glm-5.3-flash-20260826", "provider": "OpenInference",
            "choices": [{"index": 0, "finish_reason": finish, "message": message}], **extra}
    if usage == "default":
        usage = {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100,
                 "cost": 0.0002, "completion_tokens_details": {"reasoning_tokens": 40}}
    if usage is not None:
        body["usage"] = usage
    return TransportResponse(status, headers or {}, json.dumps(body).encode())


def error_reply(status, message="boom", headers=None):
    return TransportResponse(status, headers or {},
                             json.dumps({"error": {"code": status, "message": message}}).encode())


def tool_call(arguments='{"source": "x", "checks": []}', name="run_checks", id="call_1"):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": arguments}}


TIMEOUT = TransportTimeout("deadline")
DISCONNECT = TransportConnectionError("reset")


def make_client(tmp_path, transport, *, ledger=None, config=None, sleeps=None, **kwargs):
    ledger = ledger or Ledger(tmp_path / "ledger.jsonl")
    sleeps = [] if sleeps is None else sleeps
    client = OpenRouterClient(config or ModelConfig(), PRICES, ledger, KEY, transport,
                              sleep=sleeps.append, **kwargs)
    return client, ledger, sleeps


def ledger_events(ledger):
    return [json.loads(line) for line in ledger.path.read_text().splitlines()]
