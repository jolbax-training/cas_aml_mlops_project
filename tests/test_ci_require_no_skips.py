import ast
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


def _module_level_skips(path):
    """Calls that skip a whole module at collection time: any call in a top-level statement
    (assignments, if/try handlers, finally, with) outside function and class bodies, however
    `pytest` or the skip functions were imported."""
    tree = ast.parse(path.read_text())
    modules, functions = {"pytest"}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "pytest"}
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            functions |= {a.asname or a.name: a.name for a in node.names}
    found = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                    and func.value.id in modules and func.attr in {"importorskip", "skip"}:
                name = func.attr
            elif isinstance(func, ast.Name) and functions.get(func.id) in {"importorskip", "skip"}:
                name = functions[func.id]
            else:
                continue
            found.append((node.lineno, f"{path.name}:{node.lineno} {name}"))
    return [hit for _, hit in sorted(found)]


def test_module_level_skip_detection_covers_assignments_aliases_and_handlers(tmp_path):
    probe = tmp_path / "test_probe.py"
    probe.write_text("""import pytest
import pytest as pt
from pytest import importorskip, skip as bail
a = pytest.importorskip("a")
importorskip("b")
try:
    import c
except ImportError:
    pt.skip("c", allow_module_level=True)
finally:
    bail("d", allow_module_level=True)


def test_fine():
    pytest.skip("inside a test is fine")


class TestFine:
    def test_it(self):
        pytest.importorskip("e")
""")

    assert [hit.split()[0] for hit in _module_level_skips(probe)] == [
        "test_probe.py:4", "test_probe.py:5", "test_probe.py:9", "test_probe.py:11"]


def test_no_test_module_skips_at_collection():
    """A module-level skip is reported even when the module's tests are deselected, which
    fails the podman job's no-skip guard (it broke that job twice); use a skipif mark."""
    skips = [hit for path in sorted((REPO / "tests").glob("test_*.py")) for hit in _module_level_skips(path)]
    assert skips == []
