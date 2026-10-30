"""Fixed, serialisable limits for one candidate check."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace
from typing import Any, Mapping


@dataclass(frozen=True)
class ExecutionLimits:
    """Per-check limits; the defaults are the agreed project values."""

    deadline_seconds: float = 10.0  # includes container startup and code loading; cleanup is separate
    memory_mib: int = 128
    cpus: int = 1
    max_processes: int = 32
    tmp_mib: int = 16
    payload_bytes: int = 65_536  # candidate source plus arguments
    print_bytes: int = 32_768
    protocol_bytes: int = 65_536

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{field.name} must be a positive number")
            if field.name != "deadline_seconds" and not isinstance(value, int):
                raise ValueError(f"{field.name} must be an integer")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionLimits":
        names = {field.name for field in fields(cls)}
        if set(data) != names:
            raise ValueError(f"limits must have exactly these fields: {sorted(names)}")
        return cls(**data)

    def with_deadline(self, seconds: float) -> "ExecutionLimits":
        return replace(self, deadline_seconds=seconds)

    def config_hash(self) -> str:
        """Stable hash for recording with a run and holding fixed across variants."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


DEFAULT_LIMITS = ExecutionLimits()
