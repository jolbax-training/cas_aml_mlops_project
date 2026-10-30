import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_work_log", REPO / "scripts" / "build_work_log.py")
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

BUILD_TIME = "2026-10-30T12:00:00Z"
SVG = (REPO / "docs" / "work_log_architecture.svg").read_text(encoding="utf-8")


def make_repo(tmp_path, docs=None, sections=None):
    """A small repository: two selected documents, the real diagram, one pending section."""
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    files = {
        "docs/one.md": "# One\n\nSee [two](two.md#second-part) and [itself](#one).\n",
        "docs/two.md": "# Two\n\n## Second part\n\nText.\n",
        "docs/arch.md": "Explains the figure. See [one](one.md).\n",
        "docs/arch.svg": SVG,
    }
    files.update(docs or {})
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content, encoding="utf-8")
    sections = sections if sections is not None else """
[[section]]
id = "one"
title = "Document one"
path = "docs/one.md"
label = "current"

[[section]]
id = "two"
title = "Document two"
path = "docs/two.md"
label = "historical"

[[section]]
id = "results"
title = "Results"
kind = "pending"
needs = ["run-prompt-comparison"]
description = "Comparison outcomes."
"""
    (root / "docs" / "work_log.toml").write_text(
        '[architecture]\ndiagram = "docs/arch.svg"\nexplanation = "docs/arch.md"\n' + sections,
        encoding="utf-8",
    )
    return root


def build(root, check=False, output=None):
    return builder.run(
        root,
        root / "docs" / "work_log.toml",
        output or root / "report" / "index.html",
        builder.parse_build_time(BUILD_TIME),
        check,
    )


def built_html(root):
    build(root)
    return (root / "report" / "index.html").read_text(encoding="utf-8")


def doc_with(tmp_path, markdown):
    root = make_repo(tmp_path, {"docs/one.md": markdown})
    return root


def tree_state(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


# --- source list ---------------------------------------------------------------

def test_sections_render_in_listed_order_without_neighbours(tmp_path):
    root = make_repo(tmp_path, {"docs/neighbour.md": "# Neighbour secret-ish text\n"})
    page = built_html(root)
    ids = re.findall(r'<section id="([a-z-]+)"', page)
    assert ids == ["architecture", "one", "two", "results", "provenance"]
    assert "Neighbour" not in page


@pytest.mark.parametrize("path, message", [
    ("docs/missing.md", "does not exist"),
    ("../outside.md", "escapes the repository"),
    ("/etc/hosts.md", "absolute"),
    (".env.md", "forbidden"),
    ("runs/run.md", "forbidden"),
    ("mlruns/summary.md", "forbidden"),
    ("docs/notes.txt", "only Markdown"),
])
def test_bad_registered_sources_fail(tmp_path, path, message):
    root = make_repo(tmp_path, sections=f'''
[[section]]
id = "bad"
title = "Bad"
path = "{path}"
label = "current"
''')
    (root / "runs").mkdir()
    (root / "runs" / "run.md").write_text("# run\n")
    (root / "mlruns").mkdir()
    (root / "mlruns" / "summary.md").write_text("# summary\n")
    (root / ".env.md").write_text("# env\n")
    with pytest.raises(builder.WorkLogError, match=message):
        build(root)


def test_symlinked_source_is_refused(tmp_path):
    root = make_repo(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("# outside\n")
    (root / "docs" / "link.md").symlink_to(outside)
    (root / "docs" / "work_log.toml").write_text(
        '[architecture]\ndiagram = "docs/arch.svg"\nexplanation = "docs/arch.md"\n'
        '[[section]]\nid = "l"\ntitle = "L"\npath = "docs/link.md"\nlabel = "current"\n')
    with pytest.raises(builder.WorkLogError, match="symlink"):
        build(root)


@pytest.mark.parametrize("sections, message", [
    ('[[section]]\nid = "a"\ntitle = "A"\npath = "docs/one.md"\nlabel = "mine"\n', "label"),
    ('[[section]]\nid = "A b"\ntitle = "A"\npath = "docs/one.md"\nlabel = "current"\n', "id"),
    ('[[section]]\nid = "sections"\ntitle = "A"\npath = "docs/one.md"\nlabel = "current"\n', "reserved"),
    ('[[section]]\nid = "a"\ntitle = "A"\npath = "docs/one.md"\nlabel = "current"\nextra = 1\n', "unknown key"),
    ('[[section]]\nid = "a"\ntitle = "A"\npath = "docs/one.md"\nlabel = "current"\n'
     '[[section]]\nid = "a"\ntitle = "B"\npath = "docs/two.md"\nlabel = "current"\n', "duplicate"),
    ('[[section]]\nid = "a"\ntitle = "A"\npath = "docs/one.md"\nlabel = "current"\n'
     '[[section]]\nid = "b"\ntitle = "B"\npath = "docs/one.md"\nlabel = "current"\n', "more than once"),
])
def test_invalid_source_list_is_rejected(tmp_path, sections, message):
    with pytest.raises(builder.WorkLogError, match=message):
        build(make_repo(tmp_path, sections=sections))


# --- build / check behaviour -----------------------------------------------------

def test_build_is_deterministic_for_a_fixed_build_time(tmp_path):
    root = make_repo(tmp_path)
    first = built_html(root)
    (root / "report" / "index.html").unlink()
    assert built_html(root) == first
    assert 'name="work-log-build-time" content="2026-10-30T12:00:00Z"' in first


def test_check_mode_writes_nothing_and_leaves_sources_unchanged(tmp_path):
    root = make_repo(tmp_path)
    before = tree_state(root)
    assert "check passed" in build(root, check=True)
    assert tree_state(root) == before
    assert not (root / "report").exists()


def test_build_leaves_sources_unchanged_and_no_temp_files(tmp_path):
    root = make_repo(tmp_path)
    before = tree_state(root)
    build(root)
    after = tree_state(root)
    assert {k: v for k, v in after.items() if not k.startswith("report/")} == before
    assert list((root / "report").iterdir()) == [root / "report" / "index.html"]


def test_failed_build_preserves_previous_output(tmp_path):
    root = make_repo(tmp_path)
    good = built_html(root)
    (root / "docs" / "one.md").write_text("[broken](missing.md)\n")
    with pytest.raises(builder.WorkLogError, match="missing.md"):
        build(root)
    assert (root / "report" / "index.html").read_text(encoding="utf-8") == good
    assert list((root / "report").iterdir()) == [root / "report" / "index.html"]


def test_check_notes_stale_output_and_rejects_invalid_output(tmp_path):
    root = make_repo(tmp_path)
    build(root)
    assert "out of date" not in build(root, check=True)
    (root / "docs" / "two.md").write_text("# Two\n\n## Second part\n\nChanged.\n")
    assert "out of date" in build(root, check=True)
    (root / "report" / "index.html").write_text("<html><script>x</script></html>")
    with pytest.raises(builder.WorkLogError, match="output validation"):
        build(root, check=True)


def test_command_line_reports_errors_with_exit_code(tmp_path, capsys):
    root = make_repo(tmp_path)
    assert builder.main(["--root", str(root), "--build-time", BUILD_TIME]) == 0
    (root / "docs" / "one.md").write_text("[x](gone.md)\n")
    assert builder.main(["--root", str(root), "--check"]) == 1
    assert "gone.md" in capsys.readouterr().err


# --- rendering and links -----------------------------------------------------------

def test_tables_code_checklists_and_history_render(tmp_path):
    page = built_html(doc_with(tmp_path, (
        "# One\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\n```python\nprint('<hi>')\n```\n\n"
        "- [x] done item\n- [ ] open item\n\n> Superseded plan kept for history.\n")))
    assert "<table>" in page and "<td>2</td>" in page
    assert "print('&lt;hi&gt;')" in page
    assert 'aria-label="done"' in page and 'aria-label="not done"' in page
    assert "done item" in page and "Superseded plan kept for history." in page


def test_heading_anchors_are_unique_and_links_are_rewritten(tmp_path):
    root = make_repo(tmp_path, {"docs/one.md": "# One\n\n## Same\n\n## Same\n\n[to two](two.md#second-part) [self](#same-1) [doc](two.md)\n"})
    page = built_html(root)
    assert 'id="one--same"' in page and 'id="one--same-1"' in page
    assert 'href="#two--second-part"' in page
    assert 'href="#one--same-1"' in page
    assert 'href="#two"' in page
    ids = re.findall(r'\bid="([^"]+)"', page)
    assert len(ids) == len(set(ids))


def test_local_non_embedded_references_are_rebased_and_labelled(tmp_path):
    root = make_repo(tmp_path, {"docs/one.md": "[code](../src/x.py) [dir](../src)\n", "src/x.py": "print(1)\n"})
    page = built_html(root)
    assert 'href="../src/x.py" class="ref source-file"' in page
    assert "(source file, not embedded)" in page


@pytest.mark.parametrize("markdown, message", [
    ("[a](missing.md)", "does not exist"),
    ("[a](two.md#nope)", "no heading #nope"),
    ("[a](#nope)", "no heading #nope"),
    ("[a](javascript:alert(1))", "unsafe URL scheme"),
    ("[a](data:text/html,x)", "unsafe URL scheme"),
    ("[a](file:///etc/passwd)", "unsafe URL scheme"),
    ("[a](https://user:pw@example.com/x)", "credentials"),
    ("[a](http://example.com/x)", "loopback"),
    ("[a](//example.com/x)", "protocol-relative"),
    ("[a](../../outside.md)", "escapes"),
    ("[a](/etc/passwd)", "absolute"),
    ("[a](../.env)", "forbidden"),
    ("[a](../runs/bundle.json)", "forbidden"),
])
def test_unresolved_or_unsafe_links_fail_with_diagnostic(tmp_path, markdown, message):
    root = doc_with(tmp_path, markdown + "\n")
    with pytest.raises(builder.WorkLogError, match=message) as info:
        build(root)
    assert "docs/one.md" in str(info.value)


def test_symlinked_link_target_is_refused(tmp_path):
    root = doc_with(tmp_path, "[a](link.txt)\n")
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    (root / "docs" / "link.txt").symlink_to(outside)
    with pytest.raises(builder.WorkLogError, match="symlink"):
        build(root)


def test_external_and_loopback_references_are_allowed_but_not_fetched(tmp_path):
    page = built_html(doc_with(
        tmp_path, "[ci](https://github.com/o/r/actions/runs/1) [mlflow](http://127.0.0.1:5000/#/experiments/1)\n"))
    assert 'class="ref external"' in page and 'rel="noopener noreferrer"' in page
    assert 'class="ref local-service"' in page
    assert "<link" not in page and "<img" not in page


def test_html_python_and_remote_images_are_inert(tmp_path):
    page = built_html(doc_with(tmp_path, (
        "<script>alert(1)</script>\n\n<img src=\"https://example.com/x.png\" onerror=\"x()\">\n\n"
        "![remote chart](https://example.com/chart.png)\n\n```python\nimport os\nos.system('x')\n```\n")))
    assert "<script" not in page and "<img" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "[image not loaded: remote chart]" in page
    assert "src=" not in re.sub(r"&lt;.*?&gt;", "", page)
    assert "os.system(&#x27;x&#x27;)" in page or "os.system('x')" in page


# --- pending evidence and personal material ---------------------------------------

def test_pending_sections_are_visibly_pending_without_invented_content(tmp_path):
    page = built_html(make_repo(tmp_path))
    section = re.search(r'<section id="results".*?</section>', page, re.S).group(0)
    assert "Pending" in section and "run-prompt-comparison" in section
    assert "No reviewed record is registered yet" in section
    assert not re.search(r"\d+(\.\d+)?\s*%", section)


def test_unanswered_personal_prompts_stay_unanswered(tmp_path):
    journal = "# Journal\n\n## Reflection\n\nWhat surprised you? \n\n_(unanswered)_\n"
    root = make_repo(tmp_path, {"docs/j.md": journal}, sections=f'''
[[section]]
id = "journal"
title = "Journal"
path = "docs/j.md"
label = "personal"
''')
    page = built_html(root)
    assert "What surprised you?" in page and "(unanswered)" in page
    assert "Personal, student-authored" in page


# --- architecture asset ------------------------------------------------------------

def test_architecture_comes_first_with_accessible_text(tmp_path):
    page = built_html(make_repo(tmp_path))
    assert page.index('<section id="architecture"') < page.index('<nav id="sections"') < page.index('<section id="one"')
    assert '<svg' in page and 'role="img"' in page and 'aria-labelledby="arch-title arch-desc"' in page
    assert 'tabindex="0"' in page and 'href="#sections"' in page
    assert "Explains the figure." in page.split('<nav id="sections"')[0]


@pytest.mark.parametrize("bad", [
    SVG.replace("<defs>", "<script>alert(1)</script><defs>"),
    SVG.replace("<defs>", '<image href="https://example.com/x.png"/><defs>'),
    SVG.replace('<rect class="arch-bg"', '<rect onclick="x()" class="arch-bg"'),
    SVG.replace("</style>", "@import url(https://example.com/a.css);</style>"),
    SVG.replace('marker-end="url(#arrow)"', 'marker-end="url(https://example.com/m)"', 1),
    SVG.replace("<svg ", '<!DOCTYPE svg [<!ENTITY x "y">]><svg ', 1),
    SVG.replace('role="img" ', ""),
])
def test_unreviewed_svg_features_are_rejected(bad):
    with pytest.raises(builder.WorkLogError):
        builder.validate_svg(bad)


def test_output_validation_flags_unresolved_anchors_and_remote_loads():
    page = '<!doctype html><meta http-equiv="Content-Security-Policy" content="x">'
    with pytest.raises(builder.WorkLogError, match="internal links without targets: gone"):
        builder.validate_output(page + '<a href="#gone">x</a>')
    with pytest.raises(builder.WorkLogError, match="architecture figure must precede"):
        builder.validate_output(page)
    with pytest.raises(builder.WorkLogError, match="resource"):
        builder.validate_output(page + '<iframe src="https://example.com"></iframe>')


def test_link_title_with_attribute_like_text_does_not_fail_the_build(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs" / "one.md").write_text('[a](https://example.com "see data=1")\n')
    build(root)


def test_uppercase_markdown_target_fragments_are_validated(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs" / "other.MD").write_text("# Real\n")
    (root / "docs" / "one.md").write_text("[x](other.MD#nope)\n")
    with pytest.raises(builder.WorkLogError, match="no heading #nope"):
        build(root)


def test_output_outside_the_repository_is_refused(tmp_path):
    root = make_repo(tmp_path)
    with pytest.raises(builder.WorkLogError, match="outside the repository root"):
        build(root, output=tmp_path.parent / "elsewhere" / "index.html")


def test_report_mode_follows_the_umask_not_the_temp_file(tmp_path):
    root = make_repo(tmp_path)
    build(root)
    assert (root / "report" / "index.html").stat().st_mode & 0o044


def test_architecture_entries_must_have_the_expected_suffix(tmp_path):
    root = make_repo(tmp_path)
    config = root / "docs" / "work_log.toml"
    config.write_text(config.read_text().replace("docs/arch.svg", "docs/arch.md"), encoding="utf-8")
    with pytest.raises(builder.WorkLogError, match="'diagram' must be a .svg file"):
        build(root)


# --- the actual repository ---------------------------------------------------------

def test_actual_repository_builds_and_checks_offline():
    root = builder.REPO_ROOT
    # the output must stay inside the repository (ignored report/), so use a scratch name there
    output = root / "report" / ".test-index.html"
    config = root / "docs" / "work_log.toml"
    build_time = builder.parse_build_time(BUILD_TIME)
    before = tree_state(root / "docs")
    try:
        builder.run(root, config, output, build_time, check=False)
        page = output.read_text(encoding="utf-8")
        assert builder.run(root, config, output, build_time, check=True).startswith("check passed")
    finally:
        output.unlink(missing_ok=True)
    assert tree_state(root / "docs") == before

    assert page.index('<section id="architecture"') < page.index('<nav id="sections"')
    for pending in ("results", "evidence", "demo"):
        section = re.search(rf'<section id="{pending}".*?</section>', page, re.S).group(0)
        assert "Pending" in section
    # the benchmark review and evaluation-design guide documents are registered sources, not pending
    for source in ("benchmark-review", "guide", "coordinator-example"):
        section = re.search(rf'<section id="{source}".*?</section>', page, re.S).group(0)
        assert "Pending" not in section
    # no remote resource is loaded by the page
    assert not re.search(r"<[a-z][^>]*\b(src|srcset)\s*=", page)
    assert not re.search(r'<link\b|<script\b|<img\b', page)
    # links into non-embedded repository files are rebased relative to the output file
    assert 'class="ref source-file"' in page


def test_generated_report_is_ignored_by_git():
    if shutil.which("git") is None:
        pytest.skip("git not available")
    result = subprocess.run(
        ["git", "check-ignore", "-q", "report/index.html"], cwd=REPO, check=False)
    assert result.returncode == 0
