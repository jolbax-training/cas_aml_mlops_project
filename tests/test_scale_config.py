"""The second experiment's configuration and the guards that keep the first one's files safe."""

import hashlib
import json
import shutil

import pytest

from codegen_eval.experiment import (
    BASELINE, DEFAULT_CONFIG, ExperimentError, build_config, config_drift, load_config,
    write_config, write_probes_evidence, write_settings_freeze,
)
from codegen_eval.experiment_cli import main
from experiment_support import BENCHMARK, JUNIT, ROOT, TASKS, make_env, make_smoke, with_revised_prompt

V1 = ROOT / "experiments" / "prompt_comparison_v1.json"
V2 = ROOT / "experiments" / "prompt_comparison_v2.json"
V1_SHA256 = "1c82c9f9820949ad5103fbf8220a1c9f231d0fa1a27b9af3b7c89de3f389988a"
COUNTS = {"tests": 56, "failures": 0, "errors": 0, "skipped": 0}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- the committed configurations ------------------------------------------------------

def test_the_first_configuration_is_byte_identical_to_the_recorded_one():
    assert DEFAULT_CONFIG == V1 and sha256(V1) == V1_SHA256


def test_defaults_still_build_the_first_experiment():
    data = json.loads(V1.read_text())
    # Built for v1's recorded platform: the default platform is this host's, and CI is amd64.
    built = build_config(BENCHMARK, revised_prompt="baseline_agent_v2",
                         container_platform=data["settings"]["container_platform"])
    assert built == data
    default = build_config(BENCHMARK)
    assert default["experiment_id"] == data["experiment_id"] == "prompt_comparison_v1"
    assert default["trials_per_task"] == 3 and default["schedule"] == data["schedule"]
    assert main(["build-config", "--check"], env={}) == 0


def test_second_configuration_differs_from_the_first_in_identity_trials_and_schedule_only():
    first, second = json.loads(V1.read_text()), json.loads(V2.read_text())

    assert {key for key in first if first[key] != second[key]} == {"experiment_id", "trials_per_task", "schedule"}
    assert second["experiment_id"] == "prompt_comparison_v2" and second["trials_per_task"] == 10
    assert second["trial_order"] == "task_major" and len(second["schedule"]) == 100 == len(TASKS) * 10
    assert second["schedule"][:2] == [{"task_id": "strings_01", "trial_id": "strings_01-t1"},
                                      {"task_id": "strings_01", "trial_id": "strings_01-t2"}]
    assert second["schedule"][9]["trial_id"] == "strings_01-t10"
    assert second["variants"][0]["prompt_version"] == "baseline_agent_v1"
    assert second["variants"][1]["prompt_version"] == "baseline_agent_v2"
    assert second["settings"]["container_platform"] == "arm64"
    assert config_drift(load_config(V2)) == []


def test_second_configuration_passes_the_drift_check_through_the_cli(capsys):
    assert main(["build-config", "--check", "--config", str(V2)], env={}) == 0
    assert "matches the repository" in capsys.readouterr().out


def test_the_cli_options_build_a_configuration_for_another_experiment(tmp_path):
    target = tmp_path / "other.json"
    assert main(["build-config", "--experiment-id", "other_v1", "--trials-per-task", "2",
                 "--revised-prompt", "baseline_agent_v2", "--container-platform", "arm64",
                 "--config", str(target)], env={}) == 0

    data = json.loads(target.read_text())
    assert data["experiment_id"] == "other_v1" and len(data["schedule"]) == len(TASKS) * 2
    assert config_drift(load_config(target)) == []


# --- overwrite guards ------------------------------------------------------------------

@pytest.mark.parametrize("flags", [
    ["--trials-per-task", "10"],
    ["--experiment-id", "prompt_comparison_v2"],
    ["--experiment-id", "prompt_comparison_v2", "--trials-per-task", "10"],
    ["--revised-prompt", "baseline_agent_v1"],
])
def test_build_config_cannot_rewrite_a_configuration_that_would_change(tmp_path, capsys, flags):
    copy = tmp_path / "prompt_comparison_v1.json"
    shutil.copyfile(V1, copy)

    assert main(["build-config", "--config", str(copy), *flags], env={}) == 1

    assert "refusing to replace" in capsys.readouterr().err
    assert copy.read_bytes() == V1.read_bytes()


def test_build_config_with_nothing_to_change_is_a_no_op(tmp_path):
    copy = tmp_path / "v1.json"
    shutil.copyfile(V1, copy)
    assert main(["build-config", "--config", str(copy)], env={}) == 0
    assert copy.read_bytes() == V1.read_bytes()
    assert sha256(V1) == V1_SHA256                                       # and the real file was not aimed at


def test_write_config_refuses_any_existing_file_whose_content_differs(tmp_path):
    target = tmp_path / "c.json"
    target.write_text("{}")
    with pytest.raises(ExperimentError, match="refusing to replace"):
        write_config(build_config(BENCHMARK), target)
    assert target.read_text() == "{}"
    other = tmp_path / "dir" / "new.json"
    assert write_config(build_config(BENCHMARK), other) == other


def test_probe_evidence_is_never_replaced(tmp_path):
    write_probes_evidence(tmp_path, COUNTS, command="x", junit_xml=JUNIT)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    with pytest.raises(ExperimentError, match="refusing to replace"):
        write_probes_evidence(tmp_path, {**COUNTS, "tests": 1}, command="y", junit_xml=JUNIT)

    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_probe_evidence_refuses_when_only_the_report_exists(tmp_path):
    (tmp_path / "probes.junit.xml").write_text("kept")
    with pytest.raises(ExperimentError, match="refusing to replace"):
        write_probes_evidence(tmp_path, COUNTS, command="x", junit_xml=JUNIT)
    assert not (tmp_path / "probes.json").exists() and (tmp_path / "probes.junit.xml").read_text() == "kept"


def test_a_settings_freeze_is_never_replaced(tmp_path, inprocess_runner, monkeypatch):
    env = make_env(tmp_path, inprocess_runner, revised=with_revised_prompt(monkeypatch, tmp_path))
    freeze = env.evidence / "settings_freeze.json"
    before = freeze.read_bytes()

    with pytest.raises(ExperimentError, match="refusing to replace"):
        write_settings_freeze(env.config, env.smoke, env.evidence)

    assert freeze.read_bytes() == before


def test_a_second_experiments_freeze_goes_to_its_own_directory(tmp_path, inprocess_runner, monkeypatch):
    env = make_env(tmp_path, inprocess_runner, revised=with_revised_prompt(monkeypatch, tmp_path))
    other = tmp_path / "evidence_v2"

    path = write_settings_freeze(env.config, env.smoke, other)

    assert path.parent == other and (env.evidence / "settings_freeze.json").is_file()


# --- the MLflow experiment name ---------------------------------------------------------

def test_run_records_into_the_named_experiment_and_by_default_into_the_standard_one(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr("codegen_eval.mlflow_tracking.bundle_recorder",
                        lambda uri=None, *, experiment=None: seen.append(experiment) or None)
    from codegen_eval.experiment_cli import main as cli_main

    for extra, expected in (([], None), (["--experiment", "codegen-eval-prompt-comparison-v2"],
                                         "codegen-eval-prompt-comparison-v2")):
        seen.clear()
        # No key and no acceptance: the run is refused after the recorder is built.
        cli_main(["run", "--variant", BASELINE, "--ledger", str(tmp_path / "ledger.jsonl"),
                  "--bundles", str(tmp_path / "bundles"), *extra], env={})
        assert seen == [expected]


# --- review fixes ----------------------------------------------------------------------

def test_build_config_says_unchanged_when_nothing_is_written(tmp_path, capsys):
    target = tmp_path / "c.json"
    args = ["build-config", "--experiment-id", "other_v1", "--trials-per-task", "1",
            "--revised-prompt", "baseline_agent_v2", "--container-platform", "arm64",
            "--config", str(target)]
    assert main(args, env={}) == 0 and capsys.readouterr().out.startswith("wrote ")
    assert main(args, env={}) == 0 and capsys.readouterr().out.startswith("unchanged ")


def test_record_probes_refuses_before_running_the_suite(tmp_path, capsys):
    (tmp_path / "probes.json").write_text("{}")

    def suite():
        raise AssertionError("the probe suite must not run when the record would be refused")

    assert main(["record-probes", "--evidence", str(tmp_path)], env={}, probe_suite=suite) == 1
    assert "refusing to replace" in capsys.readouterr().err
    assert (tmp_path / "probes.json").read_text() == "{}"
