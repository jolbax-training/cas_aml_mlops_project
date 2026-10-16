"""Run one generated function call in a disposable, restricted container."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import Any

from codegen_eval.tasks import Case, Task


IMAGE = "docker.io/library/python@sha256:950206c37262dd86c55659797f6ee418fee30535072f65a82ed470d985f5cda5"
MAX_INPUT_BYTES = 65_536
MAX_OUTPUT_BYTES = 65_536

# Expected answers and scoring code never enter this process. The generated
# function sees only its source, name, and one case's arguments.
_WORKER = r'''
import contextlib
import json
import sys

class OutputSink:
    def __init__(self):
        self.size = 0
        self.exceeded = False

    def write(self, value):
        self.size += len(value.encode("utf-8", "replace"))
        self.exceeded = self.size > 32768
        return len(value)

    def flush(self):
        pass

payload = json.load(sys.stdin)
namespace = {}
sink = OutputSink()
try:
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        exec(compile(payload["source"], "<generated>", "exec"), namespace)
        value = namespace[payload["function_name"]](*payload["args"])
    if sink.exceeded:
        response = {"status": "output_limit"}
    else:
        response = {"status": "returned", "value": value, "args_after": payload["args"]}
except BaseException as error:
    response = {"status": "exception", "exception_type": type(error).__name__}
try:
    output = json.dumps(response, allow_nan=False, separators=(",", ":"))
except (TypeError, ValueError):
    output = '{"status":"serialization_error"}'
sys.stdout.write(output)
'''


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    value: Any = None
    args_after: Any = None
    detail: str = ""


def _exchange(process: subprocess.Popen[bytes], payload: bytes, seconds: float) -> tuple[bytes, bytes, str | None]:
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
                    if len(output) + len(error) > MAX_OUTPUT_BYTES:
                        reason = "output_limit"
                        break
            if reason:
                break
    finally:
        selector.close()
    return bytes(output), bytes(error), reason


def run_case(source: str, task: Task, case: Case, *, timeout_seconds: float = 8.0) -> ExecutionResult:
    """Execute a structurally validated candidate on one case.

    The caller must run validate_source first. Each case gets a fresh container.
    """
    payload = json.dumps({"source": source, "function_name": task.function_name, "args": case.args},
                         ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_INPUT_BYTES:
        return ExecutionResult("input_limit", detail="source and arguments exceed the input limit")

    name = f"codegen-eval-{uuid.uuid4().hex[:16]}"
    command = [
        "podman", "run", "--rm", "-i", "--pull=never", "--name", name,
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=32", "--memory=128m",
        "--cpus=1", "--user=65534:65534", "--workdir=/tmp",
        "--tmpfs=/tmp:rw,nosuid,noexec,size=16m", "--env=HOME=/tmp",
        IMAGE, "python", "-B", "-I", "-S", "-c", _WORKER,
    ]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
    except OSError as error:
        return ExecutionResult("infrastructure_error", detail=str(error))

    try:
        output, error, reason = _exchange(process, payload, timeout_seconds)
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        try:
            subprocess.run(["podman", "rm", "-f", "--ignore", name],
                           capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass

    if reason:
        return ExecutionResult(reason)
    if process.returncode != 0:
        return ExecutionResult("infrastructure_error", detail=error.decode("utf-8", "replace")[:500])
    try:
        response = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ExecutionResult("protocol_error", detail="worker returned invalid JSON")
    if not isinstance(response, dict) or response.get("status") not in {
        "returned", "exception", "serialization_error", "output_limit"
    }:
        return ExecutionResult("protocol_error", detail="worker returned an invalid status")
    if response["status"] == "returned":
        if "value" not in response or "args_after" not in response:
            return ExecutionResult("protocol_error", detail="worker omitted a return field")
        return ExecutionResult("returned", value=response["value"], args_after=response["args_after"])
    if response["status"] == "exception":
        return ExecutionResult("exception", detail=str(response.get("exception_type", "unknown")))
    if response["status"] == "output_limit":
        return ExecutionResult("output_limit")
    return ExecutionResult("serialization_error")
