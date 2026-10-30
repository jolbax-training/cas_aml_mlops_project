"""Versioned model/request configuration and the dated price inputs for cost reservations.

The configuration is a JSON file in `model_configs/`; its hash is recorded in every bundle.
Price and CHF-conversion inputs are supplied per run from a file the user fills in, because
they are dated facts that must be rechecked before spending (nothing here fixes them)."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

CONFIG_DIR = Path(__file__).parent / "model_configs"
DEFAULT_MODEL_CONFIG = "openrouter_glm_v1"


@dataclass(frozen=True)
class ModelConfig:
    """Every request setting that must stay fixed for a comparison. Defaults are the agreed
    project values (issue 04, Q28-Q33)."""

    config_version: str = DEFAULT_MODEL_CONFIG
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"
    model: str = "z-ai/glm-5.3-flash"
    provider: str = "open-inference/fp4"
    allow_fallbacks: bool = False
    require_parameters: bool = True
    temperature: float = 0.2
    top_p: float = 1.0
    reasoning_effort: str = "low"
    max_output_tokens: int = 2000
    max_input_tokens: int = 12000
    # The pre-send bound is ceil(request bytes / this) plus a per-message allowance. 1 is
    # provably safe (a token covers at least one byte); a larger value is only justified by
    # calibration against reported prompt tokens (see docs/model_access.md).
    input_bound_bytes_per_token: int = 1
    attempt_timeout_seconds: float = 60.0
    max_retries_per_request: int = 1
    max_retries_per_trial: int = 2
    backoff_seconds: float = 1.0
    backoff_max_seconds: float = 8.0

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if field.type in ("int",) and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError(f"{field.name} must be an integer")
            if field.type in ("float",):
                if isinstance(value, bool) or not isinstance(value, (int, float)) \
                        or not math.isfinite(value):
                    raise ValueError(f"{field.name} must be a finite number")
            if field.type == "str" and (not isinstance(value, str) or not value):
                raise ValueError(f"{field.name} must be a non-empty string")
            if field.type == "bool" and not isinstance(value, bool):
                raise ValueError(f"{field.name} must be a boolean")
        for name in ("max_output_tokens", "max_input_tokens", "input_bound_bytes_per_token",
                     "attempt_timeout_seconds"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("max_retries_per_request", "max_retries_per_trial", "backoff_seconds",
                     "backoff_max_seconds"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if self.reasoning_effort not in ("low", "high", "max"):
            raise ValueError("reasoning_effort must be low, high, or max")
        if self.allow_fallbacks or not self.require_parameters:
            raise ValueError("provider fallbacks must stay disabled and required parameters on")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelConfig":
        names = {field.name for field in fields(cls)}
        if set(data) != names:
            raise ValueError(f"model config must have exactly these fields: {sorted(names)}")
        return cls(**data)

    def config_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def request_settings(self) -> dict[str, Any]:
        """The settings that go on the wire, as recorded with each attempt."""
        return {"model": self.model, "provider": self.provider,
                "allow_fallbacks": self.allow_fallbacks,
                "require_parameters": self.require_parameters,
                "temperature": self.temperature, "top_p": self.top_p,
                "reasoning_effort": self.reasoning_effort,
                "max_tokens": self.max_output_tokens,
                "timeout_seconds": self.attempt_timeout_seconds}

    def identity(self) -> dict[str, Any]:
        """What a bundle's identity records for the model (see `run_recorded`)."""
        return {"client": "openrouter", "config_hash": self.config_hash(), **self.to_dict()}


def load_model_config(version: str = DEFAULT_MODEL_CONFIG) -> ModelConfig:
    """Load a versioned configuration file; the version is its file stem."""
    path = CONFIG_DIR / f"{version}.json"
    if path.parent != CONFIG_DIR or not path.is_file():
        raise ValueError(f"unknown model config version: {version!r}")
    config = ModelConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if config.config_version != version:
        raise ValueError(f"config file {version}.json declares {config.config_version!r}")
    return config


def _decimal(value: Any, name: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"price input {name} is required")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"price input {name} is not a number: {value!r}") from None
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"price input {name} must be {'non-negative' if allow_zero else 'positive'}")
    return number


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"price input {name} is required (record the date or source)")
    return value


@dataclass(frozen=True)
class PriceInputs:
    """Dated, verified inputs for the conservative reservation. All are required; there are no
    defaults because prices, the CHF conversion, and the margin must be rechecked per run."""

    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    prices_checked_on: str
    prices_source: str
    chf_per_usd: Decimal
    fx_date: str
    fx_source: str
    safety_margin: Decimal       # e.g. 0.25 reserves 25 percent over the token-price estimate
    fixed_fee_chf: Decimal       # applicable fees per attempt; 0 if none apply

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PriceInputs":
        names = {field.name for field in fields(cls)}
        extra = set(data) - names - {"_comment"}
        if extra or not names <= set(data):
            raise ValueError(f"price inputs must have exactly these fields: {sorted(names)}")
        return cls(
            _decimal(data["input_usd_per_million"], "input_usd_per_million"),
            _decimal(data["output_usd_per_million"], "output_usd_per_million"),
            _text(data["prices_checked_on"], "prices_checked_on"),
            _text(data["prices_source"], "prices_source"),
            _decimal(data["chf_per_usd"], "chf_per_usd"),
            _text(data["fx_date"], "fx_date"),
            _text(data["fx_source"], "fx_source"),
            _decimal(data["safety_margin"], "safety_margin", allow_zero=True),
            _decimal(data["fixed_fee_chf"], "fixed_fee_chf", allow_zero=True))

    @classmethod
    def from_file(cls, path: str | Path) -> "PriceInputs":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, str]:
        return {field.name: str(getattr(self, field.name)) for field in fields(self)}

    def reservation_chf(self, config: ModelConfig) -> Decimal:
        """Worst case for one attempt at the enforced caps, with margin and fees."""
        usd = (Decimal(config.max_input_tokens) * self.input_usd_per_million
               + Decimal(config.max_output_tokens) * self.output_usd_per_million) / 1_000_000
        return usd * self.chf_per_usd * (1 + self.safety_margin) + self.fixed_fee_chf

    def usage_estimate_chf(self, prompt_tokens: int, completion_tokens: int) -> Decimal:
        """Charge estimate from reported token usage (used only when no cost is reported)."""
        usd = (Decimal(prompt_tokens) * self.input_usd_per_million
               + Decimal(completion_tokens) * self.output_usd_per_million) / 1_000_000
        return usd * self.chf_per_usd * (1 + self.safety_margin) + self.fixed_fee_chf
