import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from codegen_eval import bundle, sandbox
from codegen_eval.bundle import BundleError, load_trial, verify_bundle
from codegen_eval.evaluate import CaseResult, TrialGrade
from codegen_eval.model_client import FixtureClient, ModelResponse, load_fixtures
from codegen_eval.replay import make_grader, replay_bundle
from codegen_eval.run_recording import run_recorded
from codegen_eval.tasks import load_benchmark

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
SCENARIOS = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")
TASKS = load_benchmark(BENCHMARK)
TASK = TASKS[0]  # strings_01, the task the agent fixtures are written for
BY_ID = {t.id: t for t in TASKS}
FREEZE = json.loads((ROOT / "data" / "benchmark_v1.freeze.json").read_text())


@pytest.fixture
def local_runner(inprocess_runner):
    """Case runner with the evaluator's (source, task, case) shape, executing in-process."""
    return lambda source, task, case: inprocess_runner(source, task.function_name, case.args)


def scenario_client(name):
    return lambda task, trial_id: FixtureClient.from_data(SCENARIOS[name])


def record(tmp_path, inprocess_runner, local_runner, name="early_submission", *, trials=2,
           grade=True, run_id="run-a"):
    return run_recorded(
        [TASK], scenario_client(name), BENCHMARK, bundle_root=tmp_path, run_id=run_id,
        trials_per_task=trials, runner=inprocess_runner,
        grader=make_grader(local_runner) if grade else None,
        model_settings={"client": "fixture", "scenario": name})


def test_fixture_run_writes_a_complete_bundle_with_identity(tmp_path, inprocess_runner, local_runner):
    path, result = record(tmp_path, inprocess_runner, local_runner, "tool_use_and_revision")

    assert result.complete and result.planned == ("strings_01-t1", "strings_01-t2")
    manifest = bundle.load_manifest(path)
    assert manifest["status"] == "complete" and manifest["schema_version"] == 1
    identity = manifest["identity"]
    assert identity["benchmark"]["sha256"] == bundle.sha256_file(BENCHMARK)
    assert identity["benchmark"]["freeze_content_hash"] == FREEZE["content_hash"]
    assert len(identity["evaluator_source_sha256"]) == 64
    assert identity["benchmark"]["version"] and len(identity["execution_limits"]["hash"]) == 64
    assert identity["agent_limits"]["max_model_calls"] == 4
    assert identity["prompt"]["version"] == "baseline_agent_v1"
    assert identity["container_image"].startswith("docker.io/library/python@sha256:")
    assert identity["runtime"]["python"] and identity["evaluator_revision"]
    assert identity["model"]["client"] == "fixture"

    trial = load_trial(path, "strings_01-t1")
    assert trial["status"] == "submitted" and trial["final_source"].startswith("def count_vowels")
    assert len(trial["requests"]) == trial["model_calls"] == len(trial["responses"]) == 3
    assert [d["attempt"] for d in trial["candidate_history"]] == [1, 2]
    assert trial["grades"]["status"] == "graded" and len(trial["grades"]["checks"]) == 4
    assert [c["id"] for c in trial["grades"]["checks"]] == [c.id for c in TASK.cases]
    assert trial["reservation"] is None and trial["attempts"] == [] and trial["latency_ms"] is None
    assert not list((path / "trials").glob("*.calls.jsonl"))  # superseded by the records


def test_grades_are_a_pending_placeholder_until_a_grader_fills_them(tmp_path, inprocess_runner, local_runner):
    path, result = record(tmp_path, inprocess_runner, local_runner, grade=False)

    assert result.complete and result.grades_pending == result.planned
    assert load_trial(path, "strings_01-t1")["grades"] == {"status": "pending", "checks": []}


def test_interrupted_run_keeps_completed_records_and_is_incomplete(tmp_path, inprocess_runner):
    def client_for(task, trial_id):
        if trial_id.endswith("t2"):
            raise KeyboardInterrupt
        return FixtureClient.from_data(SCENARIOS["early_submission"])

    with pytest.raises(KeyboardInterrupt):
        run_recorded([TASK], client_for, BENCHMARK, bundle_root=tmp_path, run_id="run-i",
                     trials_per_task=3, runner=inprocess_runner)

    path = tmp_path / "run-i"
    result = verify_bundle(path)
    assert not result.complete and result.recorded == ("strings_01-t1",)
    assert result.missing() == ("strings_01-t2", "strings_01-t3")
    assert bundle.load_manifest(path)["status"] == "incomplete"
    assert any("KeyboardInterrupt" in r for r in bundle.load_manifest(path)["reasons"])
    assert load_trial(path, "strings_01-t1")["status"] == "submitted"


def test_unfinished_manifest_is_reported_even_if_every_record_exists(tmp_path, inprocess_runner, local_runner):
    path, _ = record(tmp_path, inprocess_runner, local_runner)
    manifest = bundle.load_manifest(path)
    manifest["status"] = "in_progress"
    (path / "manifest.json").write_text(json.dumps(manifest))

    assert [p.kind for p in verify_bundle(path).problems] == ["run_not_finalized"]


def test_infrastructure_stop_marks_run_incomplete_with_planned_denominator(tmp_path, inprocess_runner, local_runner):
    path, result = record(tmp_path, inprocess_runner, local_runner, "transport_exhausted_on_call_2", trials=1)

    assert not result.complete and len(result.planned) == 1
    assert [p.kind for p in result.problems] == ["infrastructure_stop"]
    assert bundle.load_manifest(path)["status"] == "incomplete"
    assert load_trial(path, "strings_01-t1")["infrastructure_status"] == "transport_exhausted"


# --- secrets ---------------------------------------------------------------------------------

def test_fake_key_and_headers_never_reach_the_bundle(tmp_path, monkeypatch, inprocess_runner, local_runner):
    key = "sk-or-FAKE-KEY-0123456789"
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    leaky = FixtureClient([ModelResponse(
        content=f"def count_vowels(text: str) -> int:\n    return 0  # {key}\n",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "authorization": f"Bearer {key}",
               "note": key})])

    path, _ = run_recorded([TASK], lambda t, i: leaky, BENCHMARK, bundle_root=tmp_path,
                           run_id="run-s", runner=inprocess_runner)

    text = "".join(f.read_text() for f in path.rglob("*.json"))
    assert key not in text and bundle.REDACTED in text
    trial = load_trial(path, "strings_01-t1")
    assert trial["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert "authorization" not in json.dumps(trial["responses"]).lower()


def test_sanitizers_drop_everything_outside_the_allowlist():
    request = bundle.sanitize_request({"messages": [{"role": "user", "content": "hi", "x": 1}],
                                       "tools": [], "tool_choice": "auto",
                                       "headers": {"Authorization": "Bearer abc"}})
    response = bundle.sanitize_response({"content": "ok", "api_key": "k", "usage": {"a": 1, "b": "t"}})

    assert request == {"messages": [{"role": "user", "content": "hi"}], "tools": [], "tool_choice": "auto"}
    assert response == {"content": "ok", "usage": {"a": 1}}


def test_redaction_works_on_values_so_numbers_and_escapes_stay_valid(tmp_path):
    tricky = 'p"w\\x-secret-1'
    writer = bundle.BundleWriter(tmp_path, "run-r", [{"task_id": "t", "trial_id": "t-t1"}], {},
                                 extra_secrets=["10000000", tricky])
    writer.write_trial({"trial_id": "t-t1", "task_id": "t", "usage": {"prompt_tokens": 10000000},
                        "messages": [{"content": f"key {tricky} and 10000000"}]})

    record = json.loads((tmp_path / "run-r" / "trials" / "t-t1.json").read_text())
    assert record["usage"] == {"prompt_tokens": 10000000}  # a number is never rewritten
    assert record["messages"][0]["content"] == "key [REDACTED] and [REDACTED]"
    manifest = bundle.load_manifest(tmp_path / "run-r")
    assert manifest["redactions"] == 2 and writer.finish().missing() == ()


def test_secret_name_pattern_is_anchored_and_skips_non_secrets(monkeypatch):
    for name in ("SSH_AUTH_SOCK", "GIT_CONFIG_KEY_0", "MY_TOKEN_LIMIT", "SECRETARY_NAME_X"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SSH_AUTH_SOCK", "/private/tmp/agent.sock-123")
    monkeypatch.setenv("MY_TOKEN_LIMIT", "10000000")
    monkeypatch.setenv("SERVICE_API_KEY", "abcdefgh-key-value")
    monkeypatch.setenv("DB_PASSWORD", "hunter2hunter2")
    values = bundle.secret_values()

    assert "abcdefgh-key-value" in values and "hunter2hunter2" in values
    assert "/private/tmp/agent.sock-123" not in values and "10000000" not in values


def test_incremental_call_log_keeps_paid_responses_when_a_trial_crashes(tmp_path, inprocess_runner):
    class Crashing(FixtureClient):
        def complete(self, request):
            if len(self.requests) == 1:  # the second call dies after the first was paid for
                self.requests.append(request)
                raise KeyboardInterrupt
            return super().complete(request)

    with pytest.raises(KeyboardInterrupt):
        run_recorded([TASK], lambda t, i: Crashing.from_data(SCENARIOS["tool_use_and_revision"]),
                     BENCHMARK, bundle_root=tmp_path, run_id="run-c", runner=inprocess_runner)

    path = tmp_path / "run-c"
    entries = bundle.load_partial_calls(path, "strings_01-t1")
    assert [(e["event"], e["call"]) for e in entries] == [
        ("request", 1), ("response", 1), ("request", 2), ("error", 2)]
    assert entries[1]["response"]["tool_calls"][0]["name"] == "run_checks"
    result = verify_bundle(path)
    assert result.missing() == ("strings_01-t1",)
    missing = next(p for p in result.problems if p.kind == "missing_record")
    assert "4 request/response entries retained" in missing.detail
    shown = subprocess.run([sys.executable, "-m", "codegen_eval.trace_inspect", "--bundles",
                            str(tmp_path), "show", "run-c"], env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                           capture_output=True, text=True)
    assert "NO RECORD; 4 partial entries retained" in shown.stdout


def test_evaluator_revision_marks_untracked_and_modified_source_dirty(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    clean = bundle.evaluator_revision(tmp_path)
    assert len(clean) == 40 and not clean.endswith("+dirty")

    (tmp_path / "src" / "new_module.py").write_text("y = 2\n")  # untracked code that would run
    assert bundle.evaluator_revision(tmp_path) == clean + "+dirty"
    (tmp_path / "src" / "new_module.py").unlink()
    (tmp_path / "src" / "a.py").write_text("x = 2\n")
    assert bundle.evaluator_revision(tmp_path) == clean + "+dirty"
    assert bundle.evaluator_revision(tmp_path / "missing") == "unknown"


def test_atomic_write_syncs_the_directory(tmp_path, monkeypatch):
    synced = []
    monkeypatch.setattr(bundle, "_fsync_directory", synced.append)
    bundle.atomic_write(tmp_path / "d" / "f.json", b"{}")

    assert synced == [tmp_path / "d"]


def test_bundle_storage_is_ignored_by_git():
    paths = [f"{bundle.DEFAULT_BUNDLE_ROOT}/run-x/manifest.json",
             f"{bundle.DEFAULT_BUNDLE_ROOT}/run-x/trials/t.json"]
    result = subprocess.run(["git", "check-ignore", *paths], cwd=ROOT, capture_output=True, text=True)
    assert result.stdout.split() == paths


# --- tampering and completeness ---------------------------------------------------------------

@pytest.fixture
def good(tmp_path, inprocess_runner, local_runner):
    return record(tmp_path, inprocess_runner, local_runner)[0]


def kinds(path):
    return sorted(p.kind for p in verify_bundle(path).problems)


def test_untouched_bundle_verifies(good):
    assert verify_bundle(good).complete


def test_edited_record_is_detected(good):
    file = good / "trials" / "strings_01-t1.json"
    data = json.loads(file.read_text())
    data["grades"]["passed"] = False
    file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    result = verify_bundle(good)
    assert kinds(good) == ["tampered_record"] and result.problems[0].trial_id == "strings_01-t1"
    assert result.recorded == ("strings_01-t2",)


def test_deleted_record_is_reported_as_missing_trial(good):
    (good / "trials" / "strings_01-t2.json").unlink()

    result = verify_bundle(good)
    assert kinds(good) == ["missing_record"] and result.missing() == ("strings_01-t2",)


def test_unplanned_extra_record_is_detected(good):
    (good / "trials" / "extra-t9.json").write_text("{}")
    assert kinds(good) == ["unexpected_record"]


def test_record_swapped_between_trials_is_detected(good):
    one, two = (good / "trials" / f"strings_01-t{n}.json" for n in (1, 2))
    one.write_text(two.read_text())
    assert kinds(good) == ["tampered_record"]


def test_rewritten_record_and_hash_with_wrong_identity_is_detected(good):
    file = good / "trials" / "strings_01-t1.json"
    data = json.loads(file.read_text())
    data["task_id"] = "lists_01"
    raw = (json.dumps(data, sort_keys=True) + "\n").encode()
    file.write_bytes(raw)
    manifest = bundle.load_manifest(good)
    manifest["records"]["strings_01-t1"] = bundle.sha256_bytes(raw)
    (good / "manifest.json").write_text(json.dumps(manifest))

    assert kinds(good) == ["identity_mismatch"]


def good_grades(**changes):
    check = {"id": "c", "kind": "edge", "executed": True, "passed": True, "failures": [], "actual": 1}
    grades = {"status": "graded", "trial_status": "submitted", "labels": [], "success": True,
              "incomplete": False, "infrastructure_status": None, "checks": [check]}
    return {**grades, **changes}


def test_malformed_check_outcomes_are_rejected():
    assert bundle.check_grades(good_grades()) is None
    assert bundle.check_grades(bundle.PENDING_GRADES) is None
    failing = {"id": "c", "kind": "edge", "executed": True, "passed": False,
               "failures": ["wrong_answer"], "actual": 2}
    assert bundle.check_grades(good_grades(success=False, labels=["wrong_answer"], checks=[failing])) is None
    for bad in (
            good_grades(checks=[{**failing, "passed": True}]),                  # passed with a failure
            good_grades(success=False, checks=[{**failing, "failures": []}]),   # failed with no label
            good_grades(success=False, checks=[{**failing, "failures": [""]}]),
            good_grades(checks=[{**failing, "passed": "yes"}]),
            good_grades(checks=[failing]),                                       # success with a failure
            good_grades(checks=[]), good_grades(labels="x"), good_grades(incomplete=True),
            good_grades(status="maybe"),
            good_grades(checks=[good_grades()["checks"][0]] * 2)):               # duplicate ids
        assert bundle.check_grades(bad), bad


def test_infrastructure_labels_require_an_unexecuted_check_in_an_incomplete_trial():
    infra = {"id": "c", "kind": "edge", "executed": False, "passed": False,
             "failures": ["protocol_error"], "actual": None}
    incomplete = good_grades(status="incomplete", success=False, incomplete=True,
                             infrastructure_status="protocol_error", labels=["protocol_error"],
                             checks=[infra])
    assert bundle.check_grades(incomplete) is None
    assert bundle.check_grades({**incomplete, "status": "graded", "incomplete": False})
    assert bundle.check_grades({**incomplete, "checks": [{**infra, "executed": True}]})
    assert bundle.check_grades({**incomplete, "infrastructure_status": None})


def test_infrastructure_labels_match_the_sandbox_vocabulary():
    assert bundle.INFRASTRUCTURE_FAILURES == sandbox.INFRASTRUCTURE_STATUSES

def test_trial_level_grades_from_part_b_are_stored_and_valid(tmp_path, inprocess_runner, local_runner):
    """no_submission (with its reason) and infrastructure_incomplete trials are graded by
    grade_trial too; the bundle stores them without a placeholder and validates them."""
    expected = {
        "no_final_message": ("no_submission", ["no_submission", "no_final_message"], False),
        "request_rejected_on_call_3": ("no_submission", ["no_submission", "request_rejected"], False),
        "fenced_final_source": ("submitted", ["contract_error"], False),
        "transport_exhausted_on_call_2": ("infrastructure_incomplete", [], True),
    }
    for name, (status, labels, incomplete) in expected.items():
        path, result = record(tmp_path, inprocess_runner, local_runner, name, trials=1, run_id=f"run-{name}")
        grades = load_trial(path, "strings_01-t1")["grades"]
        assert grades["trial_status"] == status and grades["labels"] == labels, name
        assert grades["incomplete"] is incomplete and len(grades["checks"]) == 4, name
        assert all(not c["executed"] for c in grades["checks"]), name
        assert bundle.check_grades(grades) is None, name
        assert [p.kind for p in result.problems] == (["infrastructure_stop"] if incomplete else []), name
    assert grades["status"] == "incomplete" and grades["infrastructure_status"] == "transport_exhausted"


def test_grades_checks_keep_the_part_b_names_and_actual_values(tmp_path, inprocess_runner, local_runner):
    path, _ = record(tmp_path, inprocess_runner, local_runner, trials=1)
    checks = load_trial(path, "strings_01-t1")["grades"]["checks"]

    assert set(checks[0]) == {"id", "kind", "executed", "passed", "failures", "actual"}
    assert checks[0]["actual"] is not None


def test_invalid_and_infrastructure_check_outcomes_flag_the_run(tmp_path, inprocess_runner):
    def grader(infra_executed):
        def grade(task, result):
            cases = tuple(CaseResult(c.id, c.kind, infra_executed, False, ("protocol_error",))
                          for c in task.cases)
            return TrialGrade(task.id, task.category, "submitted", ("protocol_error",), False,
                              True, "protocol_error", cases)
        return grade

    _, result = run_recorded([TASK], scenario_client("early_submission"), BENCHMARK, bundle_root=tmp_path,
                             run_id="run-g", runner=inprocess_runner, grader=grader(True))
    assert [p.kind for p in result.problems] == ["invalid_grade"]  # infrastructure yet "executed"

    _, result = run_recorded([TASK], scenario_client("early_submission"), BENCHMARK, bundle_root=tmp_path,
                             run_id="run-h", runner=inprocess_runner, grader=grader(False))
    assert [p.kind for p in result.problems] == ["infrastructure_stop"]

def test_unknown_schema_version_and_unreadable_manifest(good):
    manifest = bundle.load_manifest(good)
    manifest["schema_version"] = 99
    (good / "manifest.json").write_text(json.dumps(manifest))
    assert kinds(good) == ["unsupported_schema"]
    (good / "manifest.json").write_text("{not json")
    assert kinds(good) == ["unreadable_manifest"]


def test_malformed_manifest_shape_is_reported_not_raised(good):
    original = bundle.load_manifest(good)
    for change in ({"planned": [{"trial_id": "x"}]}, {"planned": []}, {"planned": "no"},
                   {"records": []}, {"identity": None}, {"run_id": 7}):
        (good / "manifest.json").write_text(json.dumps({**original, **change}))
        assert kinds(good) == ["unreadable_manifest"], change


def test_record_the_manifest_never_accepted_is_unrecorded_not_tampered(good):
    manifest = bundle.load_manifest(good)
    del manifest["records"]["strings_01-t2"]  # as after a crash between the two writes
    (good / "manifest.json").write_text(json.dumps(manifest))

    result = verify_bundle(good)
    assert kinds(good) == ["unrecorded_record"]
    assert result.recorded == ("strings_01-t1",)
    with pytest.raises(BundleError, match="unrecorded_record"):
        replay_bundle(good, BENCHMARK)

def test_writer_refuses_to_overwrite_an_existing_bundle_and_unplanned_trials(tmp_path):
    plan = [{"task_id": "t", "trial_id": "t-t1"}]
    writer = bundle.BundleWriter(tmp_path, "run-w", plan, {})
    with pytest.raises(BundleError):
        bundle.BundleWriter(tmp_path, "run-w", plan, {})
    with pytest.raises(BundleError):
        writer.write_trial({"trial_id": "other", "task_id": "t"})
    with pytest.raises(BundleError):
        bundle.BundleWriter(tmp_path, "../escape", plan, {})


def test_writes_leave_no_temporary_files(good):
    assert not list(good.rglob(".*.tmp"))


# --- offline inspection ------------------------------------------------------------------------

def run_offline(args, tmp_path, extra_env=None):
    """Run the inspector with no podman on PATH, process spawning disabled, and a guard that
    fails if the model client, sandbox, or evaluator are imported."""
    guard = (
        "import sys, subprocess, runpy\n"
        "def boom(*a, **k): raise AssertionError('process spawn attempted')\n"
        "subprocess.Popen = boom\n"
        "try:\n"
        "    runpy.run_module('codegen_eval.trace_inspect', run_name='__main__', alter_sys=True)\n"
        "except SystemExit as e:\n"
        "    code = e.code or 0\n"
        "else:\n"
        "    code = 0\n"
        "bad = [m for m in ('codegen_eval.sandbox', 'codegen_eval.model_client',\n"
        "                   'codegen_eval.evaluate', 'codegen_eval.trial') if m in sys.modules]\n"
        "assert not bad, bad\n"
        "sys.exit(code)\n")
    env = {"PATH": str(tmp_path / "empty"), "PYTHONPATH": str(ROOT / "src"), **(extra_env or {})}
    return subprocess.run([sys.executable, "-c", guard, *args], env=env, cwd=tmp_path,
                          capture_output=True, text=True)


def test_inspection_works_with_no_podman_network_or_client(good, tmp_path):
    result = run_offline(["--bundles", str(good.parent), "show", good.name, "--trial", "strings_01-t1"],
                         tmp_path)

    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "COMPLETE" in out and "baseline_agent_v1" in out
    assert "final source:" in out and "def count_vowels" in out
    assert "grades: graded" in out and "pass" in out


def test_inspection_shows_tool_feedback_for_a_tool_run(tmp_path, inprocess_runner, local_runner):
    path, _ = record(tmp_path / "b", inprocess_runner, local_runner, "tool_use_and_revision", trials=1)
    result = run_offline(["--bundles", str(path.parent), "show", path.name], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "run_checks" in result.stdout and "candidate draft from tool attempt 2" in result.stdout
    assert "tool_call_id" not in result.stdout and "(reply to t1)" in result.stdout


def test_inspect_verify_exits_nonzero_for_incomplete_and_tampered_bundles(good, tmp_path):
    assert run_offline(["--bundles", str(good.parent), "verify", good.name], tmp_path).returncode == 0
    (good / "trials" / "strings_01-t2.json").unlink()
    (good / "trials" / "strings_01-t1.json").write_text("{}")

    result = run_offline(["--bundles", str(good.parent), "verify", good.name], tmp_path)
    assert result.returncode == 1
    assert "INCOMPLETE" in result.stdout and "missing_record [strings_01-t2]" in result.stdout
    assert "tampered_record [strings_01-t1]" in result.stdout


def test_inspect_list_and_unknown_run(good, tmp_path):
    listing = run_offline(["--bundles", str(good.parent), "list"], tmp_path)
    assert good.name in listing.stdout and "2/2 trials" in listing.stdout
    assert run_offline(["--bundles", str(good.parent), "show", "nope"], tmp_path).returncode == 2


# --- grading replay ----------------------------------------------------------------------------

def test_replay_regrades_saved_candidates_as_separate_linked_evidence(good, local_runner, monkeypatch):
    for name in ("OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    before = {f: f.read_bytes() for f in good.rglob("*.json")}

    path, evidence = replay_bundle(good, BENCHMARK, runner=local_runner)

    assert path.parent == good / "replays" and evidence["kind"] == "grading_replay"
    assert "No model was called" in evidence["note"] and "no agent trial was reproduced" in evidence["note"]
    assert evidence["run_id"] == "run-a" and evidence["linked_manifest_sha256"] == \
        bundle.sha256_file(good / "manifest.json")
    assert evidence["summary"] == {"regraded": 2, "compared": 2, "mismatched": 0, "incomplete": 0}
    assert evidence["benchmark_freeze_content_hash"] == FREEZE["content_hash"]
    assert evidence["original_problems"] == [] and set(evidence["environment_differences"]) <= {
        "container_image", "evaluator_revision", "evaluator_source_sha256", "execution_limits_hash"}
    assert evidence["benchmark_sha256"] == bundle.sha256_file(BENCHMARK)
    assert {f: f.read_bytes() for f in good.rglob("*.json") if f != path} == before  # originals untouched
    assert verify_bundle(good).complete  # replay evidence does not disturb the bundle


def test_replay_reports_a_mismatch_with_the_original_grades(tmp_path, inprocess_runner, local_runner):
    def lying_grader(task, result):  # original grading claims every case failed
        cases = tuple(CaseResult(c.id, c.kind, True, False, ("wrong_answer",)) for c in task.cases)
        return TrialGrade(task.id, task.category, "submitted", ("wrong_answer",), False, False, None, cases)

    path, _ = run_recorded([TASK], scenario_client("early_submission"), BENCHMARK, bundle_root=tmp_path,
                           run_id="run-m", trials_per_task=1, runner=inprocess_runner, grader=lying_grader)
    _, evidence = replay_bundle(path, BENCHMARK, runner=local_runner)

    assert evidence["summary"]["mismatched"] == 1
    assert len(evidence["trials"][0]["mismatches"]) == 2  # the two cases the candidate truly passes
    assert load_trial(path, "strings_01-t1")["grades"]["success"] is False  # original kept


def test_replay_regrades_trial_level_outcomes_without_executing_anything(tmp_path, inprocess_runner, local_runner):
    path, _ = record(tmp_path, inprocess_runner, local_runner, "request_rejected_on_call_3", trials=1,
                     grade=False, run_id="run-n")
    _, evidence = replay_bundle(path, BENCHMARK, runner=local_runner)

    trial = evidence["trials"][0]
    assert trial["original"].startswith("pending") and trial["grades"]["labels"] == [
        "no_submission", "request_rejected"]
    assert all(not c["executed"] for c in trial["grades"]["checks"])
    assert evidence["summary"]["regraded"] == 1 and evidence["summary"]["compared"] == 0


def test_replay_compares_trial_level_grades_and_flags_infrastructure_incomplete(tmp_path, inprocess_runner, local_runner):
    path, _ = record(tmp_path, inprocess_runner, local_runner, "transport_exhausted_on_call_2", trials=1)
    _, evidence = replay_bundle(path, BENCHMARK, runner=local_runner)

    assert evidence["summary"] == {"regraded": 1, "compared": 1, "mismatched": 0, "incomplete": 1}
    assert "infrastructure_stop" in [p["kind"] for p in evidence["original_problems"]]


def test_replay_grades_a_contract_invalid_submission_without_running_it(tmp_path, inprocess_runner, local_runner):
    path, _ = run_recorded([TASK], scenario_client("fenced_final_source"), BENCHMARK, bundle_root=tmp_path,
                           run_id="run-f", runner=inprocess_runner)
    _, evidence = replay_bundle(path, BENCHMARK, runner=local_runner)

    checks = evidence["trials"][0]["grades"]["checks"]
    assert len(checks) == 4 and all(c["failures"] == ["contract_error"] and not c["executed"] for c in checks)


def test_replay_refuses_a_benchmark_that_differs_from_the_recorded_hash(good, tmp_path, local_runner):
    other = tmp_path / "benchmark_v1.json"
    other.write_text(BENCHMARK.read_text() + "\n")

    with pytest.raises(BundleError, match="benchmark mismatch"):
        replay_bundle(good, other, runner=local_runner)
    assert not (good / "replays").exists()


def test_replay_refuses_a_tampered_bundle_but_replays_survivors_of_an_incomplete_one(good, local_runner):
    (good / "trials" / "strings_01-t2.json").unlink()
    _, evidence = replay_bundle(good, BENCHMARK, runner=local_runner)
    assert evidence["missing_original_records"] == ["strings_01-t2"] and not evidence["original_run_complete"]

    (good / "trials" / "strings_01-t1.json").write_text("{}")
    with pytest.raises(BundleError, match="tampered_record"):
        replay_bundle(good, BENCHMARK, runner=local_runner)


def test_replay_makes_no_network_call_and_never_stores_the_key(good, tmp_path):
    """Run replay in a fresh interpreter with a sentinel key in the environment, every
    socket connection trapped, and the recording/API-facing modules asserted unimported.
    (Replay reads environment values only to redact them from its evidence.)"""
    sentinel = "sk-or-SENTINEL-0123456789"
    script = (
        "import sys, socket\n"
        "def no_net(*a, **k): raise AssertionError('network used')\n"
        "socket.socket.connect = no_net\n"
        "socket.socket.connect_ex = no_net\n"
        "from codegen_eval.replay import replay_bundle\n"
        "def runner(source, task, case):\n"
        "    from codegen_eval.sandbox import ExecutionResult\n"
        "    ns = {}\n"
        "    exec(compile(source, 'c', 'exec'), ns)\n"
        "    args = list(case.args)\n"
        "    return ExecutionResult('returned', value=ns[task.function_name](*args), args_after=args)\n"
        f"path, evidence = replay_bundle({str(good)!r}, {str(BENCHMARK)!r}, runner=runner)\n"
        "bad = [m for m in ('codegen_eval.run_recording', 'urllib.request', 'http.client', 'ssl')\n"
        "       if m in sys.modules]\n"
        "assert not bad, bad\n"
        "print(path)\n")
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src"),
                                 "OPENROUTER_API_KEY": sentinel})

    assert result.returncode == 0, result.stderr
    evidence = Path(result.stdout.strip()).read_text()
    assert sentinel not in evidence


def test_replay_refuses_a_matching_benchmark_whose_freeze_differs(good, tmp_path, local_runner):
    """Same benchmark file, but the references/review it was frozen with are missing."""
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "data" / "benchmark_v1.json").write_bytes(BENCHMARK.read_bytes())

    with pytest.raises(BundleError, match="benchmark freeze mismatch"):
        replay_bundle(good, root / "data" / "benchmark_v1.json", runner=local_runner)


@pytest.mark.sandbox
@pytest.mark.skipif(os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="requires a running local Podman VM")
def test_replay_regrades_known_candidates_in_podman(tmp_path, inprocess_runner, local_runner):
    path, _ = record(tmp_path, inprocess_runner, local_runner, trials=1, run_id="run-p")
    _, evidence = replay_bundle(path, BENCHMARK)  # real container runner

    trial = evidence["trials"][0]
    assert evidence["summary"] == {"regraded": 1, "compared": 1, "mismatched": 0, "incomplete": 0}
    original = load_trial(path, "strings_01-t1")["grades"]["checks"]
    assert trial["grades"]["checks"] == original  # same per-check outcomes through Podman
    assert all(c["executed"] for c in original) and not trial["grades"]["incomplete"]
