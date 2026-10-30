"""OpenRouter client implementing the agent loop's `ModelClient` interface.

One client serves one trial: it counts the trial's transport retries. Every physical attempt
is reserved in the spending ledger before it is sent and recorded in `attempts`. Plain HTTP
through an injected `Transport`; there is no SDK, so no hidden retries. The API key is held
privately, used only to build the request header, and never written anywhere."""

from __future__ import annotations

import http.client
import json
import math
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Mapping, Protocol, Sequence

from codegen_eval.bundle import utc_now
from codegen_eval.ledger import BASIS_ESTIMATED, BASIS_REPORTED, BudgetCeiling, Ledger
from codegen_eval.model_client import (
    REQUEST_REJECTED, TRANSPORT_EXHAUSTED, ModelFailure, ModelRequest, ModelResponse, ToolCall,
)
from codegen_eval.openrouter_config import ModelConfig, PriceInputs

BUDGET_CEILING = "budget_ceiling"        # a reservation was refused; the run is incomplete
API_ERROR = "api_error"                  # non-retryable API error (for example HTTP 400/401)
MALFORMED_RESPONSE = "malformed_response"  # the HTTP envelope was unusable; never retried

PER_MESSAGE_TOKEN_ALLOWANCE = 8  # chat-template tokens not visible in the serialized JSON
RETRY_AFTER_CAP_SECONDS = 10.0
ERROR_DETAIL_CHARS = 200


class TransportError(Exception):
    """The request failed before a response was received."""


class TransportTimeout(TransportError):
    """The attempt deadline passed."""


class TransportConnectionError(TransportError):
    """The connection could not be made or was lost."""


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def post(self, url: str, headers: Mapping[str, str], body: bytes,
             timeout: float) -> TransportResponse: ...


class HttpTransport:
    """Standard-library HTTPS transport with a deadline covering the whole attempt."""

    def post(self, url: str, headers: Mapping[str, str], body: bytes,
             timeout: float) -> TransportResponse:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise TransportConnectionError(f"unsupported url scheme: {parts.scheme!r}")
        deadline = time.monotonic() + timeout
        connection_class = (http.client.HTTPSConnection if parts.scheme == "https"
                            else http.client.HTTPConnection)
        connection = connection_class(parts.hostname, parts.port, timeout=timeout)
        try:
            connection.request("POST", parts.path or "/", body=body, headers=dict(headers))
            response = connection.getresponse()
            chunks = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TransportTimeout("attempt deadline passed")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return TransportResponse(response.status, dict(response.getheaders()), b"".join(chunks))
        except TimeoutError:
            raise TransportTimeout("attempt deadline passed") from None
        except (OSError, http.client.HTTPException) as error:
            raise TransportConnectionError(type(error).__name__) from None
        finally:
            connection.close()


def input_token_bound(body: bytes, message_count: int, bytes_per_token: int = 1) -> int:
    """Conservative upper bound on the input tokens of a serialized request.

    Every token covers at least one byte of the serialized request, so the byte count bounds
    the token count; JSON punctuation and sampling fields over-count, and a small allowance
    per message covers template tokens. It over-estimates, never under-estimates, unless
    `bytes_per_token` is raised above 1 by a verified calibration."""
    return math.ceil(len(body) / bytes_per_token) + PER_MESSAGE_TOKEN_ALLOWANCE * message_count


def _wire_message(message: Mapping[str, Any]) -> dict[str, Any]:
    """Translate the controller's neutral message shape to the chat-completions shape."""
    wire = {key: message[key] for key in ("role", "content", "tool_call_id") if key in message}
    if message.get("tool_calls"):
        wire["tool_calls"] = [{"id": call["id"], "type": "function",
                               "function": {"name": call["name"], "arguments": call["arguments"]}}
                              for call in message["tool_calls"]]
    return wire


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _retryable_status(status: int) -> bool:
    return status in (408, 429) or 500 <= status < 600


class OpenRouterClient:
    def __init__(self, config: ModelConfig, prices: PriceInputs, ledger: Ledger, api_key: str,
                 transport: Transport, *, tool_definitions: Sequence[Mapping[str, Any]] = (),
                 context: Mapping[str, Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 now: Callable[[], str] | None = None) -> None:
        if not api_key:
            raise ValueError("an API key is required")
        self.config = config
        self.prices = prices
        self.ledger = ledger
        self.transport = transport
        # Sent again with `tool_choice: none` so the history's tool calls stay valid on the wire.
        self.tool_definitions = tuple(tool_definitions)
        self.context = dict(context or {})
        self._api_key = api_key
        self._sleep = sleep
        self._clock = clock
        self._now = now or utc_now
        self.attempts: list[dict[str, Any]] = []   # every physical attempt, in order
        self.trial_retries = 0
        self.calls = 0
        self._retry_after: float | None = None

    def __repr__(self) -> str:
        return f"OpenRouterClient(model={self.config.model!r}, key=<hidden>)"

    # -- request -----------------------------------------------------------------------

    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        config = self.config
        tools = list(request.tools) or (list(self.tool_definitions)
                                        if request.tool_choice == "none" else [])
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": [_wire_message(m) for m in request.messages],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_output_tokens,
            "reasoning": {"effort": config.reasoning_effort},
            "provider": {"order": [config.provider], "only": [config.provider],
                         "allow_fallbacks": config.allow_fallbacks,
                         "require_parameters": config.require_parameters},
            "usage": {"include": True},
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = request.tool_choice
        return payload

    # -- the ModelClient interface -----------------------------------------------------

    def complete(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        self.calls += 1
        payload = self._payload(request)
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        bound = input_token_bound(body, len(request.messages),
                                  self.config.input_bound_bytes_per_token)
        if bound > self.config.max_input_tokens:
            detail = (f"rendered request is at most {bound} input tokens by the conservative "
                      f"bound; the limit is {self.config.max_input_tokens}")
            self._record({"outcome": "pre_send_rejected", "error_class": REQUEST_REJECTED,
                          "retry_index": 0, "input_token_bound": bound, "reservation": None,
                          "sent": False})
            return ModelFailure(REQUEST_REJECTED, detail)

        request_retries = 0
        while True:
            outcome = self._attempt(body, bound, request_retries)
            if isinstance(outcome, (ModelResponse, ModelFailure)):
                return outcome
            # `outcome` is the error class of a transient failure
            if (request_retries < self.config.max_retries_per_request
                    and self.trial_retries < self.config.max_retries_per_trial):
                request_retries += 1
                self._sleep(self._backoff(request_retries, self._retry_after))
                continue
            return ModelFailure(TRANSPORT_EXHAUSTED,
                                f"{outcome} after {request_retries} retry(ies) in this request; "
                                f"{self.trial_retries} used in this trial")

    # -- one physical attempt ----------------------------------------------------------

    def _backoff(self, retry_number: int, retry_after: float | None) -> float:
        delay = min(self.config.backoff_seconds * 2 ** (retry_number - 1),
                    self.config.backoff_max_seconds)
        if retry_after is not None:
            delay = max(delay, min(retry_after, RETRY_AFTER_CAP_SECONDS))
        return delay

    def _attempt(self, body: bytes, bound: int, retry_index: int) -> ModelResponse | ModelFailure | str:
        """Send once. Returns a final result, or an error class if the failure is retryable."""
        self._retry_after = None
        amount = self.prices.reservation_chf(self.config)
        context = {**self.context, "call": self.calls, "retry_index": retry_index,
                   "model": self.config.model}
        try:
            reservation = self.ledger.reserve(amount, self._reservation_inputs(), context)
        except BudgetCeiling as error:
            self._record({"outcome": "budget_refused", "error_class": BUDGET_CEILING,
                          "retry_index": retry_index, "input_token_bound": bound,
                          "reservation": None, "sent": False})
            return ModelFailure(BUDGET_CEILING, str(error))

        if retry_index:
            self.trial_retries += 1  # counted once the retry is actually going to be sent
        record: dict[str, Any] = {"retry_index": retry_index, "input_token_bound": bound,
                                  "reservation": {"id": reservation.id,
                                                  "amount_chf": str(reservation.amount_chf)},
                                  "sent": True, "started_at": self._now()}
        started = self._clock()
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json"}
        try:
            reply = self.transport.post(self.config.endpoint, headers, body,
                                        self.config.attempt_timeout_seconds)
        except TransportTimeout:
            return self._failed(record, started, "timeout", reservation.id)
        except TransportError:
            return self._failed(record, started, "connection_error", reservation.id)
        except BaseException as error:
            self._finish_record(record, started)
            record.update(outcome="client_error", error_class=f"unexpected_{type(error).__name__}")
            self._keep(reservation.id, record["error_class"])
            self._record(record)
            raise
        record["latency_ms"] = round((self._clock() - started) * 1000)
        record["ended_at"] = self._now()
        return self._interpret(reply, record, reservation.id)

    def _reservation_inputs(self) -> dict[str, Any]:
        return {"prices": self.prices.to_dict(),
                "input_cap_tokens": self.config.max_input_tokens,
                "output_cap_tokens": self.config.max_output_tokens,
                "config_hash": self.config.config_hash()}

    def _finish_record(self, record: dict[str, Any], started: float) -> None:
        record["latency_ms"] = round((self._clock() - started) * 1000)
        record["ended_at"] = self._now()

    def _keep(self, reservation_id: str, reason: str) -> None:
        self.ledger.keep(reservation_id, reason)

    def _failed(self, record: dict[str, Any], started: float, error_class: str,
                reservation_id: str) -> str:
        self._finish_record(record, started)
        record.update(outcome="transport_failure", error_class=error_class)
        self._keep(reservation_id, error_class)
        self._record(record)
        return error_class

    def _interpret(self, reply: TransportResponse, record: dict[str, Any],
                   reservation_id: str) -> ModelResponse | ModelFailure | str:
        record["http_status"] = reply.status
        try:
            data = json.loads(reply.body)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            data = {}
        self._metadata(record, data)
        settled = self._settle(record, data, reservation_id)

        error = data.get("error") if isinstance(data.get("error"), dict) else None
        if reply.status != 200 or error:
            code = reply.status if reply.status != 200 else _number((error or {}).get("code"))
            status = int(code) if isinstance(code, (int, float)) else 0
            record["error_class"] = f"http_{status}" if reply.status != 200 else f"api_error_{status}"
            record["outcome"] = "api_error"
            detail = str((error or {}).get("message", ""))[:ERROR_DETAIL_CHARS]
            if not settled:
                self._keep(reservation_id, record["error_class"])
            self._record(record)
            if _retryable_status(status):
                self._retry_after = self._parse_retry_after(reply.headers)
                return record["error_class"]
            return ModelFailure(API_ERROR, f"{record['error_class']}: {detail}".rstrip(": "))

        parsed = self._parse_choice(data)
        if parsed is None:
            record["error_class"] = MALFORMED_RESPONSE
            record["outcome"] = "malformed_response"
            if not settled:
                self._keep(reservation_id, MALFORMED_RESPONSE)
            self._record(record)
            return ModelFailure(MALFORMED_RESPONSE, "response has no usable choice")
        content, calls, truncated, finish_reason = parsed
        record.update(outcome="response", error_class=None, finish_reason=finish_reason,
                      truncated=truncated)
        if not settled:
            self._keep(reservation_id, "usage_missing")
        self._record(record)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return ModelResponse(content, calls, truncated, usage)

    @staticmethod
    def _parse_retry_after(headers: Mapping[str, str]) -> float | None:
        for name, value in headers.items():
            if name.lower() == "retry-after":
                try:
                    seconds = float(value)
                except ValueError:
                    return None
                return seconds if math.isfinite(seconds) and seconds >= 0 else None
        return None

    def _metadata(self, record: dict[str, Any], data: Mapping[str, Any]) -> None:
        """Fill provider/model/usage/cost fields; absent ones are listed in `missing_fields`."""
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        provider = data.get("provider") if isinstance(data.get("provider"), str) else None
        fields = {
            "requested_model": self.config.model,
            "requested_provider": self.config.provider,
            "settings": self.config.request_settings(),
            "returned_model": data.get("model") if isinstance(data.get("model"), str) else None,
            "provider": provider,
            "generation_id": data.get("id") if isinstance(data.get("id"), str) else None,
            "prompt_tokens": _number(usage.get("prompt_tokens")),
            "completion_tokens": _number(usage.get("completion_tokens")),
            "total_tokens": _number(usage.get("total_tokens")),
            "reasoning_tokens": _number(details.get("reasoning_tokens")),
            "reported_cost_usd": _number(usage.get("cost")),
            # The response body does not carry endpoint precision; it is never assumed.
            "precision": None,
        }
        record.update(fields)
        record["missing_fields"] = sorted(k for k, v in fields.items() if v is None)
        # A provider name is compared loosely (case, separators) with the pinned slug's prefix.
        pin = self.config.provider.split("/")[0].replace("-", "").lower()
        record["provider_matches_pin"] = (None if provider is None
                                          else provider.replace("-", "").replace(" ", "").lower()
                                          .startswith(pin))

    def _settle(self, record: dict[str, Any], data: Mapping[str, Any], reservation_id: str) -> bool:
        """Commit the charge if it is known; otherwise leave the reservation counted."""
        cost = record["reported_cost_usd"]
        prompt, completion = record["prompt_tokens"], record["completion_tokens"]
        if cost is not None and cost >= 0:
            amount = Decimal(str(cost)) * self.prices.chf_per_usd
            basis, reported = BASIS_REPORTED, str(cost)
        elif prompt is not None and completion is not None:
            amount = self.prices.usage_estimate_chf(int(prompt), int(completion))
            basis, reported = BASIS_ESTIMATED, None
        else:
            return False
        usage = {k: record[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                 if record[k] is not None}
        self.ledger.settle(reservation_id, amount, basis, reported_cost_usd=reported, usage=usage)
        record["charge"] = {"amount_chf": str(amount), "basis": basis}
        return True

    @staticmethod
    def _parse_choice(data: Mapping[str, Any]) -> tuple[str | None, tuple[ToolCall, ...], bool, str | None] | None:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return None
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            return None
        calls = []
        for index, raw in enumerate(message.get("tool_calls") or []):
            function = raw.get("function") if isinstance(raw, dict) else None
            if not isinstance(function, dict):
                return None
            arguments = function.get("arguments", "")
            if not isinstance(arguments, str):  # keep raw text; structured arguments are dumped
                arguments = json.dumps(arguments)
            calls.append(ToolCall(str(raw.get("id") or f"call_{index}"),
                                  str(function.get("name") or ""), arguments))
        finish = choice.get("finish_reason")
        finish = finish if isinstance(finish, str) else None
        return content, tuple(calls), finish == "length", finish

    def _record(self, record: dict[str, Any]) -> None:
        entry = {"attempt_id": uuid.uuid4().hex[:12], "call": self.calls,
                 "requested_model": self.config.model, "settings": self.config.request_settings(),
                 "at": self._now(), **record}
        self.attempts.append(entry)
