"""Model-client interface for agent trials, plus a deterministic recorded-response client.

The controller depends only on `ModelClient`. A live client (a later change) implements
the same interface; the fixture client here replays scripted responses and needs no API."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text exactly as the model produced it; may be malformed


@dataclass(frozen=True)
class ModelRequest:
    """One rendered request. `tool_choice` is "auto" while tools are offered, else "none"."""

    messages: tuple[Mapping[str, Any], ...]
    tools: tuple[Mapping[str, Any], ...]
    tool_choice: str


@dataclass(frozen=True)
class ModelResponse:
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    truncated: bool = False
    usage: Mapping[str, Any] | None = None


# Failure kinds the controller understands. A live client may add transport kinds later.
REQUEST_REJECTED = "request_rejected"  # rendered request exceeded the input limit; nothing was sent


@dataclass(frozen=True)
class ModelFailure:
    kind: str
    detail: str = ""


class ModelClient(Protocol):
    def complete(self, request: ModelRequest) -> ModelResponse | ModelFailure: ...


class FixtureExhausted(AssertionError):
    """The controller asked for more model calls than the fixture scripted."""


def _response_from_data(data: Mapping[str, Any]) -> ModelResponse | ModelFailure:
    if "failure" in data:
        return ModelFailure(str(data["failure"]), str(data.get("detail", "")))
    calls = []
    for index, call in enumerate(data.get("tool_calls", [])):
        arguments = call["arguments"]
        if not isinstance(arguments, str):  # fixtures may write well-formed arguments as JSON
            arguments = json.dumps(arguments)
        calls.append(ToolCall(str(call.get("id", f"call_{index}")), call["name"], arguments))
    return ModelResponse(data.get("content"), tuple(calls), bool(data.get("truncated", False)),
                         data.get("usage"))


@dataclass
class FixtureClient:
    """Replays scripted responses in order and records every request it receives."""

    responses: Sequence[ModelResponse | ModelFailure]
    requests: list[ModelRequest] = field(default_factory=list)

    def complete(self, request: ModelRequest) -> ModelResponse | ModelFailure:
        # Snapshot so later mutation of the controller's conversation cannot alter the record.
        self.requests.append(copy.deepcopy(request))
        if len(self.requests) > len(self.responses):
            raise FixtureExhausted(f"fixture scripted {len(self.responses)} responses, "
                                   f"call {len(self.requests)} requested")
        return self.responses[len(self.requests) - 1]

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "FixtureClient":
        return cls([_response_from_data(item) for item in data["responses"]])


def load_fixtures(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load recorded-response scenarios keyed by name."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture file must map scenario names to scenarios")
    return raw
