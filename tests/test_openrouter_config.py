import json
from decimal import Decimal
from pathlib import Path

import pytest

from codegen_eval.openrouter_config import (
    DEFAULT_MODEL_CONFIG, ModelConfig, PriceInputs, load_model_config,
)

ROOT = Path(__file__).resolve().parents[1]


def test_defaults_are_the_agreed_values_and_match_the_versioned_file():
    config = load_model_config()

    assert config == ModelConfig() and config.config_version == DEFAULT_MODEL_CONFIG
    assert (config.model, config.provider) == ("z-ai/glm-5.3-flash", "open-inference/fp4")
    assert (config.allow_fallbacks, config.require_parameters) == (False, True)
    assert (config.temperature, config.top_p, config.reasoning_effort) == (0.2, 1.0, "low")
    assert (config.max_input_tokens, config.max_output_tokens) == (12000, 2000)
    assert config.attempt_timeout_seconds == 60
    assert (config.max_retries_per_request, config.max_retries_per_trial) == (1, 2)


def test_hash_is_stable_and_tracks_every_change():
    base = ModelConfig()

    assert base.config_hash() == ModelConfig.from_dict(base.to_dict()).config_hash()
    assert ModelConfig(temperature=0.3).config_hash() != base.config_hash()
    assert ModelConfig(reasoning_effort="high").config_hash() != base.config_hash()
    assert base.identity()["config_hash"] == base.config_hash()


def test_invalid_configuration_is_rejected():
    for bad in ({"allow_fallbacks": True}, {"require_parameters": False},
                {"max_input_tokens": 0}, {"temperature": float("nan")},
                {"reasoning_effort": "medium"}, {"max_retries_per_trial": -1},
                {"max_output_tokens": True}):
        with pytest.raises(ValueError):
            ModelConfig(**bad)
    with pytest.raises(ValueError):
        ModelConfig.from_dict({**ModelConfig().to_dict(), "extra": 1})
    with pytest.raises(ValueError):
        load_model_config("../openrouter_glm_v1")


def test_reservation_uses_caps_prices_conversion_margin_and_fees():
    prices = PriceInputs.from_dict({
        "input_usd_per_million": "0.0052", "output_usd_per_million": "0.1985",
        "prices_checked_on": "d", "prices_source": "s", "chf_per_usd": "0.8", "fx_date": "d",
        "fx_source": "s", "safety_margin": "0.25", "fixed_fee_chf": "0.001"})
    usd = (Decimal(12000) * Decimal("0.0052") + Decimal(2000) * Decimal("0.1985")) / 1_000_000

    assert prices.reservation_chf(ModelConfig()) == usd * Decimal("0.8") * Decimal("1.25") \
        + Decimal("0.001")
    assert prices.usage_estimate_chf(0, 0) == Decimal("0.001")


def test_price_inputs_are_required_and_the_example_file_is_not_usable_as_is():
    example = json.loads((ROOT / "docs" / "openrouter_pricing.example.json").read_text())
    with pytest.raises(ValueError, match="chf_per_usd"):
        PriceInputs.from_dict(example)
    filled = {**example, "chf_per_usd": "0.8", "fx_date": "2026-10-30", "fx_source": "x",
              "safety_margin": "0.2", "fixed_fee_chf": "0"}
    assert PriceInputs.from_dict(filled).input_usd_per_million == Decimal("0.0052")
    with pytest.raises(ValueError):
        PriceInputs.from_dict({k: v for k, v in filled.items() if k != "fx_date"})
    with pytest.raises(ValueError):
        PriceInputs.from_dict({**filled, "safety_margin": "-1"})
    with pytest.raises(ValueError):
        PriceInputs.from_dict({**filled, "fx_source": ""})
