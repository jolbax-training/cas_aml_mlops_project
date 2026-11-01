"""Stub-based checks for scripts/orchestration: fake `orca` and `curl` on PATH, canned output, no network or Orca."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts" / "orchestration"

# Plays back out.<n> (and optional err.<n>) for the n-th call, repeating the last one; logs each call's arguments.
ORCA_STUB = """#!/bin/sh
D="$STUB_DIR"
n=$(( $(cat "$D/count" 2>/dev/null || echo 0) + 1 )); echo $n > "$D/count"
echo "$*" >> "$D/calls"
f="$D/out.$n"; [ -f "$f" ] || f=$(ls "$D"/out.* | sort -t. -k2 -n | tail -1)
[ -f "$D/err.$n" ] && cat "$D/err.$n" >&2
cat "$f"
exit "$(cat "$D/rc" 2>/dev/null || echo 0)"
"""

# Maps the URL tail to a canned file; the run body plays run.<n> per poll; unmapped URLs answer with a rate-limit body.
CURL_STUB = """#!/bin/sh
D="$STUB_DIR"
for u; do :; done
echo "$u" >> "$D/urls"
case "$u" in
  */actions/runs/*/jobs) name=jobs ;;
  */actions/runs/*) k=$(( $(cat "$D/polls" 2>/dev/null || echo 0) + 1 )); echo $k > "$D/polls"
                    name="run.$k"; [ -f "$D/$name" ] || name=$(ls "$D"/run.* | sort -t. -k2 -n | tail -1 | xargs basename) ;;
  */actions/jobs/*) name="job-${u##*/}" ;;
  */check-runs/*/annotations) p=${u%/annotations}; name="ann-${p##*/}" ;;
esac
if [ -f "$D/$name" ]; then cat "$D/$name"; else echo '{"message": "API rate limit exceeded for 1.2.3.4"}'; fi
"""


@pytest.fixture
def stub(tmp_path):
    bindir, state = tmp_path / "bin", tmp_path / "state"
    bindir.mkdir()
    state.mkdir()
    for name, text in (("orca", ORCA_STUB), ("curl", CURL_STUB)):
        (bindir / name).write_text(text)
        (bindir / name).chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", STUB_DIR=str(state))
    env.pop("CIWATCH_REPO", None)
    return state, env


def run(script, args, env, cwd=None):
    return subprocess.run(["sh", str(SCRIPTS / script), *args], env=env, cwd=cwd,
                          capture_output=True, text=True, timeout=60)


def delivery(delivery_id, messages, timed_out=False):
    return json.dumps({"result": {"deliveryId": delivery_id, "timedOut": timed_out, "count": len(messages),
                                  "messages": messages}})


def message(kind, subject="s", body="b"):
    return {"type": kind, "id": f"msg_{kind}", "from_handle": "term_x", "subject": subject, "body": body,
            "payload": {"k": 1}}


# --- dry-run and help -------------------------------------------------------------------------

@pytest.mark.parametrize("script", ["wait.sh", "waitloop.sh", "ciwatch.sh"])
def test_help_prints_usage_without_side_effects(script, stub):
    state, env = stub
    result = run(script, ["--help"], env)
    assert result.returncode == 0 and "Usage" in result.stdout
    assert not (state / "calls").exists() and not (state / "urls").exists()


def test_wait_dry_run_prints_resolved_command(stub):
    state, env = stub
    result = run("wait.sh", ["--dry-run", "--terminal", "T1", "--ack", "d9", "--timeout-ms", "5"], env)
    assert result.stdout.strip() == ("orca orchestration check --terminal T1 --ack d9 --wait "
                                     "--types worker_done,escalation,question --timeout-ms 5 --json")
    assert not (state / "calls").exists()


def test_ciwatch_dry_run_resolves_repo_from_origin_remote(stub, tmp_path):
    state, env = stub
    clone = tmp_path / "clone"
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", "git@github.com:acme/widgets.git"], check=True)
    result = run("ciwatch.sh", ["--dry-run", "7"], env, cwd=clone)
    assert "repos/acme/widgets/actions/runs/7" in result.stdout
    https = run("ciwatch.sh", ["--dry-run", "--repo", "other/repo", "7"], env, cwd=clone)
    assert "repos/other/repo/" in https.stdout
    assert not (state / "urls").exists()


def test_scripts_hold_no_session_identifiers():
    pattern = re.compile(r"ctx_|term_[0-9a-f]|run_[0-9a-f]{6,}|delivery_[0-9a-f]|/private/tmp|/Users/|jolbax")
    for path in SCRIPTS.glob("*.sh"):
        assert not pattern.search(path.read_text()), path.name


# --- wait.sh ----------------------------------------------------------------------------------

def test_wait_prints_summary_and_filters_keepalives(stub):
    state, env = stub
    (state / "out.1").write_text(delivery("delivery_a", [message("worker_done", "done", "all green")]))
    (state / "err.1").write_text('{"_keepalive": true}\n')
    result = run("wait.sh", ["--ack", "delivery_prev"], env)
    assert result.returncode == 0
    assert "delivery delivery_a timedOut False count 1" in result.stdout
    assert "--- worker_done msg_worker_done term_x done" in result.stdout and "all green" in result.stdout
    assert "_keepalive" not in result.stderr
    assert "--ack delivery_prev --wait" in (state / "calls").read_text()


def test_wait_reports_non_json_and_failure(stub):
    state, env = stub
    (state / "out.1").write_text("Error: Orca is not running\n")
    (state / "rc").write_text("1")
    result = run("wait.sh", [], env)
    assert result.returncode == 2 and "Orca is not running" in result.stdout


def test_wait_diagnostic_stderr_does_not_break_summary(stub):
    state, env = stub
    (state / "out.1").write_text(delivery("delivery_a", []))
    (state / "err.1").write_text("warning: something odd\n")
    result = run("wait.sh", [], env)
    assert result.returncode == 0 and "count 0" in result.stdout and "something odd" in result.stderr


# --- waitloop.sh ------------------------------------------------------------------------------

def test_waitloop_acks_heartbeat_batches_then_stops_at_actionable_delivery_without_acking_it(stub):
    state, env = stub
    (state / "out.1").write_text(delivery("delivery_1", [message("heartbeat")]))
    (state / "out.2").write_text(delivery("delivery_2", [message("heartbeat")]))
    (state / "out.3").write_text(delivery("delivery_3", [message("worker_done", "finished")]))
    result = run("waitloop.sh", ["--terminal", "T1"], env)
    assert result.returncode == 0 and "--- worker_done" in result.stdout
    calls = (state / "calls").read_text().splitlines()
    assert len(calls) == 3
    assert "--ack" not in calls[0]
    assert "--ack delivery_1" in calls[1] and "--ack delivery_2" in calls[2]
    assert all("delivery_3" not in call for call in calls)


@pytest.mark.parametrize("kind", ["question", "escalation"])
def test_waitloop_stops_on_question_and_escalation(kind, stub):
    state, env = stub
    (state / "out.1").write_text(delivery("delivery_q", [message(kind)]))
    result = run("waitloop.sh", [], env)
    assert result.returncode == 0 and f"--- {kind} " in result.stdout


def test_waitloop_exhausted_rounds_exit_nonzero_and_name_the_pending_ack(stub):
    state, env = stub
    (state / "out.1").write_text(delivery("delivery_h", [message("heartbeat")], timed_out=False))
    result = run("waitloop.sh", ["--rounds", "2"], env)
    assert result.returncode == 1
    assert "no actionable message after 2 rounds" in result.stdout and "delivery_h still unacked" in result.stdout
    assert len((state / "calls").read_text().splitlines()) == 2


def test_waitloop_propagates_wait_failure(stub):
    state, env = stub
    (state / "out.1").write_text("not json")
    result = run("waitloop.sh", [], env)
    assert result.returncode == 2 and "no usable delivery" in result.stdout


# --- ciwatch.sh -------------------------------------------------------------------------------

def seed_run(state, conclusion, annotations):
    (state / "run.1").write_text(json.dumps({"id": 7, "status": "in_progress", "conclusion": None}))
    (state / "run.2").write_text(json.dumps({"id": 7, "status": "completed", "conclusion": conclusion,
                                             "head_sha": "abcdef1234", "html_url": "https://example.test/run/7"}))
    (state / "jobs").write_text(json.dumps({"jobs": [{"id": 11}]}))
    steps = [{"name": "Set up", "conclusion": "success"},
             {"name": "Tests", "conclusion": "failure" if conclusion == "failure" else "success"},
             {"name": "Cache", "conclusion": "skipped"}]
    (state / "job-11").write_text(json.dumps({"name": "offline", "conclusion": conclusion, "steps": steps}))
    (state / "ann-11").write_text(json.dumps(annotations))


def test_ciwatch_failure_prints_steps_and_annotations_and_exits_nonzero(stub):
    state, env = stub
    seed_run(state, "failure", [
        {"annotation_level": "failure", "title": "test_a", "message": "assert 1 == 2\nline two"},
        {"annotation_level": "warning", "title": "", "message": "Node.js 20 actions are deprecated"}])
    result = run("ciwatch.sh", ["--repo", "acme/widgets", "--interval", "0", "7"], env)
    assert result.returncode == 1
    assert "run 7 abcdef1 failure https://example.test/run/7" in result.stdout
    assert "job offline failure ['Tests']" in result.stdout
    assert "failure test_a assert 1 == 2 | line two" in result.stdout and "Node.js 20" not in result.stdout
    assert (state / "polls").read_text().strip() == "2"
    assert all("/repos/acme/widgets/" in url for url in (state / "urls").read_text().split())


def test_ciwatch_success_exits_zero(stub):
    state, env = stub
    seed_run(state, "success", [])
    result = run("ciwatch.sh", ["--repo", "acme/widgets", "--interval", "0", "7"], env)
    assert result.returncode == 0 and "job offline success []" in result.stdout


def test_ciwatch_rate_limit_is_reported_not_misread(stub):
    state, env = stub
    result = run("ciwatch.sh", ["--repo", "acme/widgets", "--interval", "0", "7"], env)
    (state / "run.1").unlink(missing_ok=True)
    assert result.returncode == 2 and "GitHub API error" in result.stdout and "rate limit exceeded" in result.stdout


def test_ciwatch_gives_up_after_max_polls(stub):
    state, env = stub
    (state / "run.1").write_text(json.dumps({"id": 7, "status": "in_progress", "conclusion": None}))
    result = run("ciwatch.sh", ["--repo", "acme/widgets", "--interval", "0", "--max-polls", "3", "7"], env)
    assert result.returncode == 3 and "still in_progress after 3 polls" in result.stdout


def test_ciwatch_requires_a_repository(stub, tmp_path):
    state, env = stub
    bare = tmp_path / "norepo"
    bare.mkdir()
    result = run("ciwatch.sh", ["7"], env, cwd=bare)
    assert result.returncode == 2 and "--repo" in result.stderr
