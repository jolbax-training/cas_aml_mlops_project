"""Run one generated function call in a disposable, restricted container.

Expected answers and scoring never enter this module: `execute_check` takes only
source, function name, and one check's arguments, and returns raw outcomes."""

from __future__ import annotations

import json
import os
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


IMAGE = "docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5"

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
        "podman", "run", "--rm", "-i", "--pull=never", "--name", name,
        "--network=none", "--read-only", "--read-only-tmpfs=false", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", f"--pids-limit={limits.max_processes}",
        f"--memory={memory}", f"--memory-swap={memory}", f"--cpus={limits.cpus}",
        "--user=65534:65534", "--workdir=/tmp",
        f"--tmpfs=/tmp:rw,nosuid,noexec,size={limits.tmp_mib}m", "--env=HOME=/tmp",
        IMAGE, "python", "-B", "-I", "-S", "-c", SUPERVISOR,
    ]


def _remove_container(name: str, *, retry: bool) -> None:
    """Remove the container. After a killed client the server may still be creating
    it, so later passes run to catch a late creation."""
    for attempt in range(3 if retry else 1):
        if attempt:
            time.sleep(1.0)
        try:
            subprocess.run(["podman", "rm", "-f", "--ignore", name],
                           capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _reap(process: subprocess.Popen[bytes], *, kill: bool) -> None:
    """Make sure the Podman client has exited so its return code is meaningful."""
    if not kill:
        try:
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
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

    name = f"codegen-eval-{uuid.uuid4().hex[:16]}"
    try:
        process = subprocess.Popen(_container_command(name, limits), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        return ExecutionResult("infrastructure_error", detail=str(error))

    reason: str | None = None
    completed = False
    try:
        output, error, reason = _exchange(process, payload, limits.deadline_seconds,
                                          limits.protocol_bytes + 4096)
        completed = reason is None
    finally:
        # Cleanup happens after, and outside, the deadline. A client whose streams
        # closed normally is given time to exit; anything else is killed.
        _reap(process, kill=not completed)
        _remove_container(name, retry=reason is not None)

    if reason == "timeout":
        return ExecutionResult("timeout")
    if reason:
        return ExecutionResult("protocol_error", detail="supervisor output exceeded the protocol limit")
    if process.returncode is None:
        return ExecutionResult("infrastructure_error", detail="container client did not exit")
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
