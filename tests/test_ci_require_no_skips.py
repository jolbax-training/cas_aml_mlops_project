import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_require_no_skips", REPO / "scripts" / "ci_require_no_skips.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

CLEAN = '<testsuites><testsuite tests="2" skipped="0" failures="0" errors="0">' \
        '<testcase classname="t" name="a"/><testcase classname="t" name="b"/></testsuite></testsuites>'
SKIPPED = '<testsuite tests="2" skipped="1" failures="0" errors="0"><testcase classname="t" name="a"/>' \
          '<testcase classname="t" name="needs_podman"><skipped message="no podman"/></testcase></testsuite>'
EMPTY = '<testsuites><testsuite tests="0" skipped="0" failures="0" errors="0"/></testsuites>'
FAILED = '<testsuite tests="1" skipped="0" failures="1" errors="0"><testcase classname="t" name="a"/></testsuite>'


def run(tmp_path, xml):
    report = tmp_path / "junit.xml"
    if xml is not None:
        report.write_text(xml)
    return helper.main([str(report)])


def test_clean_run_passes(tmp_path):
    assert run(tmp_path, CLEAN) == 0


def test_skipped_test_fails_and_is_named(tmp_path, capsys):
    assert run(tmp_path, SKIPPED) == 1
    err = capsys.readouterr().err
    assert "t::needs_podman" in err and "no podman" in err


@pytest.mark.parametrize("xml", [EMPTY, FAILED, None])
def test_empty_failed_or_missing_report_fails(tmp_path, xml):
    assert run(tmp_path, xml) == 1


def test_usage_error():
    assert helper.main([]) == 2
