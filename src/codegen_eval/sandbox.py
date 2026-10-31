"""Run one generated function call in a disposable, restricted container.

Expected answers and scoring never enter this module: `execute_check` takes only
source, function name, and one check's arguments, and returns raw outcomes."""

from __future__ import annotations

import json
import os
import platform
import secrets
import selectors
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import Any, Sequence

from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.tasks import Case, Task
from codegen_eval.worker import SUPERVISOR


# python:3.12.14-slim-trixie. Each digest is the per-platform image manifest, so the host
# architecture selects the matching pin (an arm64 digest cannot run on an amd64 runner).
_IMAGE_BY_ARCH = {
    "arm64": "docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5",
    "amd64": "docker.io/library/python@sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b",
}
_ARCH_ALIASES = {"aarch64": "arm64", "x86_64": "amd64"}


def normalize_platform(machine: str) -> str:
    """The architecture name used by the image pins (`arm64`, `amd64`)."""
    return _ARCH_ALIASES.get(machine.lower(), machine.lower())


def _select_image(machine: str) -> str:
    try:
        return _IMAGE_BY_ARCH[normalize_platform(machine)]
    except KeyError:
        raise RuntimeError(f"no pinned candidate image for architecture {machine!r}") from None


def image_for_platform(arch: str) -> str:
    """The image pinned for `arch`, so a recorded platform can be checked on any host."""
    return _select_image(arch)


def platform_of_image(image: str) -> str | None:
    """The architecture an image pin is for, or None for an image that is not a pin."""
    return next((arch for arch, pinned in _IMAGE_BY_ARCH.items() if pinned == image), None)


HOST_PLATFORM = normalize_platform(platform.machine())
IMAGE = _select_image(HOST_PLATFORM)

# Container names carry the process id, so concurrent runs sharing one Podman VM (parallel
# test sessions, CI) can each list and clean up only their own containers.
NAME_PREFIX = f"codegen-eval-{os.getpid()}-"

# Statuses attributable to the container or worker rather than candidate code.
INFRASTRUCTURE_STATUSES = frozenset({"infrastructure_error", "protocol_error"})
_WORKER_STATUSES = frozenset({
    "returned", "exception", "serialization_error", "output_limit",
    "protocol_violation", "candidate_crash",
})


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    value: Any = None
    args_after: Any = None
    detail: str = ""


def _exchange(process: subprocess.Popen[bytes], payload: bytes, seconds: float, max_output: int) -> tuple[bytes, bytes, str | None]:
    """Exchange bytes with the process, enforcing time and output limits."""
    assert process.stdin and process.stdout and process.stderr
    selector = selectors.DefaultSelector()
    streams = ((process.stdin, selectors.EVENT_WRITE, "input"),
               (process.stdout, selectors.EVENT_READ, "output"),
               (process.stderr, selectors.EVENT_READ, "error"))
    for stream, event, label in streams:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, event, label)

    offset = 0
    output = bytearray()
    error = bytearray()
    deadline = time.monotonic() + seconds
    reason: str | None = None
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "timeout"
                break
            for key, _ in selector.select(remaining):
                stream = key.fileobj
                if key.data == "input":
                    try:
                        offset += os.write(stream.fileno(), payload[offset:offset + 4096])
                    except BrokenPipeError:
                        offset = len(payload)
                    if offset >= len(payload):
                        selector.unregister(stream)
                        stream.close()
                else:
                    chunk = os.read(stream.fileno(), 4096)
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    target = output if key.data == "output" else error
                    target.extend(chunk)
                    if len(output) + len(error) > max_output:
                        reason = "protocol_limit"
                        break
            if reason:
                break
    finally:
        selector.close()
    return bytes(output), bytes(error), reason


def _container_command(name: str, limits: ExecutionLimits) -> list[str]:
    memory = f"{limits.memory_mib}m"
    return [
        "podman", "create", "-i", "--pull=never", "--name", name,
        "--network=none", "--read-only", "--read-only-tmpfs=false", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", f"--pids-limit={limits.max_processes}",
        f"--memory={memory}", f"--memory-swap={memory}", f"--cpus={limits.cpus}",
        "--user=65534:65534", "--workdir=/tmp",
        f"--tmpfs=/tmp:rw,nosuid,noexec,size={limits.tmp_mib}m", "--env=HOME=/tmp",
        IMAGE, "python", "-B", "-I", "-S", "-c", SUPERVISOR,
    ]


def _oom_killed(name: str) -> bool:
    """Whether the container's memory cgroup recorded an OOM kill. The container is
    kept (no --rm) until after this check so the state can still be read."""
    try:
        result = subprocess.run(["podman", "inspect", "--format", "{{.State.OOMKilled}}", name],
                                capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == b"true"


CLEANUP_SECONDS = 30  # total budget for verified removal; a late attempt may overrun it by ~15 s


def _container_exists(name: str) -> bool:
    try:
        result = subprocess.run(["podman", "container", "exists", name],
                                capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return True  # cannot tell: assume it is still there
    return result.returncode == 0


def _remove_container(name: str, *, retry: bool) -> None:
    """Remove the container; after an abnormal end, keep going until it is verifiably gone.

    The container is created in its own step and always exists before this runs, so the
    removal never races a creation that a killed client left in flight (an earlier design
    killed `podman run` mid-request and could never know whether the server would still
    create the container).

    `-t 0` kills at once. Without it `rm -f` sends SIGTERM and waits ten seconds before
    SIGKILL, and the supervisor is PID 1 and ignores SIGTERM; the five-second subprocess
    timeout then abandoned the client mid-stop and left the container in `Stopping`.

    The retries share one time budget (`CLEANUP_SECONDS`), so an unresponsive Podman costs
    a few tens of seconds at most, not a number of attempts times their timeouts."""
    end = time.monotonic() + CLEANUP_SECONDS
    while True:
        try:
            subprocess.run(["podman", "rm", "-f", "-t", "0", "--ignore", name],
                           capture_output=True, check=False,
                           timeout=max(min(10, end - time.monotonic()), 1))
        except (OSError, subprocess.TimeoutExpired):
            pass
        else:
            if not retry or not _container_exists(name):
                return
        if not retry or time.monotonic() >= end:
            return
        time.sleep(0.5)


CREATE_GRACE_SECONDS = 60  # cleanup allowance for a creation still running at the deadline


def _await_creation(creator: subprocess.Popen[bytes], deadline: float) -> tuple[bool, str | None, str]:
    """Wait for `podman create` to finish; returns (created, reason, detail).

    Creation counts against the deadline. If it is still running then, the candidate never
    ran: the client is not killed (that would leave the server finishing the creation
    unseen) but waited for, outside the deadline, so the container exists before cleanup."""
    try:
        creator.wait(timeout=max(deadline - time.monotonic(), 0))
    except subprocess.TimeoutExpired:
        try:
            creator.wait(timeout=CREATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            creator.kill()
            _reap(creator, kill=True)
        return False, "timeout", ""
    if creator.returncode == 0:
        return True, None, ""
    stderr = getattr(creator, "stderr", None)
    detail = stderr.read().decode("utf-8", "replace")[:500] if stderr else ""
    return False, None, detail


def _reap(process: subprocess.Popen[bytes], *, kill: bool, wait_seconds: float = 5) -> None:
    """Make sure the Podman client has exited so its return code is meaningful."""
    if not kill:
        try:
            process.wait(timeout=wait_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        pass


def execute_check(source: str, function_name: str, args: Sequence[Any],
                  limits: ExecutionLimits = DEFAULT_LIMITS) -> ExecutionResult:
    """Run one candidate call in a fresh container and return its raw outcome.

    Candidate-attributable statuses: returned, exception, serialization_error,
    output_limit, timeout, payload_too_large (rejected before any container starts),
    protocol_violation (forged or missing worker report), and candidate_crash.
    Infrastructure statuses are infrastructure_error and protocol_error.
    The caller must run validate_source first.
    """
    request = {"source": source, "function_name": function_name, "args": list(args)}
    size = len(json.dumps(request, ensure_ascii=False).encode("utf-8"))
    if size > limits.payload_bytes:
        return ExecutionResult("payload_too_large", detail="source and arguments exceed the payload limit")
    # The token is never given to the candidate: only the supervisor reads it
    # from stdin, and the executor uses it to sign its single report.
    payload = json.dumps({**request, "token": secrets.token_hex(16),
                          "limits": {"print_bytes": limits.print_bytes,
                                     "protocol_bytes": limits.protocol_bytes}},
                         ensure_ascii=False).encode("utf-8")

    name = f"{NAME_PREFIX}{uuid.uuid4().hex[:12]}"
    deadline = time.monotonic() + limits.deadline_seconds
    try:
        creator = subprocess.Popen(_container_command(name, limits), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
    except OSError as error:
        return ExecutionResult("infrastructure_error", detail=str(error))

    process: subprocess.Popen[bytes] | None = None
    reason: str | None = None
    completed = False
    oom_killed = False
    created = False
    try:
        created, reason, detail = _await_creation(creator, deadline)
        if not created and reason is None:
            return ExecutionResult("infrastructure_error", detail=detail)
        if created:
            try:
                process = subprocess.Popen(["podman", "start", "--attach", "--interactive", name],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
            except OSError as error:
                return ExecutionResult("infrastructure_error", detail=str(error))
            output, error, reason = _exchange(process, payload,
                                              max(deadline - time.monotonic(), 0),
                                              limits.protocol_bytes + 4096)
            completed = reason is None
    finally:
        # Cleanup happens after, and outside, the deadline. A client whose streams
        # closed normally is given time to exit; anything else is killed.
        if process is not None:
            _reap(process, kill=not completed)
            if completed and process.returncode not in (0, None):
                oom_killed = _oom_killed(name)
        _remove_container(name, retry=reason is not None or not created)

    if reason == "timeout":
        return ExecutionResult("timeout")
    if reason:
        return ExecutionResult("protocol_error", detail="supervisor output exceeded the protocol limit")
    assert process is not None  # a completed exchange always has a start client
    if process.returncode is None:
        return ExecutionResult("infrastructure_error", detail="container client did not exit")
    if process.returncode != 0 and oom_killed:
        # Only candidate allocations can exhaust the container's memory (the
        # supervisor's footprint is fixed), but the OOM killer may pick the
        # supervisor, ending the container without a report.
        return ExecutionResult("candidate_crash", detail="container memory limit exceeded (OOM kill)")
    if process.returncode != 0:
        return ExecutionResult("infrastructure_error", detail=error.decode("utf-8", "replace")[:500])
    # Only the supervisor can write to the container's stdout, so a malformed
    # message here is not attributable to candidate code.
    try:
        response = json.loads(output)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return ExecutionResult("protocol_error", detail="supervisor returned invalid JSON")
    if not isinstance(response, dict) or response.get("status") not in _WORKER_STATUSES:
        return ExecutionResult("protocol_error", detail="supervisor returned an invalid status")
    status = response["status"]
    if status == "returned":
        if "value" not in response or "args_after" not in response:
            return ExecutionResult("protocol_error", detail="supervisor omitted a return field")
        return ExecutionResult("returned", value=response["value"], args_after=response["args_after"])
    if status == "exception":
        return ExecutionResult("exception", detail=str(response.get("exception_type", "unknown")))
    return ExecutionResult(status, detail=str(response.get("detail", "")))


def run_case(source: str, task: Task, case: Case, *, timeout_seconds: float | None = None,
             limits: ExecutionLimits = DEFAULT_LIMITS) -> ExecutionResult:
    """Execute a structurally validated candidate on one case.

    Only the function name and this case's arguments are passed on; `case.expected`
    is never read here.
    """
    if timeout_seconds is not None:
        limits = limits.with_deadline(timeout_seconds)
    return execute_check(source, task.function_name, case.args, limits)
