import inspect
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from codegen_eval import sandbox
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.sandbox import execute_check, run_case
from codegen_eval.tasks import load_tasks


PILOT = Path(__file__).resolve().parents[1] / "data" / "pilot_tasks.json"
TASKS = load_tasks(PILOT, {"strings": 1, "lists": 1, "dictionaries": 1})
VOWELS = "def count_vowels(text: str) -> int:\n    return 0\n"


def test_default_limits_are_the_agreed_values():
    assert DEFAULT_LIMITS.to_dict() == {
        "deadline_seconds": 10.0, "memory_mib": 128, "cpus": 1, "max_processes": 32,
        "tmp_mib": 16, "payload_bytes": 65_536, "print_bytes": 32_768, "protocol_bytes": 65_536,
    }


def test_limits_round_trip_and_hash_changes_with_any_limit():
    assert ExecutionLimits.from_dict(json.loads(json.dumps(DEFAULT_LIMITS.to_dict()))) == DEFAULT_LIMITS
    assert DEFAULT_LIMITS.config_hash() == ExecutionLimits().config_hash()
    assert DEFAULT_LIMITS.with_deadline(5).config_hash() != DEFAULT_LIMITS.config_hash()


@pytest.mark.parametrize("bad", [{"deadline_seconds": 0}, {"memory_mib": -1}, {"cpus": 1.5}, {"tmp_mib": True}])
def test_invalid_limits_are_rejected(bad):
    with pytest.raises(ValueError):
        ExecutionLimits(**bad)


def test_from_dict_requires_exactly_the_known_fields():
    with pytest.raises(ValueError):
        ExecutionLimits.from_dict({"deadline_seconds": 10})


def test_container_command_applies_every_limit_and_restriction():
    limits = ExecutionLimits(memory_mib=64, cpus=1, max_processes=8, tmp_mib=4)
    command = sandbox._container_command("probe", limits)

    for flag in ("--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                 "--user=65534:65534", "--pids-limit=8", "--memory=64m", "--memory-swap=64m", "--cpus=1",
                 "--tmpfs=/tmp:rw,nosuid,noexec,size=4m", "--pull=never"):
        assert flag in command
    # No mounts, secrets, host namespaces, devices, or Podman socket.
    assert not any(part.startswith(("-v", "--volume", "--mount", "--privileged", "--pid=", "--ipc=",
                                    "--userns=", "--device", "--secret", "--env-file"))
                   for part in command)
    assert [part for part in command if part.startswith("--env")] == ["--env=HOME=/tmp"]
    assert not any("podman.sock" in part for part in command)
    # The container is kept after exit so State.OOMKilled can be read, then removed explicitly.
    assert "--rm" not in command


def test_each_check_gets_a_fresh_named_container(monkeypatch):
    names = []

    def fake_popen(command, **kwargs):
        names.append(command[command.index("--name") + 1])
        raise OSError("no podman in this test")

    monkeypatch.setattr(sandbox.subprocess, "Popen", fake_popen)
    first = execute_check(VOWELS, "count_vowels", ["a"])
    second = execute_check(VOWELS, "count_vowels", ["a"])

    assert first.status == second.status == "infrastructure_error"
    assert len(set(names)) == 2


def test_oversized_payload_is_rejected_before_any_container_starts(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no container may start for an oversized payload")

    monkeypatch.setattr(sandbox.subprocess, "Popen", forbidden)
    result = execute_check(VOWELS + "# " + "x" * 70_000, "count_vowels", ["a"])

    assert result.status == "payload_too_large"
    small = DEFAULT_LIMITS.__class__(payload_bytes=100)
    assert execute_check(VOWELS, "count_vowels", ["x" * 200], small).status == "payload_too_large"


def test_entry_point_takes_no_expected_value_and_payload_contains_none(monkeypatch):
    assert list(inspect.signature(execute_check).parameters) == ["source", "function_name", "args", "limits"]
    task = TASKS[0]
    case = replace(task.cases[0], expected="EXPECTED-ANSWER-7a3f")
    sent = {}

    class FakeProcess:
        returncode = 0

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(sandbox.subprocess, "Popen", lambda command, **kw: FakeProcess())
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *a, **kw: None)

    def fake_exchange(process, payload, seconds, max_output):
        sent["payload"] = payload
        return b'{"status":"returned","value":1,"args_after":[["hello"]]}', b"", None

    monkeypatch.setattr(sandbox, "_exchange", fake_exchange)
    run_case(VOWELS, task, case)

    payload = json.loads(sent["payload"])
    assert set(payload) == {"source", "function_name", "args", "token", "limits"}
    assert payload["function_name"] == task.function_name and payload["args"] == list(case.args)
    assert "EXPECTED-ANSWER-7a3f" not in sent["payload"].decode()
    assert set(payload["limits"]) == {"print_bytes", "protocol_bytes"}


def test_run_case_deadline_override_replaces_only_the_deadline(monkeypatch):
    seen = {}
    monkeypatch.setattr(sandbox, "execute_check",
                        lambda source, name, args, limits: seen.setdefault("limits", limits))
    run_case(VOWELS, TASKS[0], TASKS[0].cases[0], timeout_seconds=1.5)

    assert seen["limits"] == DEFAULT_LIMITS.with_deadline(1.5)


def test_unavailable_podman_is_an_infrastructure_outcome(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("podman")

    monkeypatch.setattr(sandbox.subprocess, "Popen", missing)

    assert execute_check(VOWELS, "count_vowels", ["a"]).status == "infrastructure_error"
    assert "infrastructure_error" in sandbox.INFRASTRUCTURE_STATUSES


def test_malformed_supervisor_output_is_an_infrastructure_outcome(monkeypatch):
    class FakeProcess:
        returncode = 0

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(sandbox.subprocess, "Popen", lambda command, **kw: FakeProcess())
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *a, **kw: None)
    for output in (b"not json", b'{"status":"returned"}', b'{"status":"made_up"}', b"[]"):
        monkeypatch.setattr(sandbox, "_exchange", lambda *a, _o=output: (_o, b"", None))
        assert execute_check(VOWELS, "count_vowels", ["a"]).status == "protocol_error"


def _sleeper(seconds: float):
    return subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({seconds})"])


def test_reap_waits_for_a_client_that_is_about_to_exit():
    process = _sleeper(0.5)
    sandbox._reap(process, kill=False, wait_seconds=5)

    assert process.returncode == 0


def test_reap_kills_a_client_that_outlives_the_wait():
    process = _sleeper(30)
    sandbox._reap(process, kill=False, wait_seconds=0.2)

    assert process.returncode is not None and process.returncode < 0


def test_reap_kills_immediately_when_asked_and_always_collects_the_return_code():
    process = _sleeper(30)
    sandbox._reap(process, kill=True, wait_seconds=5)

    assert process.returncode is not None and process.returncode < 0


def test_container_removal_kills_immediately_and_verifies_it_is_gone(monkeypatch):
    """`rm -f` without `-t 0` waits ten seconds for a SIGTERM the supervisor ignores; the
    cleanup timeout then abandoned a container mid-stop (the intermittent leftover)."""
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1 if command[1] == "container" else 0, b"", b"")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    sandbox._remove_container("codegen-eval-x", retry=True)

    assert commands == [["podman", "rm", "-f", "-t", "0", "--ignore", "codegen-eval-x"],
                        ["podman", "container", "exists", "codegen-eval-x"]]


def test_cleanup_is_time_bounded_when_podman_is_unresponsive(monkeypatch):
    clock = {"now": 0.0}

    def fake_run(command, **kwargs):
        clock["now"] += kwargs["timeout"]
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    monkeypatch.setattr(sandbox.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(sandbox.time, "sleep", lambda seconds: clock.__setitem__("now", clock["now"] + seconds))
    sandbox._remove_container("codegen-eval-x", retry=True)

    assert sandbox.CLEANUP_SECONDS <= clock["now"] <= sandbox.CLEANUP_SECONDS + 15


def test_container_is_created_before_it_is_started(monkeypatch):
    seen = []

    class FakeProcess:
        returncode = 0

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def fake_popen(command, **kwargs):
        seen.append(command[:2])
        return FakeProcess()

    monkeypatch.setattr(sandbox.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *a, **kw: None)
    monkeypatch.setattr(sandbox, "_exchange", lambda *a: (b'{"status":"returned","value":1,'
                                                          b'"args_after":[["a"]]}', b"", None))
    execute_check(VOWELS, "count_vowels", ["a"])

    assert seen == [["podman", "create"], ["podman", "start"]]
