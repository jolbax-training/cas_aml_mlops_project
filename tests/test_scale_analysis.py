"""The at-scale analysis (Wilson intervals, per-task counts, baseline/revised and
baseline/repeat, charged CHF), offline over fixture bundles."""

import hashlib
import json
import socket
from decimal import Decimal

import pytest

from codegen_eval import scale_analysis
from codegen_eval.bundle import BundleError
from codegen_eval.experiment import BASELINE, REVISED, run_variant
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.scale_analysis import analyse, charged_total, main, render, wilson_interval
from experiment_support import (
    BENCHMARK, ROOT, TASKS, local_grader, make_env, reference, solving, with_revised_prompt, wrong,
)

SCENARIOS = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")


@pytest.fixture
def env(tmp_path, monkeypatch, inprocess_runner):
    return make_env(tmp_path, inprocess_runner, revised=with_revised_prompt(monkeypatch, tmp_path))


@pytest.fixture
def grader(inprocess_runner):
    return local_grader(inprocess_runner)


def run(env, variant, client_for, grader, inprocess_runner, **kwargs):
    return run_variant(env.config, variant, client_for, grader=grader, runner=inprocess_runner,
                       **{**env.options, **kwargs})


def misses_strings_01(task):
    return wrong(task) if task.id == "strings_01" else reference(task)


def three_runs(env, grader, inprocess_runner, revised_source=misses_strings_01):
    first = run(env, BASELINE, solving(reference), grader, inprocess_runner)
    second = run(env, REVISED, solving(revised_source), grader, inprocess_runner)
    repeat = run(env, BASELINE, solving(reference), grader, inprocess_runner, allow_rerun=True)
    return {"baseline": first.run_id, "revised": second.run_id, "repeat": repeat.run_id}


# --- Wilson interval -----------------------------------------------------------------

@pytest.mark.parametrize("successes,total,expected", [
    (0, 100, (0.0, 0.0370)), (50, 100, (0.4038, 0.5962)),
    (100, 100, (0.9630, 1.0)), (29, 30, (0.8333, 0.9941)),
])
def test_wilson_interval_matches_the_formula(successes, total, expected):
    assert wilson_interval(successes, total) == expected


def test_a_perfect_run_has_an_upper_end_of_one_and_a_lower_end_below_it():
    low, high = wilson_interval(100, 100)
    assert high == 1.0 and low < 1.0


@pytest.mark.parametrize("successes,total", [(1, 0), (-1, 10), (11, 10)])
def test_wilson_interval_rejects_impossible_counts(successes, total):
    with pytest.raises(ValueError):
        wilson_interval(successes, total)


# --- three runs ----------------------------------------------------------------------

def test_three_runs_report_counts_per_task_intervals_and_both_pairs(env, grader, inprocess_runner):
    runs = three_runs(env, grader, inprocess_runner)

    result = analyse(env.config, env.bundles, runs, BENCHMARK)

    base, revised, repeat = (result["runs"][name] for name in ("baseline", "revised", "repeat"))
    assert base["primary"] == {"count": 30, "of": 30, "rate": 1.0}
    assert revised["primary"] == {"count": 27, "of": 30, "rate": 0.9}
    assert revised["per_task"]["strings_01"] == {"succeeded": 0, "trials": 3}
    assert base["per_task"]["strings_01"] == {"succeeded": 3, "trials": 3}
    low, high = wilson_interval(27, 30)
    assert (revised["wilson_95"]["lower"], revised["wilson_95"]["upper"]) == (low, high)
    assert repeat["variant"] == BASELINE and repeat["run_id"] == runs["repeat"] != base["run_id"]

    vs_revised, vs_repeat = result["pairs"]["baseline_vs_revised"], result["pairs"]["baseline_vs_repeat"]
    assert vs_revised["comparable"] and vs_revised["delta"]["primary_successes"] == -3
    assert vs_revised["delta"]["regressed_tasks"] == ["strings_01"] and vs_revised["delta"]["gained_tasks"] == []
    assert vs_revised["delta"]["intervals_overlap"] is (wilson_interval(30, 30)[0] <= high)
    assert vs_repeat["comparable"] and vs_repeat["delta"]["primary_successes"] == 0
    assert vs_repeat["delta"]["unchanged_tasks"] == sorted(t.id for t in TASKS)
    assert vs_repeat["delta"]["intervals_overlap"] is True
    text = render(result)
    assert "baseline_vs_repeat (repeat - baseline): comparable" in text
    assert "27/30 (90.0%)" in text and "descriptive aid, not a test" in text
    assert "significant" not in text.replace("no significance claim", "")


def test_output_is_deterministic(env, grader, inprocess_runner, capsys):
    runs = three_runs(env, grader, inprocess_runner)
    args = ["--config", str(env.bundles.parent / "config.json"), "--bundles", str(env.bundles),
            "--baseline", runs["baseline"], "--revised", runs["revised"], "--repeat", runs["repeat"]]
    (env.bundles.parent / "config.json").write_text(json.dumps(env.config.data))

    outputs = []
    for extra in ([], ["--json"]):
        for _ in range(2):
            assert main([*args, *extra]) == 0
            outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1] and outputs[2] == outputs[3]
    assert json.loads(outputs[2])["runs"]["revised"]["primary"]["count"] == 27


def test_a_subset_of_runs_reports_only_the_pairs_it_has(env, grader, inprocess_runner):
    runs = three_runs(env, grader, inprocess_runner)

    only_baseline = analyse(env.config, env.bundles, {"baseline": runs["baseline"]}, BENCHMARK)
    with_repeat = analyse(env.config, env.bundles,
                          {"baseline": runs["baseline"], "repeat": runs["repeat"]}, BENCHMARK)

    assert only_baseline["pairs"] == {} and list(with_repeat["pairs"]) == ["baseline_vs_repeat"]


def test_an_incomplete_run_is_labelled_and_no_difference_is_computed(env, grader, inprocess_runner):
    first = run(env, BASELINE, solving(reference), grader, inprocess_runner)
    stopped = SCENARIOS["transport_exhausted_on_call_2"]
    second = run(env, REVISED, lambda task, trial_id: FixtureClient.from_data(stopped), grader,
                 inprocess_runner)

    result = analyse(env.config, env.bundles, {"baseline": first.run_id, "revised": second.run_id}, BENCHMARK)

    revised = result["runs"]["revised"]
    assert not revised["headline_eligible"] and revised["primary"] == {"count": 0, "of": 30, "rate": 0.0}
    pair = result["pairs"]["baseline_vs_revised"]
    assert not pair["comparable"] and pair["delta"] is None
    assert any("revised run is not headline-eligible" in r for r in pair["reasons"])
    assert "NOT headline-eligible" in render(result) and "NOT comparable" in render(result)


def test_runs_that_differ_in_more_than_the_prompt_are_not_comparable(env, grader, inprocess_runner):
    runs = three_runs(env, grader, inprocess_runner)
    path = env.bundles / runs["repeat"] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["identity"]["model"]["temperature"] = 0.9
    path.write_text(json.dumps(manifest))

    result = analyse(env.config, env.bundles, runs, BENCHMARK)

    pair = result["pairs"]["baseline_vs_repeat"]
    assert not pair["comparable"] and pair["delta"] is None
    assert any("'model' differs" in r for r in pair["reasons"])
    assert result["pairs"]["baseline_vs_revised"]["comparable"]


def test_a_repeat_that_records_another_prompt_is_not_comparable(env, grader, inprocess_runner):
    runs = three_runs(env, grader, inprocess_runner)
    path = env.bundles / runs["repeat"] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["identity"]["prompt"]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))

    pair = analyse(env.config, env.bundles, runs, BENCHMARK)["pairs"]["baseline_vs_repeat"]

    assert not pair["comparable"] and any("same prompt" in r for r in pair["reasons"])


def test_an_unknown_run_is_an_error(env, capsys):
    (env.bundles.parent / "config.json").write_text(json.dumps(env.config.data))
    assert main(["--config", str(env.bundles.parent / "config.json"), "--bundles", str(env.bundles),
                 "--baseline", "no-such-run"]) == 1
    assert "no-such-run" in capsys.readouterr().err
    with pytest.raises(BundleError):
        analyse(env.config, env.bundles, {"baseline": "no-such-run"}, BENCHMARK)


# --- charged spend and the stop rule -------------------------------------------------

def test_charged_total_sums_runs_and_counts_missing_charges_as_zero():
    runs = {"baseline": {"charged_chf": 0.4}, "revised": {"charged_chf": 0.35},
            "repeat": {"charged_chf": None}}
    assert charged_total(runs) == Decimal("0.75")


def test_charged_total_above_the_limit_exits_three(env, grader, inprocess_runner, monkeypatch, capsys):
    runs = three_runs(env, grader, inprocess_runner)
    (env.bundles.parent / "config.json").write_text(json.dumps(env.config.data))
    args = ["--config", str(env.bundles.parent / "config.json"), "--bundles", str(env.bundles),
            "--baseline", runs["baseline"]]
    assert main(args) == 0 and "not exceeded" in capsys.readouterr().out

    monkeypatch.setattr(scale_analysis, "charged_total", lambda analysed: Decimal("1.0001"))
    assert main(args) == 3
    assert "EXCEEDED, stop and ask the user" in capsys.readouterr().out
    monkeypatch.setattr(scale_analysis, "charged_total", lambda analysed: Decimal("1"))
    assert main(args) == 0                                           # the limit itself is allowed


# --- the analysis only reads the bundles ----------------------------------------------

def snapshot(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns,
                   hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "")
                  for p in root.rglob("*"))


def test_the_analysis_opens_no_ledger_and_no_network_and_writes_nothing(
        env, grader, inprocess_runner, tmp_path, monkeypatch, capsys):
    runs = three_runs(env, grader, inprocess_runner)
    config = tmp_path / "analysis_config.json"
    config.write_text(json.dumps(env.config.data))
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    (sealed / "ledger.jsonl").write_text("{}")
    sealed.chmod(0o000)
    monkeypatch.setenv("CODEGEN_EVAL_LEDGER", str(sealed / "ledger.jsonl"))

    def forbidden(*args, **kwargs):
        raise AssertionError("the analysis must not touch the ledger or the network")

    monkeypatch.setattr("codegen_eval.ledger.Ledger.__init__", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    before = snapshot(env.bundles)
    try:
        status = main(["--config", str(config), "--bundles", str(env.bundles),
                       "--baseline", runs["baseline"], "--revised", runs["revised"],
                       "--repeat", runs["repeat"], "--json"])
    finally:
        sealed.chmod(0o700)

    assert status == 0 and capsys.readouterr().out
    assert snapshot(env.bundles) == before


def test_a_non_numeric_charged_limit_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_:
        main(["--baseline", "x", "--charged-limit-chf", "one"])
    assert exit_.value.code == 2 and "not a number" in capsys.readouterr().err
