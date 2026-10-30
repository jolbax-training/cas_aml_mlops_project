import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_annotate_junit", REPO / "scripts" / "ci_annotate_junit.py")
annotate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(annotate)


def report(tmp_path, cases, tests=None):
    path = tmp_path / "junit.xml"
    path.write_text(f'<testsuites><testsuite tests="{tests or len(cases)}" skipped="0" failures="{len(cases)}" '
                    f'errors="0">{"".join(cases)}</testsuite></testsuites>')
    return path


def test_each_failure_becomes_one_escaped_error_annotation(tmp_path):
    case = ('<testcase classname="tests.test_x" name="test_a[p,q]"><failure message="assert \'timeout\' == \'returned\'">'
            'line one\nassert 100% bad</failure></testcase>')
    lines = annotate.annotations(report(tmp_path, [case]))

    assert lines[0].startswith("::error title=tests.test_x%3A%3Atest_a[p%2Cq]::")
    assert "\n" not in lines[0] and "100%25 bad" in lines[0]
    assert lines[-1] == "::notice title=pytest totals::tests=1, skipped=0, failures=1, errors=0"


def test_annotations_are_capped_and_truncated(tmp_path):
    cases = [f'<testcase classname="t" name="n{i}"><failure message="{"x" * 2000}"/></testcase>' for i in range(30)]
    lines = annotate.annotations(report(tmp_path, cases))

    errors = [line for line in lines if line.startswith("::error")]
    assert len(errors) == 21 and "10 further" in errors[-1]
    assert all(len(line) < 700 for line in errors)


def test_missing_report_is_one_error_and_exit_is_zero(tmp_path, capsys):
    assert annotate.main([str(tmp_path / "none.xml")]) == 0
    assert capsys.readouterr().out.startswith("::error title=pytest produced no JUnit report")
