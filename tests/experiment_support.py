"""Offline environment for experiment tests: a configuration, probe and freeze evidence, a
retained smoke bundle made through the fake transport, and scripted per-task solutions."""

import json
from dataclasses import dataclass
from pathlib import Path

from codegen_eval import agent_config
from codegen_eval.experiment import (
    build_config, parse_config, write_probes_evidence, write_settings_freeze,
)
from codegen_eval.ledger import Ledger
from codegen_eval.model_client import FixtureClient, ModelResponse
from codegen_eval.openrouter_client import OpenRouterClient
from codegen_eval.openrouter_config import ModelConfig
from codegen_eval.replay import make_grader
from codegen_eval.run_checks import TOOL_SCHEMA
from codegen_eval.run_recording import run_recorded
from codegen_eval.tasks import load_benchmark
from openrouter_support import KEY, PRICES, FakeTransport, reply, tool_call

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
TASKS = load_benchmark(BENCHMARK)
SOURCE = "def count_vowels(text: str) -> int:\n    return sum(c in 'aeiou' for c in text.lower())\n"
CALL = tool_call(json.dumps({"source": SOURCE, "checks": [{"arguments": ["abc"], "expected": 1}]}))
REVISED_PROMPT = "revised_test_v1"


def reference(task):
    return (ROOT / "data" / "references_v1" / f"{task.id}.py").read_text(encoding="utf-8")


def wrong(task):
    return f"def {task.signature}:\n    return None\n"


def solving(source_for):
    """client_for answering each trial with one final message: `source_for(task)`."""
    return lambda task, trial_id: FixtureClient([ModelResponse(content=source_for(task))])


def local_grader(inprocess_runner):
    return make_grader(lambda source, task, case: inprocess_runner(source, task.function_name, case.args))


def smoke_replies(prompt_tokens=100):
    usage = {"prompt_tokens": prompt_tokens, "completion_tokens": 50, "total_tokens": prompt_tokens + 50,
             "cost": 0.0001}
    tools = [reply(None, tool_calls=[{**CALL, "id": f"call_{n}"}], usage=usage, finish="tool_calls")
             for n in range(3)]
    return [*tools, reply(SOURCE, usage=usage)]


def make_smoke(tmp_path, inprocess_runner, *, prompt_tokens=100, config=None):
    """A retained smoke bundle made with the real client over the fake transport."""
    config = config or ModelConfig()
    transport = FakeTransport(*smoke_replies(prompt_tokens))
    ledger = Ledger(tmp_path / "smoke_ledger.jsonl")

    def client_for(task, trial_id):
        return OpenRouterClient(config, PRICES, ledger, KEY, transport, tool_definitions=(TOOL_SCHEMA,),
                                sleep=lambda s: None)

    path, _ = run_recorded(TASKS[:1], client_for, BENCHMARK, bundle_root=tmp_path / "smoke",
                           run_id="smoke-1", runner=inprocess_runner,
                           model_settings=config.identity(), extra_secrets=(KEY,))
    return path


@dataclass
class Env:
    config: object
    options: dict
    evidence: Path
    bundles: Path
    ledger: Ledger
    smoke: Path


def make_env(tmp_path, inprocess_runner, *, revised=None, **overrides):
    """Everything the preconditions need, satisfied; `overrides` replace option values."""
    evidence = tmp_path / "evidence"
    config = parse_config(build_config(BENCHMARK, revised_prompt=revised))
    write_probes_evidence(evidence, {"tests": 56, "failures": 0, "errors": 0, "skipped": 0},
                          command="pytest -m sandbox")
    smoke = make_smoke(tmp_path, inprocess_runner)
    write_settings_freeze(config, smoke, evidence)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    options = dict(ledger=ledger, prices=PRICES, accept_cost=True, api_key=KEY, evidence_dir=evidence,
                   bundle_root=tmp_path / "bundles", benchmark_path=BENCHMARK)
    options.update(overrides)
    return Env(config, options, evidence, tmp_path / "bundles", ledger, smoke)


def with_revised_prompt(monkeypatch, tmp_path, text="You are a careful coder. Revised.\n"):
    """Make a second prompt file visible to `load_prompt` without touching the repository."""
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    for source in agent_config.PROMPT_DIR.glob("*.md"):
        (prompts / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (prompts / f"{REVISED_PROMPT}.md").write_text(text, encoding="utf-8")
    monkeypatch.setattr(agent_config, "PROMPT_DIR", prompts)
    return REVISED_PROMPT
