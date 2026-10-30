"""Scripts that run inside the candidate container.

The supervisor is the container's first process. It marks itself non-dumpable
(so same-user candidate code cannot read its memory, environment, or open
descriptors through /proc) and resets SIGINT to its default action so, as
PID 1, it ignores every signal sent from inside the container (a Python signal
handler would otherwise be delivered). It starts the executor, which runs the candidate and reports on a
private pipe with a per-check token the candidate is never given. Only the
supervisor writes to the container's real stdout. Expected answers never enter
either script.
"""

EXECUTOR = r'''
import contextlib
import json
import math
import os
import sys


class OutputSink:
    def __init__(self, limit):
        self.limit = limit
        self.size = 0
        self.exceeded = False

    def write(self, value):
        self.size += len(value.encode("utf-8", "replace"))
        self.exceeded = self.size > self.limit
        return len(value)

    def flush(self):
        pass


def main():
    # Make the executor and its children the OOM killer's preferred victims.
    # An unprivileged process can lower this again, so the host also attributes
    # container OOM kills to the candidate; this is defence in depth.
    try:
        with open("/proc/self/oom_score_adj", "w") as handle:
            handle.write("1000")
    except OSError:
        pass
    payload = json.load(sys.stdin)
    token = payload["token"]
    report_fd = payload["report_fd"]
    args = payload["args"]
    write = os.write
    exit_now = os._exit
    quote = json.encoder.encode_basestring_ascii

    # Bind every builtin and helper now so candidate code that patches modules
    # or builtins afterwards cannot change how its results are serialised.
    def encode(value, depth=0, _type=type, _str=str, _int=int, _float=float, _bool=bool,
               _list=list, _tuple=tuple, _dict=dict, _int_repr=int.__repr__,
               _float_repr=float.__repr__, _quote=quote, _finite=math.isfinite,
               _join=str.join):
        if depth > 100:
            raise ValueError("nested too deeply")
        kind = _type(value)
        if value is None:
            return "null"
        if kind is _bool:
            return "true" if value else "false"
        if kind is _int:
            return _int_repr(value)
        if kind is _float:
            if not _finite(value):
                raise ValueError("non-finite float")
            return _float_repr(value)
        if kind is _str:
            return _quote(value)
        if kind is _list or kind is _tuple:
            return "[" + _join(",", [encode(item, depth + 1) for item in value]) + "]"
        if kind is _dict:
            parts = []
            for key, item in value.items():
                if _type(key) is not _str:
                    raise ValueError("non-string key")
                parts.append(_quote(key) + ":" + encode(item, depth + 1))
            return "{" + _join(",", parts) + "}"
        raise ValueError("unsupported type")

    def emit(fields):
        data = ('{"token":' + quote(token) + "," + fields + "}\n").encode("ascii")
        while data:
            data = data[write(report_fd, data):]
        exit_now(0)

    namespace = {}
    sink = OutputSink(payload["print_bytes"])
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            exec(compile(payload["source"], "<generated>", "exec"), namespace)
            value = namespace[payload["function_name"]](*args)
    except BaseException as error:
        if sink.exceeded:
            emit('"status":"output_limit"')
        name = type(error).__name__
        emit('"status":"exception","exception_type":' + quote(name if isinstance(name, str) else "unknown"))
    if sink.exceeded:
        emit('"status":"output_limit"')
    try:
        fields = '"status":"returned","value":' + encode(value) + ',"args_after":' + encode(args)
    except Exception:
        fields = '"status":"serialization_error"'
    emit(fields)


main()
'''

_SUPERVISOR_BODY = r'''
import ctypes
import json
import os
import selectors
import signal
import subprocess
import sys

STATUSES = {"returned", "exception", "serialization_error", "output_limit"}


def respond(**fields):
    sys.stdout.write(json.dumps(fields, ensure_ascii=True, allow_nan=False, separators=(",", ":")))
    sys.stdout.flush()
    os._exit(0)


def finish(limits, **fields):
    """Respond with a validated report, bounding what the supervisor itself writes.

    A forged report can be small yet expand on re-serialisation (1E9 becomes
    1000000000.0) or hold values that cannot be serialised (1e400); both are
    candidate outcomes, never supervisor failures."""
    try:
        text = json.dumps(fields, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (ValueError, RecursionError):
        respond(status="protocol_violation", detail="unserialisable worker report")
    if len(text) > limits["protocol_bytes"]:
        respond(status="output_limit", detail="protocol")
    sys.stdout.write(text)
    sys.stdout.flush()
    os._exit(0)


def reject_constant(name):
    raise ValueError("non-finite constant")


def parse_report(raw, token):
    """Return the genuine report, or None when it is missing, forged, or malformed."""
    try:
        lines = raw.decode("ascii").split("\n")
        if len(lines) != 2 or lines[1] != "":
            return None
        report = json.loads(lines[0], parse_constant=reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(report, dict) or report.pop("token", None) != token:
        return None
    status = report.get("status")
    allowed = {"status"}
    if status == "returned":
        allowed |= {"value", "args_after"}
        if not allowed <= set(report):
            return None
    elif status == "exception":
        allowed.add("exception_type")
    elif status not in STATUSES:
        return None
    return report if set(report) == allowed else None


def main():
    # Python's SIGINT handler would raise KeyboardInterrupt here; with SIG_DFL
    # the kernel discards signals sent by processes inside the container.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE = 0
        raise SystemExit("could not make the supervisor non-dumpable")
    payload = json.loads(sys.stdin.buffer.read())
    limits = payload.pop("limits")
    token = payload["token"]
    report_read, report_write = os.pipe()
    payload["report_fd"] = report_write
    payload["print_bytes"] = limits["print_bytes"]
    data = json.dumps(payload, ensure_ascii=True).encode("ascii")
    child = subprocess.Popen([sys.executable, "-B", "-I", "-S", "-c", EXECUTOR],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, pass_fds=(report_write,))
    os.close(report_write)
    try:
        supervise(child, data, report_read, token, limits)
    except BaseException:
        # Once the executor runs, a failure here was triggered by what it
        # produced; only failures before this point are infrastructure.
        child.kill()
        respond(status="protocol_violation", detail="supervisor could not process the worker output")


def supervise(child, data, report_read, token, limits):
    selector = selectors.DefaultSelector()
    streams = ((child.stdin, selectors.EVENT_WRITE, "input"),
               (child.stdout, selectors.EVENT_READ, "print"),
               (child.stderr, selectors.EVENT_READ, "print"),
               (os.fdopen(report_read, "rb", buffering=0), selectors.EVENT_READ, "report"))
    for stream, event, label in streams:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, event, label)

    offset = 0
    printed = 0
    report = bytearray()
    overflow = None

    def pump(timeout):
        nonlocal offset, printed, overflow
        events = selector.select(timeout)
        for key, _ in events:
            stream = key.fileobj
            if key.data == "input":
                try:
                    offset += os.write(stream.fileno(), data[offset:offset + 4096])
                except BrokenPipeError:
                    offset = len(data)
                if offset >= len(data):
                    selector.unregister(stream)
                    stream.close()
                continue
            try:
                chunk = os.read(stream.fileno(), 4096)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(stream)
                stream.close()
            elif key.data == "print":
                printed += len(chunk)
                if printed > limits["print_bytes"]:
                    overflow = "print"
            else:
                report.extend(chunk)
                if len(report) > limits["protocol_bytes"]:
                    overflow = "protocol"
        return len(events)

    while overflow is None and child.poll() is None:
        pump(0.05)
    while overflow is None and pump(0):
        pass
    if overflow:
        child.kill()
        child.wait()
        respond(status="output_limit", detail=overflow)
    code = child.returncode
    genuine = parse_report(bytes(report), token) if code == 0 else None
    if genuine is not None:
        if isinstance(genuine.get("exception_type"), str):
            genuine["exception_type"] = genuine["exception_type"][:100]
        finish(limits, **genuine)
    if code != 0:
        respond(status="candidate_crash", detail="worker exit code %d" % code)
    respond(status="protocol_violation", detail="missing or invalid worker report")


main()
'''

SUPERVISOR = "EXECUTOR = " + repr(EXECUTOR) + "\n" + _SUPERVISOR_BODY
