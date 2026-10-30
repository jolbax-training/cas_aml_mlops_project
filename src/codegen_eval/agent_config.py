"""Interaction limits and the versioned agent prompt for bounded trials."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentLimits:
    """Per-trial interaction limits; the defaults are the agreed project values.

    Transport retries are physical attempts inside one logical call and are not counted."""

    max_model_calls: int = 4
    max_tool_attempts: int = 3
    max_checks_per_request: int = 4

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field.name} must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentLimits":
        names = {field.name for field in fields(cls)}
        if set(data) != names:
            raise ValueError(f"limits must have exactly these fields: {sorted(names)}")
        return cls(**data)

    def config_hash(self) -> str:
        """Stable hash for recording with a run and holding fixed across variants."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


DEFAULT_AGENT_LIMITS = AgentLimits()

PROMPT_DIR = Path(__file__).parent / "prompts"
BASELINE_PROMPT = "baseline_agent_v1"


@dataclass(frozen=True)
class AgentPrompt:
    version: str  # file stem, e.g. baseline_agent_v1
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def load_prompt(version: str = BASELINE_PROMPT) -> AgentPrompt:
    """Load a versioned prompt file; the version is its file stem."""
    path = PROMPT_DIR / f"{version}.md"
    if path.parent != PROMPT_DIR or not path.is_file():
        raise ValueError(f"unknown agent prompt version: {version!r}")
    return AgentPrompt(version, path.read_text(encoding="utf-8"))
