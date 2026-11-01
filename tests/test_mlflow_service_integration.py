"""The Podman MLflow service: persistence across restarts, outage then upload, and candidate
isolation. Needs the local Podman VM and the pinned MLflow image; no model API is called."""

import importlib.util
import json
import os
import socket
import subprocess
import uuid
from pathlib import Path

import pytest

from codegen_eval import bundle, mlflow_tracking as mt, sandbox
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.replay import make_grader
from codegen_eval.run_recording import run_recorded
from codegen_eval.tasks import load_benchmark

pytestmark = [pytest.mark.sandbox, pytest.mark.mlflow_service, pytest.mark.skipif(
    os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM"
)]
HAVE_MLFLOW = importlib.util.find_spec("mlflow") is not None
if os.environ.get("CODEGEN_EVAL_REQUIRE_TRACKING") == "1":  # CI: a missing client is a failure
    import mlflow  # noqa: F401
# Per-test mark: the isolation probe below needs only the container, not the MLflow client.
needs_client = pytest.mark.skipif(not HAVE_MLFLOW, reason="needs `uv sync --group tracking` (MLflow client)")
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mlflow_service.sh"
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
SCENARIOS = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")
TASK = load_benchmark(BENCHMARK)[0]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Service:
    def __init__(self, tmp_path):
        self.port = free_port()
        self.name = "codegen-eval-mlflow-test-" + uuid.uuid4().hex[:8]
        self.env = {**os.environ, "MLFLOW_PORT": str(self.port), "MLFLOW_CONTAINER_NAME": self.name,
                    "MLFLOW_DATA_DIR": str(tmp_path / "mlflow_data"),
                    # a fresh container took ~17 s on a quiet VM; leave room for a loaded one
                    "MLFLOW_HEALTH_TIMEOUT": os.environ.get("MLFLOW_HEALTH_TIMEOUT", "240")}
        self.uri = f"http://127.0.0.1:{self.port}"

    def run(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(SCRIPT), command], env=self.env, capture_output=True,
                              text=True, timeout=300, check=False)

    def ok(self, command: str) -> subprocess.CompletedProcess:
        """Run a command that must succeed; on failure show its output and the container log."""
        result = self.run(command)
        if result.returncode != 0:
            logs = self.run("logs")
            raise AssertionError(f"{command} failed ({result.returncode}): {result.stdout}{result.stderr}\n"
                                 f"--- container log ---\n{logs.stdout}{logs.stderr}")
        return result


@pytest.fixture
def service(tmp_path):
    service = Service(tmp_path)
    yield service
    service.run("down")


def make_bundle(tmp_path, inprocess_runner, run_id):
    local = lambda source, task, case: inprocess_runner(source, task.function_name, case.args)
    path, _ = run_recorded(
        [TASK], lambda task, trial_id: FixtureClient.from_data(SCENARIOS["tool_use_and_revision"]),
        BENCHMARK, bundle_root=tmp_path / "bundles", run_id=run_id, trials_per_task=2,
        runner=inprocess_runner, grader=make_grader(local), model_settings={"client": "fixture"})
    return path


def snapshot(uri, run_id):
    """What a fresh client sees for a run: metrics, one artifact's text, trace count."""
    client = mt.make_client(uri)
    run = client.get_run(run_id)
    manifest = Path(client.download_artifacts(run_id, "bundle/manifest.json")).read_text()
    traces = client.search_traces(locations=[run.info.experiment_id], run_id=run_id)
    return dict(run.data.metrics), json.loads(manifest)["run_id"], len(traces)


@needs_client
def test_service_is_localhost_only_and_data_survives_restart_and_removal(
        tmp_path, inprocess_runner, service):
    path = make_bundle(tmp_path, inprocess_runner, "svc-run")
    service.ok("start")
    published = subprocess.run(["podman", "port", service.name], capture_output=True, text=True)
    assert published.stdout.strip() and all("127.0.0.1" in line for line in published.stdout.splitlines())

    result = mt.record_bundle(path, service.uri)
    before = snapshot(service.uri, result.run_id)
    assert before[1:] == ("svc-run", 2)

    service.ok("restart")  # stop then start the same container
    assert snapshot(service.uri, result.run_id) == before
    service.ok("down")     # remove the container itself
    assert service.run("status").returncode != 0
    service.ok("start")    # a new container, same host data
    assert snapshot(service.uri, result.run_id) == before

    again = mt.record_bundle(path, service.uri)    # idempotent across the restarts
    assert not again.created and again.run_id == result.run_id


@needs_client
def test_outage_then_later_upload_uses_the_same_bundle_and_no_model(
        tmp_path, inprocess_runner, service):
    service.ok("start")
    service.ok("stop")
    path = make_bundle(tmp_path, inprocess_runner, "late-run")  # the run completes, tracking stopped
    digest = bundle.verify_bundle(path).bundle_digest

    with pytest.raises(mt.TrackingUnavailable):
        mt.record_bundle(path, service.uri)
    assert mt.read_sidecar(path)["status"] == "not_recorded"

    service.ok("start")
    result = mt.record_bundle(path, service.uri)
    assert result.created and mt.read_sidecar(path)["status"] == "recorded"
    assert bundle.verify_bundle(path).bundle_digest == digest and bundle.verify_bundle(path).complete


def test_candidate_container_cannot_reach_the_tracking_service(service):
    service.ok("start")
    probe = ("import socket,sys\n"
             "s=socket.socket(); s.settimeout(3)\n"
             f"for host in ('host.containers.internal','10.0.2.2','127.0.0.1'):\n"
             f"    try:\n        s.connect((host,{service.port})); print('REACHED',host); sys.exit(1)\n"
             "    except OSError as e:\n        pass\nprint('unreachable')\n")
    # Control: the probe does reach the service from a container that has a network.
    control = subprocess.run(["podman", "run", "--rm", "--pull=never", sandbox.IMAGE,
                              "python", "-c", probe], capture_output=True, text=True, timeout=180)
    assert control.returncode == 1 and "REACHED" in control.stdout, control.stdout + control.stderr
    # Same isolation flags as the sandbox's real candidate container.
    flags = [a for a in sandbox._container_command("x", sandbox.DEFAULT_LIMITS)[3:]
             if a.startswith("--") and not a.startswith("--name")]
    result = subprocess.run(["podman", "run", "--rm", "--pull=never", *flags, sandbox.IMAGE,
                             "python", "-c", probe], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0 and result.stdout.strip() == "unreachable", result.stdout + result.stderr
