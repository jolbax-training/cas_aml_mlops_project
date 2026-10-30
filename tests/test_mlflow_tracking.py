"""Recording retained bundles in MLflow, against a temporary SQLite store (no service, no
Podman, no model client). The Podman service tests are in test_mlflow_service_integration.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

mlflow = pytest.importorskip("mlflow")

from codegen_eval import bundle, mlflow_tracking as mt, sandbox
from codegen_eval.bundle import BundleError
from codegen_eval.limits import DEFAULT_LIMITS
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.replay import make_grader, replay_bundle
from codegen_eval.run_recording import run_recorded
from codegen_eval.tasks import load_benchmark

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
SCENARIOS = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")
TASK = load_benchmark(BENCHMARK)[0]


@pytest.fixture
def local_runner(inprocess_runner):
    return lambda source, task, case: inprocess_runner(source, task.function_name, case.args)


@pytest.fixture
def store(tmp_path):
    """A throwaway tracking store: SQLite file plus a local artifact directory."""
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    client = mt.make_client(uri)
    client.create_experiment(mt.DEFAULT_EXPERIMENT, artifact_location=str(tmp_path / "artifacts"))
    return uri, client


def make_bundle(tmp_path, inprocess_runner, local_runner, scenario="tool_use_and_revision", *,
                trials=2, grade=True, run_id="run-a"):
    path, _ = run_recorded(
        [TASK], lambda task, trial_id: FixtureClient.from_data(SCENARIOS[scenario]), BENCHMARK,
        bundle_root=tmp_path / "bundles", run_id=run_id, trials_per_task=trials,
        runner=inprocess_runner, grader=make_grader(local_runner) if grade else None,
        model_settings={"client": "fixture", "scenario": scenario})
    return path


def experiment_id(client):
    return client.get_experiment_by_name(mt.DEFAULT_EXPERIMENT).experiment_id


def bundle_runs(client):
    return client.search_runs([experiment_id(client)],
                              f"tags.`{mt.TAG}record_kind` = '{mt.KIND_BUNDLE}'")


def traces(client, run_id=None):
    return client.search_traces(locations=[experiment_id(client)], run_id=run_id, max_results=100)


def artifact_text(client, run_id):
    """Every artifact file of a run, concatenated."""
    out, stack = [], [""]
    while stack:
        for info in client.list_artifacts(run_id, stack.pop() or None):
            if info.is_dir:
                stack.append(info.path)
            else:
                out.append(Path(client.download_artifacts(run_id, info.path)).read_text())
    return "\n".join(out)


def test_complete_bundle_is_recorded_with_identity_params_metrics_artifacts_and_traces(
        tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    manifest = bundle.load_manifest(path)
    digest = bundle.verify_bundle(path).bundle_digest

    result = mt.record_bundle(path, uri)

    assert result.created
    run = client.get_run(result.run_id)
    tags, params, metrics = run.data.tags, run.data.params, run.data.metrics
    assert run.info.status == "FINISHED" and run.info.run_name == "run-a"
    assert tags[mt.TAG + "bundle_run_id"] == "run-a" and tags[mt.TAG + "bundle_digest"] == digest
    assert tags[mt.TAG + "benchmark_sha256"] == manifest["identity"]["benchmark"]["sha256"]
    assert tags[mt.TAG + "prompt_version"] == "baseline_agent_v1"
    assert tags[mt.TAG + "evaluator_revision"] == manifest["identity"]["evaluator_revision"]
    assert tags[mt.TAG + "run_complete"] == "true" and tags[mt.TAG + "headline_candidate"] == "true"
    assert params["agent_limits.max_model_calls"] == "4"
    assert params["model.scenario"] == "tool_use_and_revision"
    assert params["container_image"] == manifest["identity"]["container_image"]
    assert metrics["trials_planned"] == 2 and metrics["trials_recorded"] == 2
    # The fixture's final candidate ignores accents, so it fails the hidden accented cases:
    # two of four checks per trial pass and no trial succeeds.
    assert metrics["success_rate"] == 0.0 and metrics["trials_successful"] == 0
    assert metrics["checks_total"] == 8 and metrics["checks_passed"] == 4
    assert metrics["edge_checks_total"] == 4 and metrics["edge_checks_passed"] == 2
    assert metrics["model_calls"] == 6 and metrics["tool_attempts"] == 4
    assert metrics["trial/strings_01-t1/success"] == 0.0 and metrics["label.wrong_answer"] == 2
    text = artifact_text(client, result.run_id)
    assert "run-a" in text and "def count_vowels" in text
    assert len(traces(client, result.run_id)) == 2
    sidecar = mt.read_sidecar(path)
    assert sidecar["status"] == "recorded" and sidecar["mlflow_run_id"] == result.run_id


def test_incomplete_bundle_is_visible_as_incomplete_and_not_a_headline_run(
        tmp_path, inprocess_runner, local_runner, store):
    uri, client = store

    def client_for(task, trial_id):
        if trial_id.endswith("t2"):
            raise KeyboardInterrupt
        return FixtureClient.from_data(SCENARIOS["early_submission"])

    with pytest.raises(KeyboardInterrupt):
        run_recorded([TASK], client_for, BENCHMARK, bundle_root=tmp_path / "bundles",
                     run_id="run-i", trials_per_task=3, runner=inprocess_runner,
                     grader=make_grader(local_runner))

    result = mt.record_bundle(tmp_path / "bundles" / "run-i", uri)

    run = client.get_run(result.run_id)
    assert run.data.tags[mt.TAG + "run_complete"] == "false"
    assert run.data.tags[mt.TAG + "headline_candidate"] == "false"
    assert run.data.tags[mt.TAG + "bundle_status"] == "incomplete"
    assert run.data.tags[mt.TAG + "missing_trials"] == "strings_01-t2,strings_01-t3"
    # The full planned denominator is kept: one success out of three planned trials.
    assert run.data.metrics["trials_planned"] == 3 and run.data.metrics["trials_recorded"] == 1
    # The one fixture trial fails the hidden accented cases; the denominator stays at three.
    assert run.data.metrics["trials_successful"] == 0 and run.data.metrics["success_rate"] == 0.0
    assert run.data.metrics["checks_total"] == 4 and run.data.metrics["trials_graded"] == 1
    assert len(traces(client, result.run_id)) == 1


def test_pending_grades_are_not_a_headline_candidate(tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner, grade=False)

    run = client.get_run(mt.record_bundle(path, uri).run_id)

    assert run.data.tags[mt.TAG + "headline_candidate"] == "false"
    assert run.data.metrics["trials_grades_pending"] == 2 and run.data.metrics["success_rate"] == 0.0


def test_trial_trace_has_ordered_model_tool_and_submission_spans(
        tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    mt.record_bundle(path, uri)

    trace = next(t for t in traces(client) if t.info.tags[mt.TAG + "trial_id"] == "strings_01-t1")

    spans = sorted(trace.data.spans, key=lambda s: (s.parent_id is not None,
                                                    (s.attributes or {}).get("step", 0)))
    assert [(s.name, s.span_type) for s in spans] == [
        ("trial strings_01-t1", "AGENT"),
        ("model_call 1", "CHAT_MODEL"), ("run_checks attempt 1", "TOOL"),
        ("model_call 2", "CHAT_MODEL"), ("run_checks attempt 2", "TOOL"),
        ("model_call 3", "CHAT_MODEL"), ("submission", "CHAIN")]
    by_name = {s.name: s for s in spans}
    assert "def count_vowels" in json.dumps(by_name["run_checks attempt 1"].inputs)
    assert by_name["run_checks attempt 1"].outputs  # the bounded feedback the model received
    assert by_name["model_call 3"].outputs["content"].startswith("def count_vowels")
    assert by_name["submission"].outputs["submitted"] is True
    assert by_name["model_call 1"].attributes["tools_enabled"] is True
    assert trace.info.tags[mt.TAG + "bundle_run_id"] == "run-a"


def test_hidden_expectations_and_grades_stay_out_of_the_agent_trace(
        tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    run_id = mt.record_bundle(path, uri).run_id

    trace_text = json.dumps([[s.to_dict() for s in t.data.spans] for t in traces(client)])

    # Cases the agent never wrote for itself (its own checks use "hello" and "").
    for case in TASK.cases:
        assert case.id not in trace_text
    for hidden in ("café", "ÄÉæ"):
        assert hidden not in trace_text and json.dumps(hidden) not in trace_text
    assert '"labels"' not in trace_text and "grades" not in trace_text
    # Grading evidence is attached to the run separately, per trial.
    grading = json.loads(Path(client.download_artifacts(
        run_id, "bundle/grading/strings_01-t1.json")).read_text())
    assert grading["grades"]["status"] == "graded" and len(grading["grades"]["checks"]) == 4


def test_re_recording_the_same_bundle_is_detected_and_changes_nothing(
        tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    first = mt.record_bundle(path, uri)
    before = (client.get_run(first.run_id).data, len(traces(client)))

    second = mt.record_bundle(path, uri)

    assert not second.created and second.run_id == first.run_id
    assert len(bundle_runs(client)) == 1 and len(traces(client)) == before[1] == 2
    assert client.get_run(first.run_id).data.metrics == before[0].metrics


def test_interrupted_upload_is_rebuilt_without_duplicates(
        tmp_path, inprocess_runner, local_runner, store, monkeypatch):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    real, calls = mt.write_trial_trace, []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("connection dropped")
        return real(*args, **kwargs)

    monkeypatch.setattr(mt, "write_trial_trace", flaky)
    with pytest.raises(mt.TrackingUnavailable):
        mt.record_bundle(path, uri)
    assert mt.read_sidecar(path)["status"] == "not_recorded"
    partial = bundle_runs(client)
    assert len(partial) == 1 and partial[0].info.status == "FAILED"
    assert mt.UPLOAD_COMPLETE not in partial[0].data.tags

    monkeypatch.setattr(mt, "write_trial_trace", real)
    result = mt.record_bundle(path, uri)

    assert result.created
    runs = bundle_runs(client)  # the failed partial run is deleted, not left beside the good one
    assert [r.info.run_id for r in runs] == [result.run_id]
    assert len(traces(client)) == 2


def test_grading_replay_is_a_distinct_linked_record_and_never_an_agent_trial(
        tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    replay_bundle(path, BENCHMARK, runner=lambda s, t, c: local_runner(s, t, c))
    first = mt.record_bundle(path, uri)
    original_traces = {t.info.trace_id for t in traces(client)}
    original_metrics = dict(client.get_run(first.run_id).data.metrics)

    again = mt.record_bundle(path, uri)  # replays are idempotent too

    assert len(first.replays) == 1 and again.replays == ()
    replay = client.search_runs([experiment_id(client)],
                                f"tags.`{mt.TAG}record_kind` = '{mt.KIND_REPLAY}'")
    assert len(replay) == 1
    tags = replay[0].data.tags
    assert tags["mlflow.parentRunId"] == first.run_id
    assert tags[mt.TAG + "agent_trial"] == "false" and tags[mt.TAG + "headline_candidate"] == "false"
    assert tags[mt.TAG + "bundle_digest"] == bundle.verify_bundle(path).bundle_digest
    assert tags[mt.TAG + "linked_manifest_matches_bundle"] == "true"
    assert replay[0].data.metrics["replay_mismatched"] == 0
    assert "replay-" in artifact_text(client, replay[0].info.run_id)
    # The original is untouched, and the replay added no trace.
    assert {t.info.trace_id for t in traces(client)} == original_traces
    assert not traces(client, replay[0].info.run_id)
    assert client.get_run(first.run_id).data.metrics == original_metrics
    assert len(bundle_runs(client)) == 1


def test_no_secret_appears_in_recorded_content(
        tmp_path, inprocess_runner, local_runner, store, monkeypatch):
    uri, client = store
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-0123456789abcdef")
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    secret = "sk-or-test-0123456789abcdef"

    run_id = mt.record_bundle(path, uri).run_id

    run = client.get_run(run_id)
    everything = json.dumps([run.data.params, run.data.tags, run.data.metrics]) \
        + artifact_text(client, run_id) \
        + json.dumps([[s.to_dict() for s in t.data.spans] for t in traces(client)]) \
        + json.dumps([t.info.tags for t in traces(client)])
    assert secret not in everything


def test_upload_redacts_a_secret_that_is_in_an_older_bundle(
        tmp_path, inprocess_runner, local_runner, store, monkeypatch):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    # A credential that was configured after the bundle was written and appears in it.
    monkeypatch.setenv("LATE_API_TOKEN", "count_vowels")

    result = mt.record_bundle(path, uri)

    run = client.get_run(result.run_id)
    everything = json.dumps(run.data.params) + artifact_text(client, result.run_id) \
        + json.dumps([[s.to_dict() for s in t.data.spans] for t in traces(client)])
    assert "count_vowels" not in everything and bundle.REDACTED in everything
    assert result.redactions > 0 and run.data.tags[mt.TAG + "redactions_at_upload"] != "0"


def test_tampered_bundle_is_refused(tmp_path, inprocess_runner, local_runner, store):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)
    trial = path / "trials" / "strings_01-t1.json"
    trial.write_text(trial.read_text().replace("submitted", "tampered"))

    with pytest.raises(BundleError, match="cannot be recorded"):
        mt.record_bundle(path, uri)
    assert not bundle_runs(client)


def test_outage_then_later_upload_of_the_same_bundle(
        tmp_path, inprocess_runner, local_runner, store, capsys):
    uri, client = store
    path = make_bundle(tmp_path, inprocess_runner, local_runner)  # the run completed, tracking down
    digest = bundle.verify_bundle(path).bundle_digest
    down = "http://127.0.0.1:9"  # nothing listens here

    code = mt.main(["record", str(path), "--tracking-uri", down])

    assert code == 3 and "not yet recorded" in capsys.readouterr().err
    assert mt.read_sidecar(path)["status"] == "not_recorded"
    mt.main(["status", "--bundles", str(tmp_path / "bundles")])
    assert "run-a: not_recorded" in capsys.readouterr().out
    assert bundle.verify_bundle(path).bundle_digest == digest  # evidence untouched

    assert mt.main(["record", str(path), "--tracking-uri", uri]) == 0

    assert mt.read_sidecar(path)["status"] == "recorded"
    assert bundle.verify_bundle(path).complete and bundle.verify_bundle(path).bundle_digest == digest
    assert len(bundle_runs(client)) == 1


def test_recording_never_imports_the_model_client_sandbox_or_evaluator():
    code = (f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); "
            "import codegen_eval.mlflow_tracking as m; "
            "bad = [n for n in ('codegen_eval.model_client', 'codegen_eval.sandbox', "
            "'codegen_eval.evaluate', 'codegen_eval.run_recording') if n in sys.modules]; "
            "print(bad); sys.exit(1 if bad else 0)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_candidate_containers_have_no_network_or_tracking_configuration():
    command = sandbox._container_command("probe", DEFAULT_LIMITS)

    assert "--network=none" in command
    assert [a for a in command if a.startswith(("--env", "-e"))] == ["--env=HOME=/tmp"]
    assert not any(flag in command for flag in ("-p", "--publish", "--network=host", "-v", "--volume"))
    assert not any("mlflow" in a.lower() for a in command)
    assert "mlflow" not in Path(sandbox.__file__).read_text().lower()


def test_agent_and_evaluator_modules_do_not_depend_on_the_tracking_service():
    """Execution must complete with MLflow stopped (or not installed): only the recorder
    module may import it."""
    sources = {p.name: p.read_text() for p in (ROOT / "src" / "codegen_eval").glob("*.py")}
    offenders = [n for n, text in sources.items()
                 if n != "mlflow_tracking.py" and ("mlflow" in text.lower())]
    assert offenders == []
