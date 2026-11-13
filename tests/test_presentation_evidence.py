import builtins
import json
import pathlib
import re
import subprocess
import sys

import pytest

from presentation_support import FIXTURE, REPO, SCRIPTS, copy_repo, load_script

pe = load_script("presentation_evidence")


@pytest.fixture(scope="module")
def summary():
    return pe.load_summary(REPO)


def rewrite_summary(root, change):
    path = root / pe.SUMMARY_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(pe.canonical(data), encoding="utf-8")


def test_committed_evidence_passes_the_offline_check():
    assert pe.check_all(REPO) == []


def test_offline_check_command_exits_zero(capsys):
    assert pe.main(["check"]) == 0
    assert "passed (offline)" in capsys.readouterr().out


def test_bundle_sections_are_assembled_from_the_fixture(summary):
    live = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fresh = pe.assemble(live, REPO, script_sha=summary["provenance"]["generated_by"]["sha256"])
    for key in pe.BUNDLE_SECTIONS:
        assert fresh[key] == summary[key]
    assert fresh["provenance"]["runs"] == summary["provenance"]["runs"]


def test_summary_holds_no_absolute_path_and_relative_bundles(summary):
    text = (REPO / pe.SUMMARY_REL).read_text(encoding="utf-8")
    assert "/Users/" not in text and str(pathlib.Path.home()) not in text
    for variant in pe.VARIANTS:
        assert summary["provenance"]["runs"][variant]["bundle"].startswith("run_bundles/")


def test_summary_carries_all_limits_and_the_non_claim(summary):
    assert len(summary["limits"]["items"]) == 7
    assert "not a claim of improvement" in summary["limits"]["non_claim"]
    assert "not a measured improvement" in summary["limits"]["statement"]


def test_every_document_value_is_derived_from_its_quote(summary):
    for entry in summary["documents"]:
        assert entry["value"] == pe.extract_value(entry["quote"], entry["cell"], entry["pattern"],
                                                  entry["group"], entry["kind"])


def test_extract_value_kinds_and_errors():
    row = "| Model latency | 470,969 ms (15,699 ms) | 0.0027 |"
    assert pe.extract_value(row, 2, r"^([\d,]+) ms \(([\d,]+) ms\)$", 2, "int") == 15699
    assert pe.extract_value(row, 3, r"^([\d.]+)$", 1, "float") == 0.0027
    assert pe.extract_value(row, 1, r"^(\w+)", 1, "str") == "Model"
    with pytest.raises(pe.EvidenceError):
        pe.extract_value(row, 9, r"x", 1, "str")
    with pytest.raises(pe.EvidenceError):
        pe.extract_value(row, 1, r"^(\d+)$", 1, "int")


def test_find_quote_needs_exactly_one_line(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("| A | 1 |\n| A | 2 |\n| B | 3 |\n", encoding="utf-8")
    assert pe.find_quote(tmp_path, "docs/a.md", "| B", 1) == "| B | 3 |"
    with pytest.raises(pe.EvidenceError):
        pe.find_quote(tmp_path, "docs/a.md", "| A", 1)
    with pytest.raises(pe.EvidenceError):
        pe.find_quote(tmp_path, "docs/a.md", "| Z", 1)


def test_final_form_is_read_from_recorded_labels_only():
    assert pe.final_form({"labels": ["syntax_error"], "contract_issue_code": "syntax_error"}) == "prose before code"
    assert pe.final_form({"labels": ["contract_error"], "contract_issue_code": "contract_error"}) == "fenced reply"
    assert pe.final_form({"labels": ["wrong_answer"], "contract_issue_code": None}) == "bare function"
    assert pe.final_form({"labels": [], "contract_issue_code": None}) == "bare function"


def test_story_trial_reads_recorded_fields():
    record = {"trial_id": "t-1", "model_calls": 2, "tool_attempts": 1,
              "contract_issue": {"code": "contract_error"},
              "candidate_history": [{"result": {"ok": True, "checks": [{"passed": False}]}}],
              "grades": {"success": False, "labels": ["contract_error"],
                         "checks": [{"id": "c1", "actual": 3, "passed": False},
                                    {"id": "c2", "actual": 4, "passed": True}]}}
    trial = pe.story_trial(record)
    assert trial["dev_check_failed"] is True and trial["failed_checks"] == [{"id": "c1", "actual": 3}]
    assert trial["contract_issue_code"] == "contract_error" and trial["success"] is False


# --- tampering: each edit must fail the offline check ------------------------------------------

def test_a_value_edited_while_its_quote_stays_intact_fails(tmp_path):
    root = copy_repo(tmp_path)

    def change(data):
        entry = next(d for d in data["documents"] if d["field"] == "mlflow_run.baseline")
        entry["value"] = "0" * 32
    rewrite_summary(root, change)
    problems = pe.check_all(root)
    assert any("mlflow_run.baseline" in p and "quote" in p for p in problems)


def test_a_document_line_edited_fails_the_quote_check(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "docs" / "prompt_comparison.md"
    path.write_text(path.read_text(encoding="utf-8").replace("| 27/30 (90.0%) |", "| 26/30 (86.7%) |"),
                    encoding="utf-8")
    problems = pe.check_all(root)
    assert any("primary.baseline" in p for p in problems)


def test_a_summary_number_edited_fails_the_headline_cross_check(tmp_path):
    root = copy_repo(tmp_path)

    def change(data):
        data["comparison"]["baseline"]["primary"]["count"] = 28
        data["comparison"]["baseline"]["per_task"]["lists_02"]["succeeded"] = 1
    rewrite_summary(root, change)
    problems = pe.check_all(root)
    assert any("primary.baseline" in p and "summary has 28" in p for p in problems)


def test_impossible_counts_fail_the_arithmetic(tmp_path, summary):
    broken = json.loads(json.dumps(summary))
    broken["comparison"]["revised"]["hidden_checks"]["count"] = 121
    broken["efficiency"]["revised"]["tokens"]["total_tokens"] += 1
    problems = pe.check_arithmetic(broken)
    assert any("impossible" in p for p in problems) and any("token" in p for p in problems)


def test_structure_problems_are_named(summary):
    broken = json.loads(json.dumps(summary))
    del broken["comparison"]["baseline"]["primary"]
    broken["provenance"]["runs"]["revised"]["bundle"] = "/abs/path"
    problems = pe.validate_structure(broken)
    assert any("primary" in p for p in problems) and any("relative" in p for p in problems)


def test_a_stale_chart_fails(tmp_path):
    root = copy_repo(tmp_path)
    chart = root / pe.CHARTS_REL / "outcome-overview.svg"
    chart.write_text(chart.read_text(encoding="utf-8").replace("27/30", "28/30"), encoding="utf-8")
    assert any("outcome-overview.svg" in p for p in pe.check_all(root))


def test_a_stale_manifest_fails(tmp_path):
    root = copy_repo(tmp_path)
    path = root / pe.MANIFEST_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    data["title"]["author"] = "Someone Else"
    path.write_text(pe.canonical(data), encoding="utf-8")
    assert any("manifest" in p for p in pe.check_all(root))


def test_manifest_date_stays_empty_with_a_visible_placeholder():
    manifest = json.loads((REPO / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    assert manifest["title"]["date"] is None
    assert manifest["title"]["date_placeholder"] == "[DATE: fill in]"
    assert manifest["title"]["author"] == "Jose Luis Barahona"
    assert manifest["title"]["course"] == "CAS Applied Machine Learning (ZHAW)"
    manifest["title"]["date"] = "2026-11-20"
    assert any("date" in p for p in pe.check_manifest(manifest, REPO))


def test_manifest_paths_resolve_or_are_pending():
    manifest = json.loads((REPO / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    assert pe.check_manifest(manifest, REPO) == []
    for kind in ("figures", "diagrams", "screenshots", "assets"):
        for entry in manifest[kind]:
            assert (REPO / entry["path"]).is_file() or entry["status"] == "pending"
            assert not entry["path"].startswith("/")
    for entry in manifest["screenshots"]:
        assert entry["owner"] == "coordinator"
    assert [d["path"] for d in manifest["diagrams"]][:4] == [
        "docs/architecture_logical.drawio.svg", "docs/architecture_physical.drawio.svg",
        "docs/run_flow_activity.drawio.svg", "docs/run_flow_sequence.drawio.svg"]


def test_a_missing_file_that_is_not_pending_fails(tmp_path):
    root = copy_repo(tmp_path)
    (root / "presentation" / "charts" / "failure-labels.svg").unlink()
    manifest = json.loads((root / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    assert any("failure-labels" in p and "missing" in p for p in pe.check_manifest(manifest, root))


def test_logo_digest_and_source_note(tmp_path):
    root = copy_repo(tmp_path)
    manifest = json.loads((root / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    assert pe.check_manifest(manifest, root) == []
    note = (root / "presentation/assets/zhaw_rgb.jpg.source.txt").read_text(encoding="utf-8")
    assert "https://www.zhaw.ch/storage/engineering/ueber-uns/medien/zhaw_rgb.jpg" in note
    assert manifest["assets"][0]["sha256"] in note
    (root / "presentation/assets/zhaw_rgb.jpg").write_bytes(b"changed")
    assert any("digest" in p for p in pe.check_manifest(manifest, root))


def test_forbidden_text_is_rejected():
    assert pe.scan_text("x", "see /Users/someone/file")
    assert pe.scan_text("x", "Authorization: Bearer abcdefghijklmnop")
    assert pe.scan_text("x", "sk-abcdefghijklmnopqrstu")
    assert pe.scan_text("x", "~/.codegen_eval/spend_ledger.jsonl")
    assert pe.scan_text("x", "clean text") == []


def test_committed_presentation_files_are_free_of_paths_and_secrets():
    suffixes = {".svg", ".json", ".cast", ".html", ".txt", ".md"}
    for path in sorted((REPO / "presentation").rglob("*")):
        if path.is_file() and path.suffix in suffixes:
            text = path.read_text(encoding="utf-8")
            assert pe.scan_text(str(path), text, (str(REPO), str(pathlib.Path.home()))) == []


# --- ledger and import discipline ---------------------------------------------------------------

def test_scripts_never_import_or_name_the_ledger():
    for name in ("presentation_evidence", "render_charts", "record_demo"):
        source = (SCRIPTS / f"{name}.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+codegen_eval(\.| import )ledger", source, re.M)
        assert "codegen_eval.ledger" not in source.replace("import codegen_eval.ledger", "")
        assert "Ledger(" not in source and "spend_ledger" not in source.split("FORBIDDEN_TEXT")[0]


def test_importing_the_script_does_not_load_evaluator_code(tmp_path):
    code = ("import sys; sys.path.insert(0, %r); import presentation_evidence, render_charts, record_demo; "
            "assert not [m for m in sys.modules if m.startswith('codegen_eval')], 'evaluator code loaded'"
            % str(SCRIPTS))
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_guard_ledger_points_at_a_path_that_does_not_exist(monkeypatch):
    monkeypatch.delenv(pe.LEDGER_ENV, raising=False)
    path = pe.guard_ledger()
    assert pathlib.Path(path).name == "absent.jsonl" and not pathlib.Path(path).exists()
    assert pe.os.environ[pe.LEDGER_ENV] == path


def test_assemble_and_check_never_open_the_real_ledger(monkeypatch):
    seen = []
    real_open, real_path_open = builtins.open, pathlib.Path.open

    def watch(name):
        if ".codegen_eval" in str(name):
            seen.append(str(name))
            raise AssertionError("the ledger must not be opened")

    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (watch(f), real_open(f, *a, **k))[1])
    monkeypatch.setattr(pathlib.Path, "open", lambda self, *a, **k: (watch(self), real_path_open(self, *a, **k))[1])
    live = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pe.assemble(live, REPO)
    assert pe.check_all(REPO) == []
    assert seen == []


def test_staleness_is_a_read_only_report(tmp_path, capsys, monkeypatch):
    root = copy_repo(tmp_path)
    before = (root / pe.SUMMARY_REL).read_text(encoding="utf-8")
    monkeypatch.setattr(pe, "_collect_count", lambda root, marker: 1)
    assert pe.staleness(root) == 0
    assert "older than the repository" in capsys.readouterr().out
    assert (root / pe.SUMMARY_REL).read_text(encoding="utf-8") == before


def test_collect_refuses_without_bundles_argument(capsys):
    with pytest.raises(SystemExit):
        pe.main(["collect"])


# --- round 2: protocol facts, user text, alt text ---------------------------------------------------

def test_protocol_facts_are_quoted_and_provenanced(summary):
    protocol = summary["protocol"]
    assert (protocol["tasks"], protocol["trials_per_task"]) == (10, 3)
    assert (protocol["planned_trials_per_variant"], protocol["planned_trials_total"]) == (30, 60)
    assert (protocol["ceiling_chf"], protocol["checkpoint_chf"]) == (15, 10)
    assert protocol["ledger_total_chf"] == "0.0068475273497" and protocol["probes_passed"] == 67
    assert len(protocol["probe_categories"]) == 5 and "Podman control" in protocol["probe_categories"]
    fields = {d["field"] for d in summary["documents"]}
    for name in ("protocol.tasks", "protocol.ceiling_chf", "protocol.checkpoint_chf",
                 "protocol.ledger_total_chf", "protocol.probe_category.0", "protocol.planned_total"):
        assert name in fields
    assert pe.assemble_doc_sections(summary["documents"])["protocol"] == protocol


def test_a_protocol_value_edited_without_its_quote_fails(tmp_path):
    root = copy_repo(tmp_path)

    def change(data):
        data["protocol"]["ceiling_chf"] = 20
        next(d for d in data["documents"] if d["field"] == "protocol.ceiling_chf")["value"] = 20
    rewrite_summary(root, change)
    problems = pe.check_all(root)
    assert any("protocol.ceiling_chf" in p for p in problems)


def test_a_protocol_quote_edited_in_the_document_fails(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "docs" / "progress.md"
    path.write_text(path.read_text(encoding="utf-8").replace("CHF 15 ceiling blocks", "CHF 20 ceiling blocks"),
                    encoding="utf-8")
    assert any("protocol.ceiling_chf" in p for p in pe.check_all(root))


def test_protocol_must_agree_with_the_comparison(summary):
    broken = json.loads(json.dumps(summary))
    broken["protocol"]["tasks"] = 9
    assert any("protocol.tasks" in p for p in pe.cross_check(broken))


def test_word_numbers_are_read_for_the_protocol():
    assert pe.extract_value("ten tasks x three trials", None, r"(\w+) tasks x (\w+) trials", 2, "wordint") == 3
    with pytest.raises(pe.EvidenceError):
        pe.extract_value("many tasks x few trials", None, r"(\w+) tasks", 1, "wordint")


def test_user_text_file_has_empty_marked_slots():
    import tomllib
    text = (REPO / pe.USER_TEXT_REL).read_text(encoding="utf-8")
    assert "THE USER WRITES" in text and "No tool" in text
    data = tomllib.loads(text)
    assert set(data) == {"motivation", "takeaways"}
    for slot in data.values():
        assert set(slot) == {"deck", "report"} and slot == {"deck": "", "report": ""}


def test_manifest_lists_the_user_text_and_reports_empty_slots():
    manifest = json.loads((REPO / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    entry = manifest["user_text"]
    assert entry["path"] == "presentation/user_text.toml" and entry["owner"] == "user"
    assert entry["slots"] == {"motivation": {"deck": "empty", "report": "empty"},
                              "takeaways": {"deck": "empty", "report": "empty"}}
    assert (REPO / entry["path"]).is_file()


def test_a_filled_slot_is_reported_filled_and_the_file_is_never_written(tmp_path):
    root = copy_repo(tmp_path)
    path = root / pe.USER_TEXT_REL
    path.write_text(path.read_text(encoding="utf-8").replace('[takeaways]\ndeck = ""',
                                                            '[takeaways]\ndeck = "my words"'), encoding="utf-8")
    before = path.read_bytes()
    entry = pe.user_text_entry(root)
    assert entry["slots"]["takeaways"]["deck"] == "filled" and entry["slots"]["motivation"]["deck"] == "empty"
    pe.build_manifest(root)
    assert path.read_bytes() == before


def test_a_missing_user_text_file_fails_the_manifest_check(tmp_path):
    root = copy_repo(tmp_path)
    manifest = json.loads((root / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    (root / pe.USER_TEXT_REL).unlink()
    assert any("user_text" in p for p in pe.check_manifest(manifest, root))


def test_no_script_writes_the_user_text_file():
    for name in ("presentation_evidence", "render_charts", "record_demo"):
        source = (SCRIPTS / f"{name}.py").read_text(encoding="utf-8")
        for match in re.finditer(r"USER_TEXT_REL|user_text\.toml", source):
            line = source[source.rfind("\n", 0, match.start()) + 1:source.find("\n", match.end())]
            assert not re.search(r"write_text|write_bytes|open\(.*[\"']w|\.touch\(|unlink", line), line


def test_collect_and_manifest_leave_the_user_text_file_untouched(tmp_path):
    root = copy_repo(tmp_path)
    path = root / pe.USER_TEXT_REL
    before = path.read_bytes()
    assert pe.main(["--root", str(root), "manifest"]) == 0
    assert path.read_bytes() == before


def test_every_manifest_entry_has_alt_text_including_the_logo(tmp_path):
    manifest = json.loads((REPO / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    for kind in ("figures", "diagrams", "screenshots", "assets"):
        for entry in manifest[kind]:
            assert entry["alt"].strip(), (kind, entry["id"])
    assert "ZHAW" in manifest["assets"][0]["alt"]
    root = copy_repo(tmp_path)
    broken = json.loads(json.dumps(manifest))
    broken["assets"][0]["alt"] = " "
    assert any("alt text is required" in p and "zhaw-logo" in p for p in pe.check_manifest(broken, root))
    broken = json.loads(json.dumps(manifest))
    del broken["figures"][0]["alt"]
    assert any("alt text is required" in p for p in pe.check_manifest(broken, root))


def test_compact_entries_must_link_to_a_full_figure(tmp_path):
    root = copy_repo(tmp_path)
    manifest = json.loads((root / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    compact = next(f for f in manifest["figures"] if f["variant"] == "compact")
    compact["full_size"] = "nope"
    assert any("full_size" in p for p in pe.check_manifest(manifest, root))


def test_version_one_interface_is_extended_additively():
    manifest = json.loads((REPO / pe.MANIFEST_REL).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1 and pe.SCHEMA_VERSION == 1
    old_ids = {"outcome-overview", "outcome-by-category", "outcome-by-task", "failure-labels",
               "story-lists-02", "story-strings-01", "efficiency-calls", "efficiency-tokens",
               "efficiency-latency", "cost-charged-reserved", "engineering-tests", "engineering-ci",
               "engineering-changes"}
    full = {f["id"]: f for f in manifest["figures"] if f["variant"] == "full"}
    assert set(full) == old_ids
    for entry in full.values():
        assert entry["path"] == f"presentation/charts/{entry['id']}.svg" and entry["viewbox"] == "0 0 960 540"


def test_story_values_are_cross_checked_even_when_the_charts_are_regenerated(tmp_path):
    root = copy_repo(tmp_path)
    render_charts = load_script("render_charts")

    def change(data):
        data["stories"]["lists_02"]["revised"][0]["model_calls"] = 2
        data["stories"]["strings_01"]["revised"][1]["failed_checks"][0]["actual"] = 5
    rewrite_summary(root, change)
    summary = pe.load_summary(root)
    for name, svg in render_charts.render_all(summary).items():  # regenerate the charts together
        (root / pe.CHARTS_REL / name).write_text(svg, encoding="utf-8")
    problems = pe.check_all(root)
    assert any("stories.lists_02.revised" in p for p in problems)
    assert any("stories.strings_01.revised" in p for p in problems)
    assert not any("differs from a fresh render" in p for p in problems)


def test_story_facts_are_quoted_documents(summary):
    values = {d["field"]: d["value"] for d in summary["documents"]}
    assert values["story.lists_02.revised_trials"] == 3
    assert values["story.lists_02.revised_model_calls"] == 1 and values["story.lists_02.revised_tool_attempts"] == 0
    assert values["story.strings_01.failed_check"] == "strings_01_d" and values["story.strings_01.failed_actual"] == 0
    assert pe.cross_check(summary) == []


# --- round 4: the latest recorded CI run ------------------------------------------------------------

def test_the_latest_ci_run_is_marked_in_the_quote_table_not_typed():
    marked = [key for key, spec in pe.CI_RUNS.items() if spec.get("latest")]
    assert marked == ["r9"]
    sections = pe.assemble_doc_sections(pe.build_documents(REPO))
    latest = next(r for r in sections["ci_runs"] if r["run"] == sections["ci_latest"])
    assert latest["commit"] == "e00236d" and latest["conclusion"] == "success"
    assert (latest["offline_tests"], latest["offline_skipped"]) == (1199, 67)
    assert (latest["podman_tests"], latest["podman_skipped"], latest["podman_failed"]) == (64, 0, 0)
    assert sections["ci_latest"] == latest["run"]


def test_the_summary_records_the_latest_run_from_the_document(summary):
    assert summary["engineering"]["ci"]["latest"] == "43461309299"
    latest = next(r for r in summary["engineering"]["ci"]["runs"] if r["run"] == "43461309299")
    assert latest["offline_tests"] == 1199 and latest["podman_tests"] == 64
    assert "https://github.com/jolbax-training/cas_aml_mlops_project/actions/runs/43461309299" in (
        REPO / "docs/ci_evidence.md").read_text(encoding="utf-8")


def test_a_summary_latest_run_that_differs_from_the_document_fails(tmp_path):
    root = copy_repo(tmp_path)
    rewrite_summary(root, lambda data: data["engineering"]["ci"].update(latest="41581787430"))
    assert any("engineering.ci.latest" in p for p in pe.check_all(root))


def test_editing_the_latest_ci_section_of_the_document_fails(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "docs" / "ci_evidence.md"
    path.write_text(path.read_text(encoding="utf-8").replace("tests=1199", "tests=1200"), encoding="utf-8")
    assert any("ci.r9.offline_tests" in p for p in pe.check_all(root))


def test_the_engineering_charts_show_the_latest_run(summary):
    charts = load_script("render_charts")
    rendered = charts.render_all(summary)
    for name in ("engineering-tests.svg", "engineering-tests-compact.svg"):
        assert "1,199" in rendered[name] and "825" not in rendered[name].replace("offline_collected", "")
    assert "43461309299" in rendered["engineering-tests.svg"]
    assert "43461309299" in rendered["engineering-ci.svg"]


def test_exactly_one_latest_marker_is_required(monkeypatch):
    documents = pe.build_documents(REPO)
    two = {**pe.CI_RUNS, "r8": {**pe.CI_RUNS["r8"], "latest": True}}
    monkeypatch.setattr(pe, "CI_RUNS", two)
    with pytest.raises(pe.EvidenceError, match="exactly one"):
        pe.assemble_doc_sections(documents)
    none = {key: {k: v for k, v in spec.items() if k != "latest"} for key, spec in pe.CI_RUNS.items()}
    monkeypatch.setattr(pe, "CI_RUNS", none)
    with pytest.raises(pe.EvidenceError, match="exactly one"):
        pe.assemble_doc_sections(documents)


def test_the_latest_run_does_not_depend_on_list_order_or_id_size():
    sections = pe.assemble_doc_sections(pe.build_documents(REPO))
    runs = sections["ci_runs"]
    assert [int(r["run"]) for r in runs] == sorted(int(r["run"]) for r in runs)  # display order only
    assert sections["ci_latest"] == next(r["run"] for r in runs if r.get("commit") == "e00236d")
