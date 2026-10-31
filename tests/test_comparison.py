"""Primary metric and diagnostics for two variants, and the experiment CLI, offline."""

import json

import pytest

from codegen_eval.comparison import compare_runs, render_comparison, variant_metrics
from codegen_eval.bundle import BundleError, load_manifest
from codegen_eval.experiment import (
    BASELINE, REVISED, build_config, parse_config, probes_problems, run_variant,
)
from codegen_eval.experiment_cli import main
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.summary import summarize_bundle
from experiment_support import (
    BENCHMARK, JUNIT, ROOT, TASKS, make_env, local_grader, real_prompt_file, reference, solving, with_revised_prompt, wrong,
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
    assert metrics["model_latency_ms"]["trials_measured"] == 0 and metrics["cost"]["reported_usd"] is None
    assert metrics["trial_wall_clock_ms"]["trials_measured"] == 30        # from started_at to the record


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


def test_record_probes_writes_evidence_and_keeps_the_report(tmp_path, capsys):
    code = main(["record-probes", "--evidence", str(tmp_path)], env={},
                probe_suite=lambda: {"tests": 56, "failures": 0, "errors": 0, "skipped": 0,
                                     "junit_xml": JUNIT})

    record = json.loads((tmp_path / "probes.json").read_text())
    assert code == 0 and record["tests"] == 56 and (tmp_path / "probes.junit.xml").read_text() == JUNIT
    assert probes_problems(tmp_path) == []


# --- the real protocol order (review finding 1) ------------------------------------

def protocol_runs(tmp_path, inprocess_runner, grader, *, revised_source=reference):
    """Baseline first with the revised variant unset, then the revised prompt file is added to
    the repository, the configuration is rebuilt, and the revised schedule is run."""
    env = make_env(tmp_path, inprocess_runner)
    assert env.config.variant(REVISED)["prompt_version"] is None
    base = run(env, BASELINE, solving(baseline_misses_strings_01), grader, inprocess_runner)
    with real_prompt_file() as revised:
        config = parse_config(build_config(BENCHMARK, revised_prompt=revised))
        rev = run_variant(config, REVISED, solving(revised_source), grader=grader,
                          runner=inprocess_runner, **env.options)
    return env, config, base, rev


def test_following_the_protocol_order_gives_a_headline_comparison(tmp_path, inprocess_runner, grader):
    env, config, base, rev = protocol_runs(tmp_path, inprocess_runner, grader)

    assert base.complete and rev.complete
    result = compare_runs(base.bundle, rev.bundle, BENCHMARK, config)

    assert result["headline_comparison"], result["reasons_not_headline"]
    assert result["delta"]["gained_tasks"] == ["strings_01"]
    # Adding the prompt file changes the source-tree hash (and usually the Git state); that is
    # reported, not treated as a different evaluator.
    assert any("evaluator_source_sha256 differs" in c for c in result["caveats"])
    assert "note: evaluator_source_sha256 differs" in render_comparison(result)
    ids = (load_manifest(base.bundle)["identity"], load_manifest(rev.bundle)["identity"])
    assert ids[0]["experiment"]["evaluator_code_sha256"] == ids[1]["experiment"]["evaluator_code_sha256"]
    assert ids[0]["experiment"]["config_sha256"] != ids[1]["experiment"]["config_sha256"]
    assert ids[0]["evaluator_source_sha256"] != ids[1]["evaluator_source_sha256"]
    assert ids[0]["prompt"]["version"] != ids[1]["prompt"]["version"]


def tamper(bundle, change):
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest["identity"])
    path.write_text(json.dumps(manifest))


@pytest.mark.parametrize("name,change", [
    ("model settings", lambda i: i["model"].update(temperature=0.9)),
    ("model settings hash", lambda i: i["model"].update(config_hash="0" * 64)),
    ("benchmark hash", lambda i: i["benchmark"].update(sha256="0" * 64)),
    ("benchmark freeze hash", lambda i: i["benchmark"].update(freeze_content_hash="0" * 64)),
    ("agent limits", lambda i: i["agent_limits"].update(max_model_calls=5)),
    ("execution limits", lambda i: i["execution_limits"].update(hash="0" * 64)),
    ("container image", lambda i: i.update(container_image="other@sha256:0")),
    ("dependencies", lambda i: i["dependencies"].update(uv_lock_sha256="0" * 64)),
    ("runtime", lambda i: i["runtime"].update(python="3.11.0")),
    ("settings hash", lambda i: i["experiment"].update(settings_hash="0" * 64)),
    ("schedule", lambda i: i["experiment"].update(schedule_sha256="0" * 64)),
    ("trial order", lambda i: i["experiment"].update(trial_order="trial_major")),
    ("experiment id", lambda i: i["experiment"].update(experiment_id="other")),
    ("evaluator code", lambda i: i["experiment"].update(evaluator_code_sha256="0" * 64)),
    ("baseline prompt file", lambda i: i["experiment"]["prompt_files"].update(baseline_agent_v1="0" * 64)),
    ("code hash not recorded", lambda i: i["experiment"].pop("evaluator_code_sha256")),
])
def test_any_other_difference_than_the_prompt_variant_blocks_the_headline(
        tmp_path, inprocess_runner, grader, name, change):
    env, config, base, rev = protocol_runs(tmp_path, inprocess_runner, grader)
    tamper(rev.bundle, change)

    try:
        result = compare_runs(base.bundle, rev.bundle, BENCHMARK, config)
    except BundleError:      # a benchmark that is not the recorded one is refused outright
        return
    assert not result["headline_comparison"] and result["delta"] is None, name
    assert result["reasons_not_headline"], name


def test_a_changed_baseline_prompt_file_is_not_a_prompt_variant(tmp_path, inprocess_runner, grader):
    env, config, base, rev = protocol_runs(tmp_path, inprocess_runner, grader)
    tamper(base.bundle, lambda i: i["experiment"]["prompt_files"].update(baseline_agent_v1="0" * 64))

    result = compare_runs(base.bundle, rev.bundle, BENCHMARK, config)

    assert not result["headline_comparison"]
    assert any("prompt files other than the revised one" in r for r in result["reasons_not_headline"])
