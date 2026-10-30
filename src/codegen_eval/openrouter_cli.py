"""Trusted host CLI for live model access: the paid smoke trial and ledger inspection.

This is the only place that reads `OPENROUTER_API_KEY`. The smoke command spends real money
and therefore refuses to run without `--i-accept-cost` and the key; it needs Podman for the
`run_checks` tool and the pinned image, like any graded run.

    export OPENROUTER_API_KEY=...            # never written to bundles or the ledger
    python -m codegen_eval.openrouter_cli smoke --pricing ~/prices.json --i-accept-cost

    python -m codegen_eval.openrouter_cli ledger status
    python -m codegen_eval.openrouter_cli ledger adjust --amount-chf 0.40 --note "..."
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from codegen_eval.bundle import DEFAULT_BUNDLE_ROOT, load_trial
from codegen_eval.ledger import Ledger, default_ledger_path
from codegen_eval.openrouter_client import HttpTransport, OpenRouterClient, Transport
from codegen_eval.openrouter_config import (
    DEFAULT_MODEL_CONFIG, ModelConfig, PriceInputs, load_model_config,
)
from codegen_eval.run_checks import TOOL_SCHEMA
from codegen_eval.run_recording import ROOT, run_recorded
from codegen_eval.sandbox import execute_check
from codegen_eval.tasks import load_benchmark

API_KEY_ENV = "OPENROUTER_API_KEY"
REFUSED = 2


def _print_ledger(ledger: Ledger) -> None:
    state = ledger.state()
    print(f"ledger: {ledger.path}")
    print(f"committed CHF {state.committed}; reserved CHF {state.reserved} "
          f"({len(state.outstanding)} outstanding); total CHF {state.total}")
    print(f"checkpoint CHF {ledger.checkpoint_chf} logged: {state.checkpoint_logged}; "
          f"ceiling CHF {ledger.ceiling_chf}")


def run_smoke(config: ModelConfig, prices: PriceInputs, ledger: Ledger, api_key: str,
              transport: Transport, *, benchmark: str | Path, task_id: str | None,
              bundle_root: str | Path, runner: Callable[..., Any] = execute_check,
              sleep: Callable[[float], None] | None = None) -> int:
    tasks = load_benchmark(benchmark)
    if task_id:
        tasks = tuple(t for t in tasks if t.id == task_id)
        if not tasks:
            print(f"no task {task_id!r} in {benchmark}", file=sys.stderr)
            return REFUSED
    tasks = tasks[:1]
    kwargs = {"sleep": sleep} if sleep else {}

    def client_for(task: Any, trial_id: str) -> OpenRouterClient:
        return OpenRouterClient(config, prices, ledger, api_key, transport,
                                tool_definitions=(TOOL_SCHEMA,),
                                context={"purpose": "smoke", "task_id": task.id,
                                         "trial_id": trial_id}, **kwargs)

    path, verification = run_recorded(tasks, client_for, benchmark, bundle_root=bundle_root,
                                      runner=runner, model_settings=config.identity())
    print(f"bundle: {path}")
    print(f"recorded {len(verification.recorded)} of {len(verification.planned)} planned trials; "
          f"complete={verification.complete}")
    for trial_id in verification.recorded:
        record = load_trial(path, trial_id)
        print(f"trial {trial_id}: status={record['status']} label={record['label']} "
              f"infrastructure={record['infrastructure_status']}")
        for attempt in record["attempts"]:
            print("  attempt call={call} retry={retry_index} outcome={outcome} provider={provider} "
                  "model={returned_model} prompt_tokens={prompt_tokens} completion_tokens="
                  "{completion_tokens} cost_usd={reported_cost_usd} bound={input_token_bound} "
                  "missing={missing_fields}".format(**{
                      "provider": None, "returned_model": None, "prompt_tokens": None,
                      "completion_tokens": None, "reported_cost_usd": None,
                      "missing_fields": [], **attempt}))
    _print_ledger(ledger)
    print("Inspect the trace for: tool call, development feedback, tool_choice none on call 4, "
          "final submission, completion tokens within 2000, and provider/precision metadata.")
    return 0 if verification.complete else 1


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None,
         transport: Transport | None = None, runner: Callable[..., Any] = execute_check,
         sleep: Callable[[float], None] | None = None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Live OpenRouter access and the spending ledger.")
    sub = parser.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="run one PAID smoke trial through the ledger")
    smoke.add_argument("--i-accept-cost", action="store_true",
                       help="required: confirms this command spends real money")
    smoke.add_argument("--pricing", required=True,
                       help="price/CHF inputs file (see docs/openrouter_pricing.example.json)")
    smoke.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    smoke.add_argument("--ledger", help=f"ledger file (default: ${'CODEGEN_EVAL_LEDGER'} or "
                                        f"~/.codegen_eval/spend_ledger.jsonl)")
    smoke.add_argument("--benchmark", default=str(ROOT / "data" / "benchmark_v1.json"))
    smoke.add_argument("--task", help="task id (default: the first task)")
    smoke.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    led = sub.add_parser("ledger", help="inspect or adjust the spending ledger (no API call)")
    led.add_argument("action", choices=("status", "adjust"))
    led.add_argument("--ledger")
    led.add_argument("--amount-chf")
    led.add_argument("--note")
    args = parser.parse_args(argv)

    ledger = Ledger(args.ledger) if args.ledger else Ledger(default_ledger_path(env))
    if args.command == "ledger":
        if args.action == "adjust":
            try:
                amount = Decimal(args.amount_chf or "")
                ledger.adjust(amount, args.note or "")
            except (InvalidOperation, ValueError):
                parser.error("adjust needs a positive --amount-chf and a --note")
        _print_ledger(ledger)
        return 0

    if not args.i_accept_cost:
        print("refusing to run: this command makes PAID API calls. Re-run with "
              "--i-accept-cost to confirm.", file=sys.stderr)
        return REFUSED
    api_key = env.get(API_KEY_ENV)
    if not api_key:
        print(f"refusing to run: {API_KEY_ENV} is not set.", file=sys.stderr)
        return REFUSED
    try:
        config = load_model_config(args.model_config)
        prices = PriceInputs.from_file(args.pricing)
    except (OSError, ValueError) as error:
        print(f"refusing to run: {error}", file=sys.stderr)
        return REFUSED
    print(f"worst-case reservation per attempt: CHF {prices.reservation_chf(config):.6f}; "
          f"ledger {ledger.path}")
    return run_smoke(config, prices, ledger, api_key, transport or HttpTransport(),
                     benchmark=args.benchmark, task_id=args.task, bundle_root=args.bundles,
                     runner=runner, sleep=sleep)


if __name__ == "__main__":
    sys.exit(main())
