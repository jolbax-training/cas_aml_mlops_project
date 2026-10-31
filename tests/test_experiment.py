"""Experiment configuration, preconditions, and the schedule runner, offline (no network,
no Podman): fixture clients, a fake transport, and a trusted in-process check runner."""

import json
import shutil
from decimal import Decimal

import pytest

from codegen_eval.bundle import load_manifest, load_trial, verify_bundle
from codegen_eval.experiment import (
    BASELINE, DEFAULT_CONFIG, FREEZE_RECORD_FILE, MIN_BOUND_RATIO, REVISED, ExperimentError,
    PreconditionsFailed, build_config, calibrate, check_preconditions, config_drift, load_config,
    parse_config, physical_attempt_cap, probes_problems, run_variant, verify_schedule,
    write_probes_evidence, write_settings_freeze,
)
from codegen_eval.ledger import Ledger
from codegen_eval.agent_config import DEFAULT_AGENT_LIMITS
from codegen_eval.openrouter_client import OpenRouterClient
from codegen_eval.openrouter_config import ModelConfig
from codegen_eval.sandbox import HOST_PLATFORM, image_for_platform
from codegen_eval.run_checks import TOOL_SCHEMA
from experiment_support import (
    BENCHMARK, JUNIT, TASKS, make_env, make_smoke, real_prompt_file, reference, solving, local_grader,
    with_revised_prompt,
)
from openrouter_support import KEY, PRICES, FakeTransport, ledger_events, reply


@pytest.fixture
def grader(inprocess_runner):
    return local_grader(inprocess_runner)


def checks(failures):
    return {f.check for f in failures}


def never(task, trial_id):
    raise AssertionError("a client was built although the run must not start")


# --- configuration (task 1.2) ------------------------------------------------------

def test_committed_configuration_lists_variant_benchmark_settings_and_schedule():
    config = load_config(DEFAULT_CONFIG)
    data = config.data

    assert config_drift(config) == []                       # still matches the repository
    assert [v["name"] for v in data["variants"]] == [BASELINE, REVISED]
    assert data["variants"][0]["prompt_version"] == "baseline_agent_v1"
    assert data["variants"][1] == {"name": "revised", "prompt_version": None, "prompt_sha256": None}
    assert data["benchmark"]["version"] == "1" and data["benchmark"]["sha256"]
    assert data["benchmark"]["freeze_content_hash"]
    assert data["settings"]["settings_hash"] and data["settings"]["model_config_hash"]
    assert len(data["schedule"]) == 30 == len(TASKS) * data["trials_per_task"]
    assert data["schedule"][:3] == [{"task_id": "strings_01", "trial_id": f"strings_01-t{n}"}
                                    for n in (1, 2, 3)]
    assert data["trial_order"] == "task_major"


@pytest.mark.parametrize("section,mutate", [
    ("settings", lambda d: d["settings"].update(settings_hash="0" * 64)),
    ("benchmark", lambda d: d["benchmark"].update(sha256="0" * 64)),
    ("variants", lambda d: d["variants"][0].update(prompt_sha256="0" * 64)),
    ("schedule", lambda d: d["schedule"].reverse()),
])
def test_drift_names_the_section_that_no_longer_matches(section, mutate):
    data = json.loads(json.dumps(load_config(DEFAULT_CONFIG).data))
    mutate(data)

    assert any(section in line for line in config_drift(parse_config(data)))


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("schedule"),
    lambda d: d["variants"].reverse(),
    lambda d: d["variants"][1].update(prompt_version="x"),     # a version without its hash
    lambda d: d["schedule"].append(d["schedule"][0]),
])
def test_malformed_configuration_is_rejected(mutate):
    data = json.loads(json.dumps(load_config(DEFAULT_CONFIG).data))
    mutate(data)

    with pytest.raises(ExperimentError):
        parse_config(data)


def test_attempt_cap_matches_the_agreed_budget_split():
    cap = physical_attempt_cap(30, DEFAULT_AGENT_LIMITS, ModelConfig())

    assert cap == 180 and 2 * cap == 360     # 120 logical calls + 60 retries per variant


# --- evidence ----------------------------------------------------------------------

def test_probe_evidence_must_be_clean_nonempty_and_for_this_code(tmp_path):
    assert "not found" in probes_problems(tmp_path)[0]
    counts = {"tests": 10, "failures": 0, "errors": 0, "skipped": 0}
    write_probes_evidence(tmp_path, counts, command="x", junit_xml=JUNIT)
    assert probes_problems(tmp_path) == []
    write_probes_evidence(tmp_path, {**counts, "skipped": 3}, command="x", junit_xml=JUNIT)
    assert any("skipped" in p for p in probes_problems(tmp_path))      # a skipped suite proves nothing
    write_probes_evidence(tmp_path, {**counts, "tests": 0}, command="x", junit_xml=JUNIT)
    assert any("no tests" in p for p in probes_problems(tmp_path))
    write_probes_evidence(tmp_path, counts, command="x", junit_xml=JUNIT)
    record = json.loads((tmp_path / "probes.json").read_text())
    record.update(evaluator_code_sha256="0" * 64)
    (tmp_path / "probes.json").write_text(json.dumps(record))
    assert any("different evaluator code" in p for p in probes_problems(tmp_path))


def test_probe_evidence_needs_its_retained_junit_report(tmp_path):
    counts = {"tests": 10, "failures": 0, "errors": 0, "skipped": 0}
    write_probes_evidence(tmp_path, counts, command="x")                 # no report kept
    assert any("junit report" in p for p in probes_problems(tmp_path))

    write_probes_evidence(tmp_path, counts, command="x", junit_xml=JUNIT)
    assert probes_problems(tmp_path) == []
    (tmp_path / "probes.junit.xml").write_text(JUNIT.replace("56", "99"))   # edited afterwards
    assert any("junit report" in p for p in probes_problems(tmp_path))


def test_probe_evidence_survives_adding_a_prompt_file_but_not_a_code_change(
        tmp_path, monkeypatch):
    counts = {"tests": 10, "failures": 0, "errors": 0, "skipped": 0}
    write_probes_evidence(tmp_path, counts, command="x", junit_xml=JUNIT)
    with real_prompt_file():                      # a real file in src/codegen_eval/prompts
        assert probes_problems(tmp_path) == []

    monkeypatch.setattr("codegen_eval.experiment.evaluator_code_sha256", lambda: "1" * 64)
    assert any("different evaluator code" in p for p in probes_problems(tmp_path))


def test_calibration_accepts_a_pessimistic_bound_and_records_the_ratios(tmp_path, inprocess_runner):
    smoke = make_smoke(tmp_path, inprocess_runner)
    result = calibrate(smoke, ModelConfig())

    assert result.ok, result.problems
    assert result.sent_attempts == 4 and result.fourth_call_observed
    assert result.min_ratio >= MIN_BOUND_RATIO and result.max_bound <= ModelConfig().max_input_tokens


def test_calibration_fails_when_the_bound_is_below_reported_tokens(tmp_path, inprocess_runner):
    smoke = make_smoke(tmp_path, inprocess_runner, prompt_tokens=5000)
    result = calibrate(smoke, ModelConfig())

    assert not result.ok and any("at least" in p for p in result.problems)


def test_calibration_fails_for_other_settings_or_missing_usage(tmp_path, inprocess_runner):
    smoke = make_smoke(tmp_path, inprocess_runner)
    other = ModelConfig(temperature=0.3)
    assert any("different model settings" in p for p in calibrate(smoke, other).problems)

    transport = FakeTransport(reply("x", usage=None))
    bundle_root = tmp_path / "nousage"
    from codegen_eval.run_recording import run_recorded
    path, _ = run_recorded(TASKS[:1], lambda t, i: OpenRouterClient(
        ModelConfig(), PRICES, Ledger(tmp_path / "l2.jsonl"), KEY, transport,
        tool_definitions=(TOOL_SCHEMA,), sleep=lambda s: None), BENCHMARK, bundle_root=bundle_root,
        runner=inprocess_runner, model_settings=ModelConfig().identity(), extra_secrets=(KEY,))
    problems = calibrate(path, ModelConfig()).problems
    assert any("no reported prompt_tokens" in p or "cannot be calibrated" in p for p in problems)


def test_settings_freeze_is_refused_until_calibration_passes_and_names_its_evidence(
        tmp_path, inprocess_runner):
    config = parse_config(build_config(BENCHMARK))
    bad = make_smoke(tmp_path / "bad", inprocess_runner, prompt_tokens=5000)
    with pytest.raises(ExperimentError, match="calibration gate failed"):
        write_settings_freeze(config, bad, tmp_path / "evidence")
    assert not (tmp_path / "evidence" / FREEZE_RECORD_FILE).exists()

    good = make_smoke(tmp_path / "good", inprocess_runner)
    path = write_settings_freeze(config, good, tmp_path / "evidence")
    record = json.loads(path.read_text())
    assert record["decision"] == "pass" and record["smoke"]["run_id"] == "smoke-1"
    assert record["settings_hash"] == config.data["settings"]["settings_hash"]
    assert record["calibration"]["ok"] and record["calibration"]["ratios"]


# --- preconditions -----------------------------------------------------------------

OTHER_PLATFORM = "amd64" if HOST_PLATFORM == "arm64" else "arm64"


def test_committed_configuration_records_its_platform_and_the_image_pinned_for_it():
    settings = load_config(DEFAULT_CONFIG).data["settings"]

    assert settings["container_platform"] == "arm64"
    assert settings["container_image"] == image_for_platform("arm64")


@pytest.mark.parametrize("platform_name", ["arm64", "amd64"])
def test_drift_check_does_not_depend_on_the_host_architecture(platform_name):
    data = build_config(BENCHMARK, container_platform=platform_name)

    assert data["settings"]["container_image"] == image_for_platform(platform_name)
    assert config_drift(parse_config(data), benchmark_path=BENCHMARK) == []
    other = build_config(BENCHMARK, container_platform=OTHER_PLATFORM)
    assert other["settings"]["settings_hash"] != data["settings"]["settings_hash"] or \
        platform_name == OTHER_PLATFORM


def test_configuration_for_another_platform_is_drift_when_its_image_is_edited():
    data = build_config(BENCHMARK, container_platform="amd64")
    data["settings"]["container_image"] = image_for_platform("arm64")

    assert any("settings" in line for line in config_drift(parse_config(data), benchmark_path=BENCHMARK))


def test_a_host_of_another_platform_than_the_configuration_is_refused(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    recorded = env.config.data["settings"]["container_platform"]

    failures = check_preconditions(env.config, BASELINE, **env.options, host_platform=OTHER_PLATFORM)

    host = [f for f in failures if f.check == "container_host"]
    assert len(host) == 1 and recorded in host[0].detail and OTHER_PLATFORM in host[0].detail
    # Probe evidence is bound to the same platform, so it is refused too, naming both.
    probes = [f for f in failures if f.check == "probes"]
    assert probes and recorded in probes[0].detail and OTHER_PLATFORM in probes[0].detail
    assert "config_current" not in checks(failures)          # drift itself is host-independent


def test_probe_evidence_from_another_platform_does_not_count(tmp_path):
    counts = {"tests": 10, "failures": 0, "errors": 0, "skipped": 0}
    write_probes_evidence(tmp_path, counts, command="x", junit_xml=JUNIT, container_platform="amd64")

    assert probes_problems(tmp_path, "amd64") == []
    (problem,) = probes_problems(tmp_path, "arm64")
    assert "amd64" in problem and "arm64" in problem


def test_all_preconditions_met_means_no_failures(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)

    assert check_preconditions(env.config, BASELINE, **env.options) == []


@pytest.mark.parametrize("override,expected", [
    ({"accept_cost": False}, "cost_acceptance"),
    ({"api_key": None}, "api_key"),
    ({"api_key": ""}, "api_key"),
    ({"prices": None}, "budget_projection"),
])
def test_cost_acceptance_key_and_prices_are_required(tmp_path, inprocess_runner, override, expected):
    env = make_env(tmp_path, inprocess_runner, **override)

    assert expected in checks(check_preconditions(env.config, BASELINE, **env.options))


def test_each_missing_evidence_item_blocks_the_start(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    (env.evidence / "probes.json").unlink()
    assert "probes" in checks(check_preconditions(env.config, BASELINE, **env.options))

    (env.evidence / FREEZE_RECORD_FILE).unlink()
    assert "settings_frozen" in checks(check_preconditions(env.config, BASELINE, **env.options))


def test_probes_that_ran_against_other_code_do_not_count(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    record = json.loads((env.evidence / "probes.json").read_text())
    record["evaluator_code_sha256"] = "0" * 64
    (env.evidence / "probes.json").write_text(json.dumps(record))

    assert "probes" in checks(check_preconditions(env.config, BASELINE, **env.options))


def test_unfrozen_benchmark_blocks_the_start(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    copy = tmp_path / "copy" / "data"
    copy.mkdir(parents=True)
    shutil.copy(BENCHMARK, copy / "benchmark_v1.json")            # no freeze record beside it
    env.options["benchmark_path"] = copy / "benchmark_v1.json"

    assert "benchmark_freeze" in checks(check_preconditions(env.config, BASELINE, **env.options))


def test_changed_settings_after_the_freeze_block_the_start(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    record = json.loads((env.evidence / FREEZE_RECORD_FILE).read_text())
    record["settings_hash"] = "0" * 64
    (env.evidence / FREEZE_RECORD_FILE).write_text(json.dumps(record))

    assert "settings_frozen" in checks(check_preconditions(env.config, BASELINE, **env.options))


def test_missing_or_altered_smoke_trace_blocks_the_start(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    manifest = env.smoke / "manifest.json"
    original = manifest.read_text()
    manifest.write_text(original + " ")
    assert "smoke_trace" in checks(check_preconditions(env.config, BASELINE, **env.options))

    manifest.write_text(original)
    shutil.move(env.smoke, tmp_path / "elsewhere")
    assert "smoke_trace" in checks(check_preconditions(env.config, BASELINE, **env.options))


def test_failed_calibration_in_the_retained_trace_blocks_the_start(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    trial = env.smoke / "trials" / "strings_01-t1.json"
    record = json.loads(trial.read_text())
    for attempt in record["attempts"]:
        attempt["prompt_tokens"] = 99999                  # as if the bound had been too low
    trial.write_text(json.dumps(record))

    failures = check_preconditions(env.config, BASELINE, **env.options)

    assert "smoke_trace" in checks(failures) or "calibration" in checks(failures)


def test_projection_beyond_the_ceiling_blocks_the_start(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    env.ledger.adjust(Decimal("14.999"), "earlier spend")

    failures = check_preconditions(env.config, BASELINE, **env.options)

    assert "budget_projection" in checks(failures)
    assert "360 attempts" in next(f.detail for f in failures if f.check == "budget_projection")


def test_variant_without_a_prompt_cannot_run(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)

    assert "variant_prompt" in checks(check_preconditions(env.config, REVISED, **env.options))


def test_failures_are_reported_together_and_nothing_starts(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner, accept_cost=False, api_key=None)
    (env.evidence / "probes.json").unlink()

    with pytest.raises(PreconditionsFailed) as refused:
        run_variant(env.config, BASELINE, never, **env.options)

    assert {"cost_acceptance", "api_key", "probes"} <= {f.check for f in refused.value.failures}
    assert not env.bundles.exists() and env.ledger.state().events == 0


# --- schedule runner ---------------------------------------------------------------

def test_baseline_run_writes_one_complete_bundle_matching_the_schedule(tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)
    built = []

    def client_for(task, trial_id):
        built.append(trial_id)
        return solving(reference)(task, trial_id)

    run = run_variant(env.config, BASELINE, client_for, grader=grader, runner=inprocess_runner,
                      run_id="base-1", **env.options)

    schedule_ids = [i["trial_id"] for i in env.config.schedule]
    assert built == schedule_ids and len(built) == 30                  # one fresh client per trial
    assert run.complete and run.schedule.ok and run.schedule.missing == ()
    assert verify_bundle(run.bundle).complete
    manifest = load_manifest(run.bundle)
    assert [p["trial_id"] for p in manifest["planned"]] == schedule_ids  # the order is recorded
    experiment = manifest["identity"]["experiment"]
    assert (experiment["variant"], experiment["trial_order"]) == (BASELINE, "task_major")
    assert experiment["schedule_sha256"] == env.config.schedule_sha256
    assert manifest["identity"]["prompt"]["version"] == "baseline_agent_v1"
    record = load_trial(run.bundle, "strings_01-t1")
    assert len(record["grades"]["checks"]) == 4 and record["grades"]["success"]
    assert [len(load_trial(run.bundle, i)["requests"][0]["messages"]) for i in schedule_ids] == [2] * 30
    marker = json.loads((env.bundles / "base-1.experiment.json").read_text())
    assert marker["status"] == "complete" and marker["variant"] == BASELINE


def test_each_trial_goes_through_the_ledger_with_a_reservation_before_the_send(
        tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)
    transport = FakeTransport(*[reply("def x():\n    pass\n") for _ in range(30)])

    def client_for(task, trial_id):
        return OpenRouterClient(ModelConfig(), PRICES, env.ledger, KEY, transport,
                                tool_definitions=(TOOL_SCHEMA,), sleep=lambda s: None,
                                context={"trial_id": trial_id})

    run = run_variant(env.config, BASELINE, client_for, grader=grader, runner=inprocess_runner,
                      **env.options)

    events = [e["event"] for e in ledger_events(env.ledger)]
    assert events.count("reservation") == events.count("settlement") == len(transport.calls) == 30
    assert run.verification.complete and run.complete
    assert Decimal(run.ledger_total_after_chf) > Decimal(run.ledger_total_before_chf)
    assert KEY not in json.dumps([load_trial(run.bundle, i["trial_id"]) for i in env.config.schedule])


def test_ceiling_reached_mid_run_keeps_the_partial_bundle_and_labels_it_incomplete(
        tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)
    transport = FakeTransport(*[reply("def x():\n    pass\n") for _ in range(30)],
                              on_post=lambda: None)
    sent = []

    def spend_after_third():
        sent.append(1)
        if len(sent) == 3:
            env.ledger.adjust(Decimal("14.9999"), "simulated outside spend")

    transport.on_post = spend_after_third

    def client_for(task, trial_id):
        return OpenRouterClient(ModelConfig(), PRICES, env.ledger, KEY, transport,
                                tool_definitions=(TOOL_SCHEMA,), sleep=lambda s: None)

    run = run_variant(env.config, BASELINE, client_for, grader=grader, runner=inprocess_runner,
                      **env.options)

    assert not run.complete and len(transport.calls) == 3
    # The refused trial is recorded as an infrastructure stop; the rest were never run. Either
    # way the plan, and so the denominator, stays at 30.
    assert any("infrastructure_stop" in p and "strings_02-t1" in p for p in run.schedule.problems)
    assert len(run.schedule.missing) == 26 and len(load_manifest(run.bundle)["planned"]) == 30
    marker = json.loads((env.bundles / f"{run.run_id}.experiment.json").read_text())
    assert marker["status"] == "incomplete"


def test_interrupt_leaves_a_marker_and_a_second_start_is_a_recorded_decision(
        tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)

    def broken(task, trial_id):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_variant(env.config, BASELINE, broken, grader=grader, runner=inprocess_runner,
                    run_id="interrupted", **env.options)
    marker = json.loads((env.bundles / "interrupted.experiment.json").read_text())
    assert marker["status"] == "interrupted"

    failures = check_preconditions(env.config, BASELINE, **env.options)
    assert "prior_run" in checks(failures)
    assert "prior_run" not in checks(check_preconditions(env.config, BASELINE, allow_rerun=True,
                                                         **env.options))
    with pytest.raises(PreconditionsFailed):
        run_variant(env.config, BASELINE, never, **env.options)


def test_a_failing_tracking_hook_never_affects_the_bundle(tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)

    def hook(bundle, variant):
        raise ConnectionError("tracking server down")

    run = run_variant(env.config, BASELINE, solving(reference), grader=grader, runner=inprocess_runner,
                      record_run=hook, **env.options)

    assert run.complete and "tracking failed (ConnectionError)" in run.tracking
    seen = []
    env2 = make_env(tmp_path / "second", inprocess_runner)
    run2 = run_variant(env2.config, BASELINE, solving(reference), grader=grader, runner=inprocess_runner,
                       record_run=lambda bundle, variant: seen.append((bundle, variant)) or "mlflow:abc",
                       **env2.options)
    assert seen == [(run2.bundle, BASELINE)] and run2.tracking == "mlflow:abc"


def test_revised_variant_runs_the_identical_schedule_with_its_own_prompt(
        tmp_path, monkeypatch, inprocess_runner, grader):
    revised = with_revised_prompt(monkeypatch, tmp_path)
    env = make_env(tmp_path, inprocess_runner, revised=revised)

    base = run_variant(env.config, BASELINE, solving(reference), grader=grader, runner=inprocess_runner,
                       **env.options)
    rev = run_variant(env.config, REVISED, solving(reference), grader=grader, runner=inprocess_runner,
                      **env.options)

    assert base.complete and rev.complete
    assert [p["trial_id"] for p in load_manifest(base.bundle)["planned"]] == \
           [p["trial_id"] for p in load_manifest(rev.bundle)["planned"]]
    assert load_manifest(rev.bundle)["identity"]["prompt"]["version"] == revised
    assert verify_schedule(rev.bundle, env.config, BASELINE).ok is False   # not a baseline run


def test_verify_schedule_reports_missing_wrong_variant_and_wrong_schedule(tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)
    run = run_variant(env.config, BASELINE, solving(reference), grader=grader, runner=inprocess_runner,
                      **env.options)
    assert verify_schedule(run.bundle, env.config, BASELINE).ok

    (run.bundle / "trials" / "lists_01-t2.json").unlink()
    result = verify_schedule(run.bundle, env.config, BASELINE)
    assert not result.ok and result.missing == ("lists_01-t2",)

    shorter = json.loads(json.dumps(env.config.data))
    shorter["schedule"] = shorter["schedule"][:-3]
    shorter["trials_per_task"] = 3
    other = parse_config({**shorter, "benchmark": env.config.data["benchmark"]})
    assert any("differ" in p for p in verify_schedule(run.bundle, other, BASELINE).problems)


def test_unreadable_run_marker_blocks_every_variant_until_allow_rerun(tmp_path, inprocess_runner):
    env = make_env(tmp_path, inprocess_runner)
    env.bundles.mkdir()
    (env.bundles / "broken.experiment.json").write_text("{not json")

    for variant in (BASELINE, REVISED):
        assert "prior_run" in checks(check_preconditions(env.config, variant, **env.options))
    assert "prior_run" not in checks(check_preconditions(env.config, BASELINE, allow_rerun=True,
                                                         **env.options))


def test_checkpoint_state_is_recorded_before_and_after_a_run(tmp_path, inprocess_runner, grader):
    env = make_env(tmp_path, inprocess_runner)
    run = run_variant(env.config, BASELINE, solving(reference), grader=grader, runner=inprocess_runner,
                      **env.options)
    marker = json.loads((env.bundles / f"{run.run_id}.experiment.json").read_text())
    assert (run.checkpoint_reached_before, run.checkpoint_reached) == (False, False)
    assert marker["checkpoint_reached"] is False and marker["checkpoint_reached_before"] is False

    env2 = make_env(tmp_path / "b", inprocess_runner)
    env2.ledger.adjust(Decimal("10"), "earlier spend")             # crosses the CHF 10 checkpoint
    run2 = run_variant(env2.config, BASELINE, solving(reference), grader=grader,
                       runner=inprocess_runner, **env2.options)
    assert (run2.checkpoint_reached_before, run2.checkpoint_reached) == (True, True)


def test_freeze_checks_drift_against_the_benchmark_it_is_given(tmp_path, inprocess_runner):
    config = parse_config(build_config(BENCHMARK))
    smoke = make_smoke(tmp_path, inprocess_runner)
    copy = tmp_path / "other" / "benchmark_v1.json"
    copy.parent.mkdir()
    shutil.copy(BENCHMARK, copy)

    with pytest.raises(ExperimentError, match="out of date"):
        write_settings_freeze(config, smoke, tmp_path / "evidence", benchmark_path=copy)
    assert write_settings_freeze(config, smoke, tmp_path / "evidence", benchmark_path=BENCHMARK)
