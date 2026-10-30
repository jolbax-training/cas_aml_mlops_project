"""Hostile candidates run through the real container path.

Each probe asserts the trusted-side classification, not just that the container
survived. Run with RUN_SANDBOX_TESTS=1 and a running Podman VM.
"""

import os
import subprocess
from pathlib import Path

import pytest

from codegen_eval import sandbox
from codegen_eval.evaluate import score_case
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.sandbox import INFRASTRUCTURE_STATUSES, execute_check, run_case
from codegen_eval.tasks import load_tasks


pytestmark = [pytest.mark.sandbox, pytest.mark.skipif(
    os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM"
)]
ROOT = Path(__file__).resolve().parents[1]
TASKS = load_tasks(ROOT / "data" / "pilot_tasks.json", {"strings": 1, "lists": 1, "dictionaries": 1})
VOWELS, UNIQUE = TASKS[0], TASKS[1]
VOWEL_HEAD = "def count_vowels(text: str) -> int:\n"
UNIQUE_HEAD = "def unique_in_order(items: list[int]) -> list[int]:\n"


def run_vowels(body: str, imports: str = "", **kwargs):
    return run_case(f"{imports}\n{VOWEL_HEAD}{body}", VOWELS, VOWELS.cases[0], **kwargs)


def run_unique(body: str, imports: str = ""):
    return run_case(f"{imports}\n{UNIQUE_HEAD}{body}", UNIQUE, UNIQUE.cases[0])


def trusted_failures(source: str):
    """Classify like the evaluator would: expected values live only on this side."""
    case = UNIQUE.cases[0]
    return score_case(case, run_case(source, UNIQUE, case)).failures


# --- host isolation -------------------------------------------------------

def test_host_files_are_not_visible(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("host secret")
    result = run_vowels(f"""    import os
    paths = [{str(secret)!r}, {str(ROOT / "data" / "pilot_tasks.json")!r}, "/Users", "/run/podman/podman.sock", "/var/run/docker.sock"]
    return sum(os.path.exists(path) for path in paths)
""")

    assert (result.status, result.value) == ("returned", 0)


def test_host_environment_and_credentials_are_absent():
    result = run_vowels("""    import os
    names = ("CODEGEN_EVAL_TEST_SECRET", "OPENROUTER_API_KEY", "MLFLOW_TRACKING_URI", "HOME")
    return sum(name in os.environ for name in names[:3]) * 10 + len(os.environ.get("CODEGEN_EVAL_TEST_SECRET", ""))
""")

    assert (result.status, result.value) == ("returned", 0)


def test_network_is_unreachable():
    result = run_vowels("""    import socket
    for address in (("1.1.1.1", 80), ("127.0.0.1", 5000), ("host.containers.internal", 80)):
        try:
            socket.create_connection(address, timeout=0.5)
        except OSError:
            continue
        return -1
    return 0
""")

    assert (result.status, result.value) == ("returned", 0)


def test_root_filesystem_is_read_only_but_tmp_is_writable():
    result = run_vowels("""    results = 0
    for path in ("/etc/probe", "/usr/probe", "/probe"):
        try:
            open(path, "w")
        except OSError:
            results += 1
    open("/tmp/ok", "w").write("x")
    return results
""")

    assert (result.status, result.value) == ("returned", 3)


def test_candidate_runs_unprivileged_with_no_capabilities_or_mounts():
    result = run_vowels("""    status = open("/proc/self/status").read()
    caps = [line.split()[1] for line in status.splitlines() if line.startswith("CapEff")][0]
    mounts = open("/proc/self/mountinfo").read()
    host_visible = any(word in mounts for word in ("/Users", "virtiofs", "podman.sock", "cas_aml"))
    return (os.getuid() == 65534) * 1 + (int(caps, 16) == 0) * 2 + (not host_visible) * 4
""", imports="import os")

    assert (result.status, result.value) == ("returned", 7)


def test_state_from_one_check_is_not_visible_to_the_next():
    first = run_vowels("""    open("/tmp/marker", "w").write("first")
    return 0
""")
    second = run_vowels("""    import os
    return int(os.path.exists("/tmp/marker"))
""")

    assert (first.status, second.status, second.value) == ("returned", "returned", 0)


# --- limits through the real container path -------------------------------

def test_timeout_includes_container_startup_and_cleanup_is_separate():
    result = run_vowels("    return 0\n", timeout_seconds=0.05)
    loop = run_vowels("    while True:\n        pass\n", timeout_seconds=1.0)
    listing = subprocess.run(["podman", "ps", "-a", "--filter", f"name={sandbox.NAME_PREFIX}", "--format", "{{.Names}}"],
                             capture_output=True, text=True, check=True)

    assert result.status == "timeout" and loop.status == "timeout"
    assert listing.stdout.strip() == ""


def test_print_flood_through_print_or_raw_descriptor_is_output_limit():
    printed = run_vowels("    print('x' * 40000)\n    return 2\n")
    raw = run_vowels("    os.write(1, b'x' * 40000)\n    return 2\n", imports="import os")
    stderr = run_vowels("    sys.stderr.write('x' * 40000)\n    return 2\n", imports="import sys")

    assert [printed.status, raw.status, stderr.status] == ["output_limit"] * 3


def test_oversized_return_value_exceeds_protocol_limit():
    result = run_vowels("    return 'y' * 70000\n")

    assert result.status == "output_limit"


def test_custom_limits_are_enforced_in_the_container():
    small = ExecutionLimits(print_bytes=100)
    result = execute_check(f"{VOWEL_HEAD}    print('x' * 200)\n    return 2\n", "count_vowels", ["a"], small)

    assert result.status == "output_limit"


def test_memory_limit_kills_the_candidate_not_the_supervisor():
    result = run_vowels("    blob = bytearray(400 * 1024 * 1024)\n    for i in range(0, len(blob), 4096):\n        blob[i] = 1\n    return 2\n")

    assert result.status == "candidate_crash"


def test_process_limit_blocks_a_fork_bomb():
    result = run_vowels("""    count = 0
    for _ in range(200):
        try:
            if os.fork() == 0:
                time.sleep(30)
                os._exit(0)
        except OSError:
            return count
        count += 1
    return -1
""", imports="import os, time")

    assert result.status == "returned" and 0 < result.value < 32


def test_tmp_storage_limit_is_enforced():
    result = run_vowels("""    try:
        with open("/tmp/big", "wb") as handle:
            for _ in range(40):
                handle.write(b"z" * 1024 * 1024)
                handle.flush()
    except OSError:
        return 1
    return 0
""")

    assert (result.status, result.value) == ("returned", 1)


def test_cpu_and_memory_cgroup_limits_match_the_configuration():
    result = run_vowels('''    cpu = open("/sys/fs/cgroup/cpu.max").read().split()
    memory = int(open("/sys/fs/cgroup/memory.max").read())
    return (cpu[0] == cpu[1]) * 1 + (memory == 128 * 1024 * 1024) * 2
''')

    assert (result.status, result.value) == ("returned", 3)


def test_candidate_exception_is_a_candidate_outcome():
    result = run_vowels("    raise ValueError('nope')\n")

    assert (result.status, result.detail) == ("exception", "ValueError")


# --- scoring integrity ----------------------------------------------------

def test_plain_mutation_is_recorded():
    assert trusted_failures(f"{UNIQUE_HEAD}    items.append(99)\n    return [3, 1, 2]\n") == ("mutated_input",)


FORGE_STDOUT = f'''import json, os
{UNIQUE_HEAD}    original = list(items)
    items.append(99)
    os.write(1, json.dumps({{"status": "returned", "value": [3, 1, 2], "args_after": [original]}}).encode())
    os._exit(0)
'''
FORGE_FD = f'''import json, os
{UNIQUE_HEAD}    original = list(items)
    items.append(99)
    report = json.dumps({{"status": "returned", "value": [3, 1, 2], "args_after": [original]}}).encode()
    for fd in range(3, 20):
        try:
            os.write(fd, report + b"\\n")
        except OSError:
            pass
    os._exit(0)
'''
FORGE_TOKEN_GUESS = f'''import json, os
{UNIQUE_HEAD}    original = list(items)
    items.append(99)
    for fd in range(3, 20):
        try:
            os.write(fd, json.dumps({{"token": "", "status": "returned", "value": [3, 1, 2], "args_after": [original]}}).encode() + b"\\n")
        except OSError:
            pass
    return [3, 1, 2]
'''
FORGE_SUPERVISOR = f'''import os, signal
{UNIQUE_HEAD}    items.append(99)
    for path in ("/proc/1/fd/1", "/proc/1/mem", "/proc/1/environ"):
        try:
            os.write(os.open(path, os.O_WRONLY), b'{{"status":"returned","value":[3,1,2],"args_after":[[3,1,3,2,1]]}}')
        except OSError:
            pass
    try:
        os.kill(1, signal.SIGKILL)
    except OSError:
        pass
    return [3, 1, 2]
'''


@pytest.mark.parametrize("source", [FORGE_STDOUT, FORGE_FD, FORGE_TOKEN_GUESS],
                         ids=["stdout", "descriptors", "guessed-token"])
def test_forged_worker_response_is_never_accepted(source):
    case = UNIQUE.cases[0]
    execution = run_case(source, UNIQUE, case)

    assert execution.status == "protocol_violation"
    assert score_case(case, execution).failures == ("protocol_violation",)
    assert execution.value is None


def test_candidate_cannot_reach_or_kill_the_supervisor():
    execution = run_case(FORGE_SUPERVISOR, UNIQUE, UNIQUE.cases[0])

    assert execution.status == "returned"
    assert execution.args_after == [[3, 1, 3, 2, 1, 99]]
    assert trusted_failures(FORGE_SUPERVISOR) == ("mutated_input",)


CONCEAL_JSON = f'''import json
{UNIQUE_HEAD}    original = list(items)
    items.append(99)
    real = json.dumps
    def lie(obj, **kw):
        if isinstance(obj, dict) and obj.get("status") == "returned":
            obj = dict(obj, args_after=[original])
        return real(obj, **kw)
    json.dumps = lie
    return [3, 1, 2]
'''
CONCEAL_MODULES = f'''import sys, builtins, json
{UNIQUE_HEAD}    original = list(items)
    items.append(99)
    class FakeJson:
        @staticmethod
        def dumps(obj, **kw):
            return json.dumps({{"status": "returned", "value": [3, 1, 2], "args_after": [original]}})
        @staticmethod
        def load(handle):
            return None
    sys.modules["json"] = FakeJson
    json.encoder.encode_basestring_ascii = lambda value: '"x"'
    builtins.type = lambda value: list
    builtins.isinstance = lambda *a: True
    return [3, 1, 2]
'''
CONCEAL_SUBCLASS = f'''{UNIQUE_HEAD}    original = list(items)
    class Liar(list):
        def __iter__(self):
            return iter(original)
        def __len__(self):
            return len(original)
    items.append(99)
    return Liar([3, 1, 2])
'''
CONCEAL_EDIT_BACK = f'''{UNIQUE_HEAD}    items.append(99)
    items.pop()
    return [3, 1, 2]
'''


@pytest.mark.parametrize("source", [CONCEAL_JSON, CONCEAL_MODULES], ids=["patched-json", "patched-modules"])
def test_concealed_mutation_is_still_recorded(source):
    execution = run_case(source, UNIQUE, UNIQUE.cases[0])

    assert execution.status == "returned"
    assert execution.args_after == [[3, 1, 3, 2, 1, 99]]
    assert trusted_failures(source) == ("mutated_input",)


def test_value_subclass_trickery_is_not_accepted_as_a_result():
    execution = run_case(CONCEAL_SUBCLASS, UNIQUE, UNIQUE.cases[0])

    assert execution.status == "serialization_error"


def test_mutation_that_is_fully_undone_is_not_reported_as_mutation():
    assert trusted_failures(CONCEAL_EDIT_BACK) == ()


def test_exiting_without_a_report_is_a_candidate_outcome_not_infrastructure():
    exited = run_unique("    os._exit(0)\n", imports="import os")
    killed = run_unique("    os.kill(os.getpid(), 9)\n", imports="import os")

    assert exited.status == "protocol_violation"
    assert killed.status == "candidate_crash"


# --- attribution: hostile behaviour must not become an infrastructure outcome ---

def assert_candidate_outcome(source: str, expected_status: str):
    case = UNIQUE.cases[0]
    execution = run_case(source, UNIQUE, case)

    assert execution.status == expected_status, execution
    assert execution.status not in INFRASTRUCTURE_STATUSES
    assert not set(score_case(case, execution).failures) & INFRASTRUCTURE_STATUSES
    return execution


def test_a_trivial_correct_candidate_is_returned_so_the_executor_itself_is_sound():
    source = f"{UNIQUE_HEAD}    return list(dict.fromkeys(items))\n"
    execution = assert_candidate_outcome(source, "returned")

    assert execution.value == [3, 1, 2]
    assert trusted_failures(source) == ()


@pytest.mark.parametrize("signal_name", ["SIGINT", "SIGTERM", "SIGHUP", "SIGUSR1", "SIGUSR2", "SIGQUIT", "SIGALRM", "SIGPIPE", "SIGCHLD", "SIGCONT"])
def test_signals_sent_to_the_supervisor_do_not_disturb_the_check(signal_name):
    execution = assert_candidate_outcome(f"""import os, signal, time
{UNIQUE_HEAD}    os.kill(1, signal.{signal_name})
    time.sleep(0.3)
    return [3, 1, 2]
""", "returned")

    assert execution.value == [3, 1, 2]


def test_deeply_nested_return_value_is_a_candidate_outcome():
    assert_candidate_outcome(f"""import sys
{UNIQUE_HEAD}    sys.setrecursionlimit(100000)
    value = []
    for _ in range(30000):
        value = [value]
    return value
""", "serialization_error")


def test_moderately_nested_return_value_is_a_candidate_outcome():
    assert_candidate_outcome(f"""{UNIQUE_HEAD}    value = []
    for _ in range(500):
        value = [value]
    return value
""", "serialization_error")


def test_print_overflow_followed_by_an_exception_is_output_limit():
    assert_candidate_outcome(f"{UNIQUE_HEAD}    print('x' * 40000)\n    raise ValueError('late')\n", "output_limit")


FORGE_PREFIX = f'''import sys
{UNIQUE_HEAD}    emit = sys._getframe(1).f_locals["emit"]
'''


def test_forged_nan_report_is_a_candidate_outcome():
    assert_candidate_outcome(
        FORGE_PREFIX + '    emit(\'"status":"returned","value":NaN,"args_after":[[3,1,3,2,1]]\')\n',
        "protocol_violation")


def test_forged_overflowing_number_report_is_a_candidate_outcome():
    assert_candidate_outcome(
        FORGE_PREFIX + '    emit(\'"status":"returned","value":1e400,"args_after":[[3,1,3,2,1]]\')\n',
        "protocol_violation")


def test_forged_report_that_expands_when_reserialised_is_a_candidate_outcome():
    assert_candidate_outcome(
        FORGE_PREFIX + '    emit(\'"status":"returned","value":[\' + ",".join(["1E9"] * 12000) + \'],"args_after":[[3,1,3,2,1]]\')\n',
        "output_limit")


def test_forged_deeply_nested_report_is_a_candidate_outcome():
    assert_candidate_outcome(
        FORGE_PREFIX + '    emit(\'"status":"returned","value":\' + "[" * 30000 + "]" * 30000 + \',"args_after":[[3,1,3,2,1]]\')\n',
        "protocol_violation")


OOM_MANY_SMALL = f'''import os, time
{UNIQUE_HEAD}    for _ in range(28):
        if os.fork() == 0:
            blob = bytearray(4_500_000)
            for i in range(0, len(blob), 4096):
                blob[i] = 1
            time.sleep(8)
            os._exit(0)
    time.sleep(3)
    return [3, 1, 2]
'''
OOM_MANY_SMALL_RESET = OOM_MANY_SMALL.replace(
    "    for _ in range(28):",
    "    open('/proc/self/oom_score_adj', 'w').write('0')\n    for _ in range(28):")


@pytest.mark.parametrize("source", [OOM_MANY_SMALL, OOM_MANY_SMALL_RESET], ids=["many-small-processes", "oom-score-reset"])
def test_candidate_induced_container_oom_is_never_infrastructure(source):
    case = UNIQUE.cases[0]
    execution = run_case(source, UNIQUE, case)

    # Depending on which process the OOM killer takes, the check may end as returned,
    # candidate_crash, or timeout; all are candidate outcomes.
    assert execution.status in {"returned", "candidate_crash", "timeout"}, execution
    assert execution.status not in INFRASTRUCTURE_STATUSES
    assert not set(score_case(case, execution).failures) & INFRASTRUCTURE_STATUSES


def test_lone_surrogate_return_value_is_a_scorable_candidate_outcome():
    case = UNIQUE.cases[0]
    execution = run_case(f"{UNIQUE_HEAD}    return ['\\ud800']\n", UNIQUE, case)

    assert execution.status == "returned"
    assert score_case(case, execution).failures == ("wrong_answer",)
