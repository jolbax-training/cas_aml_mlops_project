import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from codegen_eval import bundle
from codegen_eval.bundle import load_partial_calls, load_trial, verify_bundle
from codegen_eval.ledger import Ledger
from codegen_eval.openrouter_cli import main
from codegen_eval.openrouter_client import OpenRouterClient
from codegen_eval.openrouter_config import ModelConfig
from codegen_eval.run_checks import TOOL_SCHEMA
from codegen_eval.run_recording import run_recorded
from codegen_eval.tasks import load_benchmark
from openrouter_support import (
    KEY, PRICES, TIMEOUT, FakeTransport, error_reply, ledger_events, reply, tool_call,
)

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
TASK = load_benchmark(BENCHMARK)[0]
SOURCE = "def count_vowels(s: str) -> int:\n    return sum(c in 'aeiou' for c in s.lower())\n"
CALL = tool_call(json.dumps({"source": SOURCE, "checks": [{"arguments": ["abc"], "expected": 1}]}))


def pricing_file(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(PRICES.to_dict()))
    return str(path)


def smoke_args(tmp_path, *extra):
    return ["smoke", "--pricing", pricing_file(tmp_path), "--ledger", str(tmp_path / "l.jsonl"),
            "--bundles", str(tmp_path / "bundles"), "--task", TASK.id, *extra]


def test_smoke_refuses_without_the_cost_flag_and_makes_no_call_or_file(tmp_path, capsys):
    transport = FakeTransport()

    code = main(smoke_args(tmp_path), env={"OPENROUTER_API_KEY": KEY}, transport=transport)

    assert code == 2 and "--i-accept-cost" in capsys.readouterr().err
    assert transport.calls == [] and not (tmp_path / "l.jsonl").exists()
    assert not (tmp_path / "bundles").exists()


def test_smoke_refuses_without_an_api_key(tmp_path, capsys):
    transport = FakeTransport()

    for env in ({}, {"OPENROUTER_API_KEY": ""}):
        assert main(smoke_args(tmp_path, "--i-accept-cost"), env=env, transport=transport) == 2
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err
    assert transport.calls == [] and not (tmp_path / "bundles").exists()


def test_smoke_refuses_without_complete_price_inputs(tmp_path, capsys):
    path = tmp_path / "prices.json"
    path.write_text((ROOT / "docs" / "openrouter_pricing.example.json").read_text())
    args = ["smoke", "--pricing", str(path), "--i-accept-cost", "--ledger", str(tmp_path / "l")]

    assert main(args, env={"OPENROUTER_API_KEY": KEY}, transport=FakeTransport()) == 2
    assert "chf_per_usd" in capsys.readouterr().err


def test_smoke_with_a_fake_transport_runs_through_ledger_and_bundle(tmp_path, inprocess_runner,
                                                                    capsys):
    transport = FakeTransport(reply(None, tool_calls=[CALL]), reply(SOURCE))

    code = main(smoke_args(tmp_path, "--i-accept-cost"), env={"OPENROUTER_API_KEY": KEY},
                transport=transport, runner=inprocess_runner)

    out = capsys.readouterr().out
    assert code == 0 and "complete=True" in out and "provider=OpenInference" in out
    assert [c["body"]["tool_choice"] for c in transport.calls] == ["auto", "auto"]
    (run,) = (tmp_path / "bundles").iterdir()
    trial = load_trial(run, f"{TASK.id}-t1")
    assert trial["status"] == "submitted" and trial["model_calls"] == 2
    assert [a["call"] for a in trial["attempts"]] == [1, 2]
    assert trial["reservation"]["attempts_reserved"] == 2 and trial["latency_ms"] is not None
    assert trial["usage"]["prompt_tokens"] == 2000
    manifest = bundle.load_manifest(run)
    assert manifest["identity"]["model"]["config_hash"] == ModelConfig().config_hash()
    assert KEY not in "".join(f.read_text() for f in run.rglob("*") if f.is_file())
    assert KEY not in (tmp_path / "l.jsonl").read_text() and KEY not in out
    assert manifest["redactions"] == 0 and "bound/actual=" in out
    state = Ledger(tmp_path / "l.jsonl").state()
    assert state.reserved == 0 and state.committed == Decimal("0.0004") * PRICES.chf_per_usd


def make_run(tmp_path, transport, ledger, runner, trials=2, run_id="run-x"):
    config = ModelConfig()

    def client_for(task, trial_id):
        return OpenRouterClient(config, PRICES, ledger, KEY, transport,
                                tool_definitions=(TOOL_SCHEMA,), sleep=lambda s: None,
                                context={"trial_id": trial_id})

    return run_recorded([TASK], client_for, BENCHMARK, bundle_root=tmp_path / "b",
                        run_id=run_id, trials_per_task=trials, runner=runner,
                        model_settings=config.identity())


def test_physical_attempts_including_retries_are_stored_in_the_trial_record(tmp_path,
                                                                            inprocess_runner):
    transport = FakeTransport(TIMEOUT, reply(SOURCE))
    ledger = Ledger(tmp_path / "l.jsonl")

    path, result = make_run(tmp_path, transport, ledger, inprocess_runner, trials=1)

    trial = load_trial(path, f"{TASK.id}-t1")
    assert [(a["retry_index"], a["error_class"]) for a in trial["attempts"]] == [(0, "timeout"),
                                                                                 (1, None)]
    assert trial["errors"] == ["timeout"] and trial["model_calls"] == 1
    assert trial["reservation"]["attempts_reserved"] == 2
    assert result.complete  # a recovered retry leaves the run complete


def test_exhausted_retries_leave_the_bundle_incomplete(tmp_path, inprocess_runner):
    transport = FakeTransport(error_reply(503), error_reply(503), reply(SOURCE))

    path, result = make_run(tmp_path, transport, Ledger(tmp_path / "l.jsonl"), inprocess_runner,
                            trials=2)

    assert not result.complete
    assert load_trial(path, f"{TASK.id}-t1")["infrastructure_status"] == "transport_exhausted"
    assert any(p.kind == "infrastructure_stop" for p in result.problems)


def test_ceiling_stops_the_run_preserves_the_bundle_and_marks_it_incomplete(tmp_path,
                                                                            inprocess_runner):
    amount = PRICES.reservation_chf(ModelConfig())
    ledger = Ledger(tmp_path / "l.jsonl", checkpoint_chf=amount, ceiling_chf=amount * 2)
    transport = FakeTransport(TIMEOUT, TIMEOUT)  # trial 1 keeps two reservations; trial 2 is refused

    path, result = make_run(tmp_path, transport, ledger, inprocess_runner, trials=3)

    assert not result.complete and len(transport.calls) == 2
    assert result.recorded == (f"{TASK.id}-t1", f"{TASK.id}-t2")
    assert result.missing() == (f"{TASK.id}-t3",)
    manifest = bundle.load_manifest(path)
    assert manifest["status"] == "incomplete"
    assert any("budget_ceiling" in r for r in manifest["reasons"])
    assert load_trial(path, f"{TASK.id}-t1")["infrastructure_status"] == "transport_exhausted"
    blocked = load_trial(path, f"{TASK.id}-t2")
    assert blocked["infrastructure_status"] == "budget_ceiling"
    assert blocked["attempts"][-1]["outcome"] == "budget_refused"
    assert ledger_events(ledger)[-1]["event"] == "refusal"


def test_attempts_reach_the_incremental_call_log_before_the_trial_finishes(tmp_path,
                                                                           inprocess_runner):
    transport = FakeTransport(reply(None, tool_calls=[CALL]), RuntimeError("crash"))

    with pytest.raises(RuntimeError):
        make_run(tmp_path, transport, Ledger(tmp_path / "l.jsonl"), inprocess_runner, trials=1)

    entries = load_partial_calls(tmp_path / "b" / "run-x", f"{TASK.id}-t1")
    kinds = [(e["event"], e.get("call")) for e in entries]
    assert ("attempt", None) in kinds and kinds.count(("attempt", None)) == 2
    assert [e["attempt"]["outcome"] for e in entries if e["event"] == "attempt"] == [
        "response", "client_error"]
    assert not verify_bundle(tmp_path / "b" / "run-x").complete


def test_ledger_subcommand_reports_and_adjusts_without_any_api_use(tmp_path, capsys):
    path = str(tmp_path / "l.jsonl")

    assert main(["ledger", "adjust", "--ledger", path, "--amount-chf", "0.40",
                 "--note", "earlier manual calls"], env={}) == 0
    out = capsys.readouterr().out
    assert "committed CHF 0.40" in out and "ceiling CHF 15" in out
    assert main(["ledger", "status", "--ledger", path], env={}) == 0
    with pytest.raises(SystemExit):
        main(["ledger", "adjust", "--ledger", path, "--amount-chf", "x"], env={})


def test_the_api_key_is_registered_for_redaction_even_outside_the_environment(tmp_path,
                                                                              inprocess_runner):
    leak = reply(f"def f():\n    return '{KEY}'\n")
    transport = FakeTransport(leak)
    ledger = Ledger(tmp_path / "l.jsonl")
    config = ModelConfig()
    client = OpenRouterClient(config, PRICES, ledger, KEY, transport, tool_definitions=(TOOL_SCHEMA,))

    path, _ = run_recorded([TASK], lambda t, i: client, BENCHMARK, bundle_root=tmp_path / "b",
                           run_id="run-k", runner=inprocess_runner, extra_secrets=(KEY,))

    text = "".join(f.read_text() for f in path.rglob("*.json"))
    assert KEY not in text and bundle.REDACTED in text


# --- smoke --exercise-final-only (section 5) ----------------------------------------

def tool_reply(n, prompt_tokens=700):
    usage = {"prompt_tokens": prompt_tokens, "completion_tokens": 50, "total_tokens": prompt_tokens + 50,
             "cost": 0.0001}
    return reply(None, tool_calls=[{**CALL, "id": f"call_{n}"}], usage=usage, finish="tool_calls")


def forced_run(tmp_path, runner, replies, *extra):
    transport = FakeTransport(*replies)
    code = main(smoke_args(tmp_path, "--i-accept-cost", *extra), env={"OPENROUTER_API_KEY": KEY},
                transport=transport, runner=runner)
    (run,) = (tmp_path / "bundles").iterdir()
    return code, transport, run


def final_reply(prompt_tokens=700):
    return reply(SOURCE, usage={"prompt_tokens": prompt_tokens, "completion_tokens": 50,
                                "total_tokens": prompt_tokens + 50, "cost": 0.0001})


def test_exercise_final_only_reaches_a_real_fourth_call_that_calibrates(tmp_path, inprocess_runner):
    from codegen_eval.experiment import calibrate
    from codegen_eval.openrouter_cli import SMOKE_FINAL_ONLY_INSTRUCTION

    code, transport, run = forced_run(
        tmp_path, inprocess_runner, [tool_reply(0), tool_reply(1), tool_reply(2), final_reply()],
        "--exercise-final-only")

    assert code == 0
    bodies = [c["body"] for c in transport.calls]
    assert [b["tool_choice"] for b in bodies] == ["auto", "auto", "auto", "none"]
    assert bodies[3]["tools"] == bodies[0]["tools"] and bodies[3]["tools"]   # tools resent
    assert len(bodies[3]["messages"]) == 2 + 3 * 2                             # full history
    assert bodies[0]["messages"][1]["content"].endswith(SMOKE_FINAL_ONLY_INSTRUCTION)
    identity = bundle.load_manifest(run)["identity"]
    assert identity["smoke"]["mode"] == "exercise_final_only"
    assert identity["smoke"]["instruction_sha256"] == hashlib.sha256(
        SMOKE_FINAL_ONLY_INSTRUCTION.encode()).hexdigest()
    result = calibrate(run, ModelConfig())
    assert result.ok and result.fourth_call_observed, result.problems


def test_exercise_final_only_leaves_agent_limits_prompt_and_config_hash_unchanged(
        tmp_path, inprocess_runner):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, _, plain = forced_run(tmp_path / "a", inprocess_runner, [final_reply()])
    _, _, forced = forced_run(tmp_path / "b", inprocess_runner,
                              [tool_reply(0), tool_reply(1), tool_reply(2), final_reply()],
                              "--exercise-final-only")
    a, b = (bundle.load_manifest(p)["identity"] for p in (plain, forced))
    for section in ("model", "prompt", "agent_limits", "execution_limits", "benchmark"):
        assert a[section] == b[section], section
    recorded = json.loads((ROOT / "experiments" / "prompt_comparison_v1.json").read_text())
    assert b["model"]["config_hash"] == recorded["settings"]["model_config_hash"]
    assert b["model"]["config_hash"] == ModelConfig().config_hash()
    assert "smoke" not in a


def test_without_the_flag_requests_and_identity_match_the_golden_fixture(tmp_path, inprocess_runner):
    golden = json.loads((ROOT / "tests" / "fixtures" / "smoke_golden.json").read_text())
    _, transport, run = forced_run(tmp_path, inprocess_runner, [reply(SOURCE)])
    identity = bundle.load_manifest(run)["identity"]

    assert transport.calls[0]["body"] == golden["first_request_body"]
    assert {k: identity[k] for k in golden["identity"]} == golden["identity"]
    assert "smoke" not in identity


def test_exercise_final_only_still_fails_calibration_when_the_model_submits_early(
        tmp_path, inprocess_runner):
    from codegen_eval.experiment import calibrate

    code, transport, run = forced_run(tmp_path, inprocess_runner,
                                      [tool_reply(0), final_reply()], "--exercise-final-only")

    assert code == 0 and len(transport.calls) == 2           # no automatic paid retry
    result = calibrate(run, ModelConfig())
    assert not result.ok and any("no final-only call" in p for p in result.problems)
