"""Test-only support for the Podman suites on a shared, possibly loaded VM.

The production deadline includes container creation and start, so a slow start under host
load surfaces as a candidate `timeout`. That semantics is deliberate and stays. Tests that
expect any *other* outcome therefore run with a deadline scaled to the startup time measured
at session start; tests that assert `timeout` keep their exact, explicit deadline. Nothing
here touches a network, filesystem, capability, mutation, or output-limit assertion.

Parallel sandbox sessions (several worktrees on one Podman VM) serialize on a file lock, and
containers left by dead sessions are swept at session start.
"""

import fcntl
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from codegen_eval import sandbox
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits

SCALE = 10                 # generous deadline = SCALE x measured startup, never below the default
BASELINE_CAP_SECONDS = float(os.environ.get("CODEGEN_EVAL_STARTUP_CAP", "5"))
LOCK_WAIT_SECONDS = 45 * 60
_STRAY = re.compile(r"^codegen-eval-(\d+)-[0-9a-f]{12}$")

_baseline: float | None = None
_lock_handle = None


def enabled() -> bool:
    return os.environ.get("RUN_SANDBOX_TESTS") == "1"


def lock_path() -> Path:
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "codegen-eval" / "sandbox.lock"


def acquire_session_lock() -> None:
    """Block until no other sandbox session holds the lock (CODEGEN_EVAL_SANDBOX_LOCK=0 skips)."""
    global _lock_handle
    if os.environ.get("CODEGEN_EVAL_SANDBOX_LOCK") == "0" or _lock_handle is not None:
        return
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+")
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    announced = False
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if not announced:
                print(f"sandbox: waiting for another sandbox session (lock {path})", file=sys.stderr)
                announced = True
            if time.monotonic() > deadline:
                handle.close()
                raise RuntimeError(f"another sandbox session held {path} for {LOCK_WAIT_SECONDS}s")
            time.sleep(2)
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    _lock_handle = handle  # released when the process exits or release_session_lock runs


def release_session_lock() -> None:
    global _lock_handle
    if _lock_handle is not None:
        fcntl.flock(_lock_handle, fcntl.LOCK_UN)
        _lock_handle.close()
        _lock_handle = None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def sweep_strays() -> list[str]:
    """Remove candidate containers whose owning test process is gone; a live PID is left alone."""
    listing = subprocess.run(["podman", "ps", "-a", "--format", "{{.Names}}"],
                             capture_output=True, text=True, check=False)
    removed = []
    for name in listing.stdout.split():
        match = _STRAY.match(name)
        if match and int(match.group(1)) != os.getpid() and not _pid_alive(int(match.group(1))):
            subprocess.run(["podman", "rm", "-f", "-t", "0", "--ignore", name],
                           capture_output=True, text=True, check=False)
            removed.append(name)
    return removed


def measure_startup() -> float:
    """Slowest of three trivial checks with the production limits, in seconds."""
    source = "def f(x):\n    return x\n"
    samples = []
    for _ in range(3):
        start = time.monotonic()
        result = sandbox.execute_check(source, "f", [1], DEFAULT_LIMITS)
        samples.append(time.monotonic() - start)
        if result.status != "returned":
            raise RuntimeError(f"startup measurement did not return a value: {result}")
    return max(samples)


def startup_baseline() -> float:
    global _baseline
    if _baseline is None:
        _baseline = measure_startup()
    return _baseline


def generous_limits(base: ExecutionLimits = DEFAULT_LIMITS) -> ExecutionLimits:
    """Production limits with only the deadline scaled to the measured startup."""
    return base.with_deadline(max(base.deadline_seconds, SCALE * startup_baseline()))


def run_case(source, task, case, *, timeout_seconds=None, limits=None):
    """sandbox.run_case: an explicit timeout keeps its exact semantics, anything else is generous."""
    if timeout_seconds is not None:
        return sandbox.run_case(source, task, case, timeout_seconds=timeout_seconds,
                                limits=limits or DEFAULT_LIMITS)
    return sandbox.run_case(source, task, case, limits=limits or generous_limits())


def execute_check(source, function_name, args, limits=None):
    return sandbox.execute_check(source, function_name, args, limits or generous_limits())


def session_header() -> str:
    return (f"sandbox startup baseline {startup_baseline():.2f}s; non-timeout deadline "
            f"{generous_limits().deadline_seconds:.1f}s (production {DEFAULT_LIMITS.deadline_seconds:.0f}s)")
