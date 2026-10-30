"""Trusted host CLI for the prompt-comparison experiment.

Offline commands (no network, no key): `build-config`, `record-probes`, `calibrate`,
`freeze-settings`, `check`, `compare`. `run` makes PAID calls through the ledger and refuses
without `--i-accept-cost`, the key, and every precondition. This module and `openrouter_cli`
are the only places that read `OPENROUTER_API_KEY`.

    python -m codegen_eval.experiment_cli build-config --check
    python -m codegen_eval.experiment_cli check --variant baseline --pricing ~/prices.json
    python -m codegen_eval.experiment_cli run --variant baseline --pricing ~/prices.json --i-accept-cost
    python -m codegen_eval.experiment_cli compare --baseline RUN_A --revised RUN_B
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from codegen_eval.bundle import DEFAULT_BUNDLE_ROOT, BundleError, resolve_bundle
from codegen_eval.comparison import compare_runs, render_comparison
from codegen_eval.experiment import (
    DEFAULT_BENCHMARK, DEFAULT_CONFIG, DEFAULT_EVIDENCE_DIR, VARIANTS, ExperimentError,
    PreconditionsFailed, build_config, calibrate, check_preconditions, load_config,
    run_variant, write_config, write_probes_evidence, write_settings_freeze, config_drift,
)
from codegen_eval.ledger import Ledger, default_ledger_path
from codegen_eval.openrouter_cli import API_KEY_ENV, REFUSED
from codegen_eval.openrouter_client import HttpTransport, OpenRouterClient, Transport
from codegen_eval.openrouter_config import PriceInputs, load_model_config
from codegen_eval.run_checks import TOOL_SCHEMA
from codegen_eval.run_recording import ROOT
from codegen_eval.sandbox import execute_check

PROBE_COMMAND = ("-m", "pytest", "-q", "-m", "sandbox")


def run_probe_suite(argv: Sequence[str] = PROBE_COMMAND) -> dict[str, int]:
    """Run the Podman probe tests and return the junit counts. The tests skip without the
    sandbox switches, and skips are recorded, so a skipped suite can never pass the gate."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "junit.xml"
        env = {**os.environ, "CODEGEN_EVAL_TEST_SECRET": "present", "RUN_SANDBOX_TESTS": "1"}
        subprocess.run([sys.executable, *argv, f"--junitxml={report}"], cwd=ROOT, env=env, check=False)
        suites = ElementTree.parse(report).getroot()
        suite = suites if suites.tag == "testsuite" else suites.find("testsuite")
        return {key: int(suite.attrib.get(key, 0)) for key in ("tests", "failures", "errors", "skipped")}


def _ledger(args: argparse.Namespace, env: Mapping[str, str]) -> Ledger:
    return Ledger(args.ledger) if args.ledger else Ledger(default_ledger_path(env))


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None,
         transport: Transport | None = None, runner: Callable[..., Any] = execute_check,
         sleep: Callable[[float], None] | None = None,
         probe_suite: Callable[[], dict[str, int]] = run_probe_suite,
         grader: Any = None, record_run: Callable[[Path, str], str | None] | None = None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Prompt-comparison experiment tooling.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default=str(DEFAULT_CONFIG))
        p.add_argument("--evidence", default=str(DEFAULT_EVIDENCE_DIR))
        p.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))

    build = sub.add_parser("build-config", help="write or verify the versioned experiment configuration")
    common(build)
    build.add_argument("--revised-prompt", help="version (file stem) of the revised prompt, once it exists")
    build.add_argument("--check", action="store_true",
                       help="only verify the recorded configuration matches the repository")
    common(sub.add_parser("record-probes",
                          help="run the Podman probe suite and record its counts as evidence"))
    cal = sub.add_parser("calibrate", help="calibrate the pre-send bound from a retained smoke bundle")
    common(cal)
    cal.add_argument("--smoke-bundle", required=True)
    freeze = sub.add_parser("freeze-settings", help="record the settings freeze (only after calibration passes)")
    common(freeze)
    freeze.add_argument("--smoke-bundle", required=True)
    freeze.add_argument("--note", default="")
    for name in ("check", "run"):
        p = sub.add_parser(name, help=("report unmet preconditions" if name == "check"
                                       else "run one variant's schedule (PAID)"))
        common(p)
        p.add_argument("--variant", required=True, choices=VARIANTS)
        p.add_argument("--pricing", help="price/CHF inputs file")
        p.add_argument("--ledger")
        p.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
        p.add_argument("--smoke-bundle")
        p.add_argument("--i-accept-cost", action="store_true",
                       help="required: confirms this command spends real money")
        p.add_argument("--allow-rerun", action="store_true",
                       help="start a variant that already has a run (spends again; record the decision)")
    cmp_ = sub.add_parser("compare", help="primary metric and diagnostics for two runs (offline)")
    common(cmp_)
    cmp_.add_argument("--baseline", required=True)
    cmp_.add_argument("--revised", required=True)
    cmp_.add_argument("--bundles", default=DEFAULT_BUNDLE_ROOT)
    cmp_.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "record-probes":
            path = write_probes_evidence(args.evidence, probe_suite(),
                                         command="python " + " ".join(PROBE_COMMAND))
            print(f"probe evidence: {path}")
            return 0
        if args.command == "build-config":
            if args.check:
                drift = config_drift(load_config(args.config), benchmark_path=args.benchmark)
                for line in drift:
                    print(f"drift: {line}")
                print("configuration matches the repository" if not drift else "configuration is stale")
                return 1 if drift else 0
            current = load_config(args.config) if Path(args.config).is_file() else None
            revised = args.revised_prompt or (current.variant("revised")["prompt_version"] if current else None)
            path = write_config(build_config(args.benchmark, revised_prompt=revised), args.config)
            print(f"wrote {path}")
            return 0
        config = load_config(args.config)
        if args.command == "calibrate":
            calibration = calibrate(args.smoke_bundle,
                                    load_model_config(config.data["settings"]["model_config_version"]))
            print(json.dumps(calibration.to_dict(), indent=2))
            return 0 if calibration.ok else 1
        if args.command == "freeze-settings":
            print(f"freeze record: {write_settings_freeze(config, args.smoke_bundle, args.evidence, note=args.note)}")
            return 0
        if args.command == "compare":
            result = compare_runs(resolve_bundle(args.bundles, args.baseline),
                                  resolve_bundle(args.bundles, args.revised), args.benchmark, config)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else render_comparison(result))
            return 0 if result["headline_comparison"] else 1
    except (ExperimentError, BundleError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    # check / run
    ledger = _ledger(args, env)
    api_key = env.get(API_KEY_ENV)
    try:
        prices = PriceInputs.from_file(args.pricing) if args.pricing else None
    except (OSError, ValueError) as error:
        print(f"refusing to run: {error}", file=sys.stderr)
        return REFUSED
    options = dict(ledger=ledger, prices=prices, accept_cost=args.i_accept_cost, api_key=api_key,
                   evidence_dir=args.evidence, bundle_root=args.bundles, benchmark_path=args.benchmark,
                   smoke_bundle=args.smoke_bundle, allow_rerun=args.allow_rerun)
    if args.command == "check":
        failures = check_preconditions(config, args.variant, **options)
        for failure in failures:
            print(f"unmet: {failure.check}: {failure.detail}")
        print("all preconditions hold" if not failures else f"{len(failures)} unmet precondition(s)")
        return 1 if failures else 0

    model = load_model_config(config.data["settings"]["model_config_version"])
    http = transport or HttpTransport()
    kwargs = {"sleep": sleep} if sleep else {}

    def client_for(task: Any, trial_id: str) -> OpenRouterClient:
        return OpenRouterClient(model, prices, ledger, api_key, http, tool_definitions=(TOOL_SCHEMA,),
                                context={"purpose": "experiment", "experiment_id": config.experiment_id,
                                         "variant": args.variant, "task_id": task.id,
                                         "trial_id": trial_id}, **kwargs)

    try:
        result = run_variant(config, args.variant, client_for, runner=runner, grader=grader,
                             record_run=record_run, **options)
    except PreconditionsFailed as error:
        for failure in error.failures:
            print(f"refusing to run: {failure.check}: {failure.detail}", file=sys.stderr)
        return REFUSED
    print(f"bundle: {result.bundle}")
    print(f"complete={result.complete}; ledger CHF {result.ledger_total_before_chf} -> "
          f"{result.ledger_total_after_chf}; tracking: {result.tracking}")
    for problem in result.schedule.problems:
        print(f"schedule: {problem}")
    return 0 if result.complete else 1


if __name__ == "__main__":
    sys.exit(main())
