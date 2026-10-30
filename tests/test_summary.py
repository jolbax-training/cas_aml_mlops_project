"""Fixed-denominator summaries and incomplete-run classification over recorded bundles.
Completeness itself is `verify_bundle`'s (tested in test_run_bundle); these tests check that
summaries consume it and classify its problems."""

import json
from pathlib import Path

import pytest

from codegen_eval import bundle
from codegen_eval.bundle import Verification, verify_bundle
from codegen_eval.evaluate import CaseResult, TrialGrade, count_results
from codegen_eval.model_client import FixtureClient, load_fixtures
from codegen_eval.replay import make_grader
from codegen_eval.run_recording import run_recorded
from codegen_eval.summary import (
    EXHAUSTED_TRANSPORT,
    FAILED_COMPLETENESS,
    INFRASTRUCTURE,
    classify_run,
    summarize_bundle,
)
from codegen_eval.tasks import load_benchmark

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "benchmark_v1.json"
SCENARIOS = load_fixtures(ROOT / "tests" / "fixtures" / "agent" / "trials.json")
TASK = load_benchmark(BENCHMARK)[0]


@pytest.fixture
def local_runner(inprocess_runner):
    return lambda source, task, case: inprocess_runner(source, task.function_name, case.args)


def record(tmp_path, inprocess_runner, local_runner, name="early_submission", *, trials=2, run_id="run-a"):
    path, result = run_recorded(
        [TASK], lambda task, trial_id: FixtureClient.from_data(SCENARIOS[name]), BENCHMARK,
        bundle_root=tmp_path, run_id=run_id, trials_per_task=trials, runner=inprocess_runner,
        grader=make_grader(local_runner), model_settings={"client": "fixture", "scenario": name})
    return path


def test_complete_run_is_headline_eligible_with_counts_and_rates(tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner)
    summary = summarize_bundle(path, BENCHMARK)

    assert summary.classification.complete and summary.classification.classes == ()
    assert summary.headline_eligible
    assert (summary.trials_planned, summary.counts.tasks_total, summary.counts.cases_total) == (2, 2, 8)
    # The early-submission fixture passes two of the four checks per trial.
    assert summary.counts.tasks_passed == summary.trials_succeeded == 0
    assert (summary.counts.cases_passed, summary.counts.cases_executed) == (4, 8)
    assert summary.counts.case_pass_rate == 0.5 and summary.trial_success_rate == 0.0
    assert summary.categories == {TASK.category: (0, 2)}
    assert summary.counts.complete_for(summary.classification.verification)


def test_exhausted_transport_makes_the_run_incomplete_and_keeps_planned_denominators(
        tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner, "transport_exhausted_on_call_2", trials=2)
    summary = summarize_bundle(path, BENCHMARK)

    # Both trials are recorded as infrastructure stops; the finalized manifest says
    # `incomplete`, so verify_bundle also reports run_not_finalized, which is implied.
    assert "run_not_finalized" in [p.kind for p in summary.classification.verification.problems]
    assert summary.classification.classes == (EXHAUSTED_TRANSPORT,)
    assert summary.classification.infrastructure_statuses == ("transport_exhausted",)
    assert not summary.headline_eligible
    assert (summary.counts.tasks_total, summary.counts.cases_total, summary.counts.cases_executed) == (2, 8, 0)
    assert summary.trials_incomplete == 2 and summary.counts.tasks_incomplete == 2
    assert summary.counts.tasks_passed == 0 and summary.counts.case_pass_rate == 0.0
    assert not summary.counts.complete_for(summary.classification.verification)


def test_infrastructure_status_is_classified_apart_from_transport(tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner, trials=1)
    manifest = bundle.load_manifest(path)
    # A checks-level infrastructure outcome in a stored, valid grade record.
    trial = bundle.load_trial(path, "strings_01-t1")
    trial["grades"] = {**trial["grades"], "status": "incomplete", "incomplete": True, "success": False,
                       "infrastructure_status": "infrastructure_error",
                       "checks": [{"id": c["id"], "kind": c["kind"], "executed": False, "passed": False,
                                   "failures": ["infrastructure_error"], "actual": None}
                                  for c in trial["grades"]["checks"]]}
    rewrite(path, manifest, "strings_01-t1", trial)

    classification = classify_run(path)
    assert classification.classes == (INFRASTRUCTURE,)
    assert classification.infrastructure_statuses == ("infrastructure_error",)


def rewrite(path, manifest, trial_id, record):
    """Replace a record and its manifest hash, as the writer would (test setup only)."""
    data = bundle._canonical(record)
    (path / "trials" / f"{trial_id}.json").write_bytes(data)
    manifest["records"][trial_id] = bundle.sha256_bytes(data)
    (path / "manifest.json").write_bytes(bundle._canonical(manifest))


def test_failed_completeness_covers_missing_and_tampered_records_without_shrinking_denominators(
        tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner)
    (path / "trials" / "strings_01-t2.json").unlink()
    summary = summarize_bundle(path, BENCHMARK)

    assert summary.classification.classes == (FAILED_COMPLETENESS,)
    assert not summary.headline_eligible
    assert (summary.trials_planned, summary.counts.tasks_total, summary.counts.cases_total) == (2, 2, 8)
    assert summary.trials_incomplete == summary.counts.tasks_incomplete == 1
    assert (summary.counts.cases_passed, summary.counts.cases_executed) == (2, 4)
    assert summary.counts.case_pass_rate == 0.25


def test_pending_grades_keep_the_run_evidence_verdict_but_are_not_headline_eligible(tmp_path, inprocess_runner):
    path, _ = run_recorded([TASK], lambda t, i: FixtureClient.from_data(SCENARIOS["early_submission"]),
                           BENCHMARK, bundle_root=tmp_path, run_id="run-p", runner=inprocess_runner)
    summary = summarize_bundle(path, BENCHMARK)

    assert summary.classification.complete and summary.classification.classes == ()
    assert not summary.classification.headline_eligible and not summary.headline_eligible
    assert not summary.counts.complete_for(summary.classification.verification)
    assert summary.counts.cases_executed == 0 and summary.counts.cases_total == 4
    assert (summary.trials_ungraded, summary.trials_incomplete, summary.trials_succeeded) == (1, 0, 0)


def test_summary_takes_its_verdict_from_verify_bundle(tmp_path, inprocess_runner, local_runner, monkeypatch):
    """A stubbed verification with a problem makes the run incomplete without any file edit."""
    path = record(tmp_path, inprocess_runner, local_runner, trials=1)
    import codegen_eval.summary as summary_module
    real = verify_bundle(path)
    stub = Verification(real.run_id, (bundle.Problem(bundle.TAMPERED_RECORD, "stub", "strings_01-t1"),),
                        real.planned, real.recorded, real.grades_pending, real.bundle_digest)
    monkeypatch.setattr(summary_module, "verify_bundle", lambda p, **kw: stub)
    summary = summarize_bundle(path, BENCHMARK)

    assert summary.classification.classes == (FAILED_COMPLETENESS,) and not summary.headline_eligible
    assert summary.counts.cases_executed == 0 and summary.trials_succeeded == 0  # stored grade not trusted


def invalid_grade_edit(path, trial_id, change):
    manifest = bundle.load_manifest(path)
    trial = bundle.load_trial(path, trial_id)
    trial["grades"] = change(trial["grades"])
    rewrite(path, manifest, trial_id, trial)


def test_a_rejected_grade_is_never_trusted(tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner, trials=2)
    invalid_grade_edit(path, "strings_01-t1", lambda g: {**g, "success": True})  # success with failing checks
    invalid_grade_edit(path, "strings_01-t2", lambda g: {**g, "checks": [{"id": "x"}]})  # malformed
    assert {p.kind for p in verify_bundle(path).problems} == {"invalid_grade"}

    summary = summarize_bundle(path, BENCHMARK)
    assert summary.classification.classes == (FAILED_COMPLETENESS,)
    assert (summary.trials_succeeded, summary.counts.tasks_passed) == (0, 0)
    assert (summary.counts.cases_total, summary.counts.cases_executed) == (8, 0)
    assert summary.trials_incomplete == 2 and not summary.headline_eligible


def test_stored_incomplete_grades_keep_their_per_check_evidence(tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner, trials=1)

    def mixed(grades):
        checks = [dict(c) for c in grades["checks"]]
        checks[3] = {**checks[3], "executed": False, "passed": False, "failures": ["infrastructure_error"]}
        return {**grades, "status": "incomplete", "incomplete": True, "success": False,
                "infrastructure_status": "infrastructure_error", "checks": checks}

    invalid_grade_edit(path, "strings_01-t1", mixed)
    summary = summarize_bundle(path, BENCHMARK)

    assert summary.classification.classes == (INFRASTRUCTURE,)
    assert summary.counts.infrastructure_failures == 1  # one real check, not all four
    assert (summary.counts.cases_total, summary.counts.cases_executed) == (4, 3)
    assert summary.trials_incomplete == 1 and not summary.headline_eligible


def test_a_finalized_run_with_an_infrastructure_check_failure_is_infrastructure_only(tmp_path, inprocess_runner):
    def grade(task, result):
        cases = tuple(CaseResult(c.id, c.kind, False, False, ("protocol_error",)) for c in task.cases)
        return TrialGrade(task.id, task.category, "submitted", ("protocol_error",), False, True,
                          "protocol_error", cases)

    path, _ = run_recorded([TASK], lambda t, i: FixtureClient.from_data(SCENARIOS["early_submission"]),
                           BENCHMARK, bundle_root=tmp_path, run_id="run-i", runner=inprocess_runner, grader=grade)
    assert bundle.load_manifest(path)["status"] == "incomplete"
    assert classify_run(path).classes == (INFRASTRUCTURE,)


def test_a_crashed_run_is_failed_completeness_only_when_nothing_else_explains_it(tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner, trials=1)
    manifest = bundle.load_manifest(path)
    manifest["status"] = "in_progress"
    (path / "manifest.json").write_bytes(bundle._canonical(manifest))

    assert classify_run(path).classes == (FAILED_COMPLETENESS,)


def test_summary_refuses_a_benchmark_the_bundle_did_not_record(tmp_path, inprocess_runner, local_runner):
    path = record(tmp_path, inprocess_runner, local_runner, trials=1)
    other = tmp_path / "other.json"
    other.write_text(BENCHMARK.read_text().replace("strings_01", "strings_xx"))

    with pytest.raises(bundle.BundleError, match="benchmark mismatch"):
        summarize_bundle(path, other)


def test_complete_for_requires_the_record_level_verdict_and_matching_trial_count():
    from codegen_eval.bundle import MISSING_RECORD, Problem
    good = count_results([])
    assert good.complete_for(Verification("r", (), (), ())) is True
    broken = Verification("r", (Problem(MISSING_RECORD, "gone", "t1"),), ("t1",), ())
    assert good.complete_for(broken) is False
    assert good.complete_for(Verification("r", (), ("t1",), ("t1",))) is False  # counts cover no trial
