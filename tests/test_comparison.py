"""Primary metric and diagnostics for two variants, and the experiment CLI, offline."""

import json

import pytest

from codegen_eval.comparison import compare_runs, render_comparison, variant_metrics
from codegen_eval.experiment import BASELINE, REVISED, run_variant
from codegen_eval.experiment_cli import main
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.summary import summarize_bundle
from experiment_support import (
    BENCHMARK, ROOT, TASKS, make_env, local_grader, reference, solving, with_revised_prompt, wrong,
)
from openrouter_support import KEY, PRICES, FakeTransport, reply

SCENARIOS = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")


@pytest.fixture
def grader(inprocess_runner):
    return local_grader(inprocess_runner)


@pytest.fixture
def env(tmp_path, monkeypatch, inprocess_runner):
    return make_env(tmp_path, inprocess_runner, revised=with_revised_prompt(monkeypatch, tmp_path))


def run(env, variant, client_for, grader, inprocess_runner, **kwargs):
    return run_variant(env.config, variant, client_for, grader=grader, runner=inprocess_runner,
                       **{**env.options, **kwargs})


def baseline_misses_strings_01(task):
    return wrong(task) if task.id == "strings_01" else reference(task)


def test_headline_comparison_reports_counts_rates_and_task_level_differences(
        env, grader, inprocess_runner):
    base = run(env, BASELINE, solving(baseline_misses_strings_01), grader, inprocess_runner)
    rev = run(env, REVISED, solving(reference), grader, inprocess_runner)

    result = compare_runs(base.bundle, rev.bundle, BENCHMARK, env.config)

    assert result["headline_comparison"] and result["reasons_not_headline"] == []
    b, r = (result["runs"][name]["metrics"] for name in (BASELINE, REVISED))
    assert b["primary"] == {"count": 27, "of": 30, "rate": 0.9}
    assert r["primary"] == {"count": 30, "of": 30, "rate": 1.0}
    assert b["hidden_checks"]["count"] == 108 and b["hidden_checks"]["of"] == 120
    assert (b["edge_cases"]["count"], b["edge_cases"]["of"]) == (54, 60)
    assert (r["edge_cases"]["count"], r["edge_cases"]["of"]) == (60, 60)
    assert b["tasks_passing_at_least_one_trial"]["count"] == 9 and b["tasks_passing_every_trial"]["count"] == 9
    assert b["per_task"]["strings_01"] == {"succeeded": 0, "trials": 3}
    assert b["categories"]["strings"] == {"count": 3, "of": 6, "rate": 0.5}
    assert b["failure_labels"]["wrong_answer"] == 3
    assert result["delta"] == {"primary_successes": 3, "primary_rate": pytest.approx(0.1),
                               "gained_tasks": ["strings_01"], "regressed_tasks": [],
                               "unchanged_tasks": sorted(t.id for t in TASKS if t.id != "strings_01")}
    assert result["runs"][REVISED]["prompt"]["version"] == "revised_test_v1"
    text = render_comparison(result)
    assert "27/30 (90.0%)" in text and "+3 successful trials" in text and "gained tasks: ['strings_01']" in text


def test_a_regression_is_reported_as_such(env, grader, inprocess_runner):
    base = run(env, BASELINE, solving(reference), grader, inprocess_runner)
    rev = run(env, REVISED, solving(baseline_misses_strings_01), grader, inprocess_runner)

    delta = compare_runs(base.bundle, rev.bundle, BENCHMARK, env.config)["delta"]

    assert delta["primary_successes"] == -3 and delta["regressed_tasks"] == ["strings_01"]
    assert delta["gained_tasks"] == []


def test_an_incomplete_run_is_not_headline_and_keeps_planned_denominators(env, grader, inprocess_runner):
    base = run(env, BASELINE, solving(reference), grader, inprocess_runner)
    stopped = SCENARIOS["transport_exhausted_on_call_2"]
    rev = run(env, REVISED, lambda task, trial_id: FixtureClient.from_data(stopped), grader,
              inprocess_runner)

    result = compare_runs(base.bundle, rev.bundle, BENCHMARK, env.config)

    assert not rev.complete and not result["headline_comparison"] and result["delta"] is None
    assert any("revised run is not headline-eligible" in r for r in result["reasons_not_headline"])
    revised = result["runs"][REVISED]
    assert revised["classification"]["classes"] == ["exhausted_transport"]
    assert revised["metrics"]["primary"] == {"count": 0, "of": 30, "rate": 0.0}      # not shrunk
    assert revised["metrics"]["hidden_checks"]["of"] == 120
    assert "NOT a headline comparison" in render_comparison(result)


def test_runs_that_differ_in_more_than_the_prompt_are_not_comparable(env, grader, inprocess_runner):
    base = run(env, BASELINE, solving(reference), grader, inprocess_runner)
    rev = run(env, REVISED, solving(reference), grader, inprocess_runner)
    manifest = json.loads((rev.bundle / "manifest.json").read_text())
    manifest["identity"]["model"]["temperature"] = 0.9
    (rev.bundle / "manifest.json").write_text(json.dumps(manifest))

    result = compare_runs(base.bundle, rev.bundle, BENCHMARK, env.config)

    assert not result["headline_comparison"] and result["delta"] is None
    assert any("'model' differs" in r for r in result["reasons_not_headline"])


def test_efficiency_and_recovery_diagnostics_come_from_the_records(env, grader, inprocess_runner):
    scenario = SCENARIOS["tool_use_and_revision"]

    def client_for(task, trial_id):
        if task.id == "strings_01":
            return FixtureClient.from_data(scenario)
        return solving(reference)(task, trial_id)

    base = run(env, BASELINE, client_for, grader, inprocess_runner)
    metrics = variant_metrics(base.bundle, summarize_bundle(base.bundle, BENCHMARK))

    assert metrics["tool_attempts"] == 6 and metrics["revisions"] == 3
    assert metrics["recovery"]["trials_with_failed_development_check"] == 3
    assert metrics["model_calls"] == 3 * 3 + 27
    assert metrics["trials_measured"] == 30
    assert metrics["latency_ms"]["trials_with_latency"] == 0 and metrics["cost"]["reported_usd"] is None


# --- CLI ---------------------------------------------------------------------------

def pricing_file(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(PRICES.to_dict()))
    return str(path)


def cli_args(env, tmp_path, command, *extra):
    return [command, "--variant", BASELINE, "--pricing", pricing_file(tmp_path),
            "--ledger", str(env.ledger.path), "--bundles", str(env.bundles),
            "--evidence", str(env.evidence), "--config", str(tmp_path / "config.json"), *extra]


def write_config_for(env, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(env.config.data))


def test_run_refuses_without_the_cost_flag_or_the_key_and_makes_no_call(env, tmp_path, capsys):
    write_config_for(env, tmp_path)
    transport = FakeTransport()

    code = main(cli_args(env, tmp_path, "run"), env={"OPENROUTER_API_KEY": KEY}, transport=transport)
    assert code == 2 and "cost_acceptance" in capsys.readouterr().err

    code = main(cli_args(env, tmp_path, "run", "--i-accept-cost"), env={}, transport=transport)
    assert code == 2 and "api_key" in capsys.readouterr().err
    assert transport.calls == [] and not env.bundles.exists()


def test_check_lists_unmet_preconditions_without_spending(env, tmp_path, capsys):
    write_config_for(env, tmp_path)
    (env.evidence / "probes.json").unlink()

    code = main(cli_args(env, tmp_path, "check"), env={})

    out = capsys.readouterr().out
    assert code == 1 and "unmet: probes" in out and "unmet: cost_acceptance" in out


def test_run_through_the_cli_with_a_fake_transport_writes_a_complete_bundle(
        env, tmp_path, grader, inprocess_runner, capsys):
    write_config_for(env, tmp_path)
    transport = FakeTransport(*[reply("def x():\n    pass\n") for _ in range(30)])
    seen = []

    code = main(cli_args(env, tmp_path, "run", "--i-accept-cost"), env={"OPENROUTER_API_KEY": KEY},
                transport=transport, runner=inprocess_runner, sleep=lambda s: None, grader=grader,
                record_run=lambda bundle, variant: seen.append(variant) or "mlflow:test")

    out = capsys.readouterr().out
    assert code == 0 and "complete=True" in out and "mlflow:test" in out and seen == [BASELINE]
    assert len(transport.calls) == 30
    assert {c["body"]["model"] for c in transport.calls} == {"z-ai/glm-5.3-flash"}


def test_compare_through_the_cli_exits_nonzero_unless_headline(env, tmp_path, grader, inprocess_runner, capsys):
    write_config_for(env, tmp_path)
    base = run(env, BASELINE, solving(reference), grader, inprocess_runner)
    rev = run(env, REVISED, solving(baseline_misses_strings_01), grader, inprocess_runner)
    args = ["compare", "--baseline", base.run_id, "--revised", rev.run_id, "--bundles", str(env.bundles),
            "--config", str(tmp_path / "config.json")]

    assert main([*args, "--json"], env={}) == 0
    assert json.loads(capsys.readouterr().out)["delta"]["primary_successes"] == -3

    (rev.bundle / "trials" / "lists_01-t1.json").unlink()
    assert main(args, env={}) == 1
    assert "NOT a headline comparison" in capsys.readouterr().out


def test_build_config_check_passes_on_the_committed_configuration(capsys):
    assert main(["build-config", "--check"], env={}) == 0
    assert "matches the repository" in capsys.readouterr().out


def test_record_probes_writes_evidence_from_the_suite_counts(tmp_path, capsys):
    code = main(["record-probes", "--evidence", str(tmp_path)], env={},
                probe_suite=lambda: {"tests": 56, "failures": 0, "errors": 0, "skipped": 0})

    assert code == 0 and json.loads((tmp_path / "probes.json").read_text())["tests"] == 56
