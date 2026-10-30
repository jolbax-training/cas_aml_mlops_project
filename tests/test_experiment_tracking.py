"""The experiment runner's MLflow hook, against a temporary SQLite store (no service, no
Podman, no model client): record after verification, or keep the outage marker for later."""

import os

import pytest

if os.environ.get("CODEGEN_EVAL_REQUIRE_TRACKING") == "1":  # CI: a missing client is a failure
    import mlflow  # noqa: F401
else:
    pytest.importorskip("mlflow", reason="needs `uv sync --group tracking` (MLflow client)")

from codegen_eval import mlflow_tracking as mt
from codegen_eval.bundle import sha256_file, verify_bundle
from codegen_eval.experiment import BASELINE, run_variant
from codegen_eval.mlflow_tracking import bundle_recorder as mlflow_recorder
from experiment_support import make_env, local_grader, reference, solving

DOWN = "http://127.0.0.1:9"   # nothing listens here; the preflight fails fast


@pytest.fixture
def store(tmp_path):
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    client = mt.make_client(uri)
    client.create_experiment(mt.DEFAULT_EXPERIMENT, artifact_location=str(tmp_path / "artifacts"))
    return uri, client


@pytest.fixture
def env(tmp_path, inprocess_runner):
    return make_env(tmp_path, inprocess_runner)


def run(env, inprocess_runner, hook, client_for=None):
    return run_variant(env.config, BASELINE, client_for or solving(reference),
                       grader=local_grader(inprocess_runner), runner=inprocess_runner,
                       record_run=hook, **env.options)


def test_a_verified_variant_run_is_recorded_once_with_its_experiment_identity(
        env, inprocess_runner, store):
    uri, client = store

    result = run(env, inprocess_runner, mlflow_recorder(uri))

    assert result.complete and result.tracking.startswith("recorded: MLflow run ")
    sidecar = mt.read_sidecar(result.bundle)
    assert sidecar["status"] == "recorded"
    run_ = client.get_run(sidecar["mlflow_run_id"])
    tags, params = run_.data.tags, run_.data.params
    assert tags[mt.TAG + "bundle_run_id"] == result.run_id
    assert tags[mt.TAG + "run_complete"] == "true" and tags[mt.TAG + "headline_candidate"] == "true"
    assert params["experiment.variant"] == BASELINE
    assert params["experiment.experiment_id"] == env.config.experiment_id
    assert run_.data.metrics["trials_planned"] == 30

    # Recording the same bundle again changes nothing.
    again = mlflow_recorder(uri)(result.bundle, BASELINE)
    assert again == result.tracking
    assert mt.read_sidecar(result.bundle)["mlflow_run_id"] == sidecar["mlflow_run_id"]


def test_an_outage_keeps_the_marker_and_the_bundle_and_later_upload_works(
        env, inprocess_runner, store, tmp_path):
    uri, client = store

    result = run(env, inprocess_runner, mlflow_recorder(DOWN))

    assert result.complete                                   # an outage never blocks the run
    assert result.tracking.startswith("not recorded:") and "mlflow_tracking record" in result.tracking
    marker = mt.read_sidecar(result.bundle)
    assert marker["status"] == "not_recorded" and marker["last_error"]
    digest = sha256_file(result.bundle / "manifest.json")
    assert verify_bundle(result.bundle).complete

    later = mt.record_bundle(result.bundle, uri)             # the documented later-upload path

    assert later.created and mt.read_sidecar(result.bundle)["status"] == "recorded"
    assert sha256_file(result.bundle / "manifest.json") == digest   # never regenerated or altered


def test_an_incomplete_run_is_recorded_as_incomplete_not_headline(env, inprocess_runner, store):
    from codegen_eval.model_client import FixtureClient, load_fixtures
    from experiment_support import ROOT
    uri, client = store
    scenario = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")[
        "transport_exhausted_on_call_2"]

    result = run(env, inprocess_runner, mlflow_recorder(uri),
                 lambda task, trial_id: FixtureClient.from_data(scenario))

    assert not result.complete and result.tracking.startswith("recorded:")
    tags = client.get_run(mt.read_sidecar(result.bundle)["mlflow_run_id"]).data.tags
    assert tags[mt.TAG + "run_complete"] == "false" and tags[mt.TAG + "headline_candidate"] == "false"
