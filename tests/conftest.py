import json
import os

import pytest

import sandbox_support
from codegen_eval.sandbox import ExecutionResult


def pytest_sessionstart(session):
    """With RUN_SANDBOX_TESTS=1: serialize with other sandbox sessions on this Podman VM,
    sweep containers of dead sessions, and measure container startup for non-timeout deadlines."""
    if not sandbox_support.enabled():
        return
    sandbox_support.acquire_session_lock()
    sandbox_support.sweep_strays()
    try:
        baseline = sandbox_support.startup_baseline()
    except RuntimeError as error:
        pytest.exit(f"sandbox environment unusable: {error}", returncode=1)
    if baseline > sandbox_support.BASELINE_CAP_SECONDS:
        load = os.getloadavg()[0]
        pytest.exit(f"container startup took {baseline:.1f}s (cap {sandbox_support.BASELINE_CAP_SECONDS}s, "
                    f"load average {load:.1f}); the Podman VM is overloaded, not scaling deadlines further",
                    returncode=1)


def pytest_report_header(config):
    if sandbox_support.enabled():
        return sandbox_support.session_header()


def pytest_sessionfinish(session, exitstatus):
    sandbox_support.release_session_lock()


@pytest.fixture
def inprocess_runner():
    """Trusted stand-in for execute_check that runs source in this process. Test-only:
    it mirrors the status vocabulary of the container path without Podman."""

    def runner(source, function_name, args, limits=None):
        namespace: dict = {}
        exec(compile(source, "<candidate>", "exec"), namespace)
        copied = json.loads(json.dumps(list(args)))
        try:
            value = namespace[function_name](*copied)
        except Exception as error:  # noqa: BLE001 - candidate code may raise anything
            return ExecutionResult("exception", detail=type(error).__name__)
        return ExecutionResult("returned", value=value, args_after=copied)

    return runner
