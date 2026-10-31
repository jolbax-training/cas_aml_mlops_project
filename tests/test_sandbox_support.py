"""Offline checks of the sandbox test support: scaling, locking, stray detection (no Podman)."""

import multiprocessing
import os
import subprocess

import pytest

import sandbox_support as support
from codegen_eval.limits import DEFAULT_LIMITS


def test_generous_limits_scale_only_the_deadline_and_never_shrink_it(monkeypatch):
    monkeypatch.setattr(support, "_baseline", 0.4)
    assert support.generous_limits() == DEFAULT_LIMITS.with_deadline(10.0)
    monkeypatch.setattr(support, "_baseline", 3.0)
    scaled = support.generous_limits()
    assert scaled.deadline_seconds == 30.0
    assert scaled.with_deadline(DEFAULT_LIMITS.deadline_seconds) == DEFAULT_LIMITS


def test_explicit_timeout_keeps_exact_semantics(monkeypatch):
    seen = {}
    monkeypatch.setattr(support, "_baseline", 5.0)
    monkeypatch.setattr(support.sandbox, "run_case", lambda *a, **k: seen.update(k))
    support.run_case("s", None, None, timeout_seconds=0.05)
    assert seen["timeout_seconds"] == 0.05 and seen["limits"] == DEFAULT_LIMITS
    support.run_case("s", None, None)
    assert seen["limits"].deadline_seconds == 50.0


def _hold(path, ready, release):
    os.environ["XDG_CACHE_HOME"] = path
    os.environ.pop("CODEGEN_EVAL_SANDBOX_LOCK", None)
    support.acquire_session_lock()
    ready.set()
    release.wait(30)


def test_session_lock_excludes_a_second_holder(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("CODEGEN_EVAL_SANDBOX_LOCK", raising=False)
    monkeypatch.setattr(support, "_lock_handle", None)
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold, args=(str(tmp_path), ready, release))
    holder.start()
    try:
        assert ready.wait(30)
        monkeypatch.setattr(support, "LOCK_WAIT_SECONDS", 0)
        with pytest.raises(RuntimeError, match="held"):
            support.acquire_session_lock()
        release.set()
        holder.join(30)
        monkeypatch.setattr(support, "LOCK_WAIT_SECONDS", 30)
        support.acquire_session_lock()
        support.release_session_lock()
    finally:
        release.set()
        holder.join(5)


def test_stray_sweep_removes_only_dead_pid_candidate_containers(monkeypatch):
    dead = subprocess.Popen(["true"])
    dead.wait()
    names = [f"codegen-eval-{dead.pid}-0123456789ab", f"codegen-eval-{os.getpid()}-0123456789ab",
             "codegen-eval-mlflow", "codegen-eval-1-0123456789ab", "unrelated"]
    calls = []

    def fake(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="\n".join(names) if cmd[1] == "ps" else "")

    monkeypatch.setattr(support.subprocess, "run", fake)
    assert support.sweep_strays() == [names[0]]  # pid 1 is alive; mlflow and unrelated never match


def test_health_timeout_must_be_a_positive_integer():
    result = subprocess.run(["scripts/mlflow_service.sh", "status"], capture_output=True, text=True,
                            env={**os.environ, "MLFLOW_HEALTH_TIMEOUT": "abc"})
    assert result.returncode == 2 and "MLFLOW_HEALTH_TIMEOUT" in result.stderr
