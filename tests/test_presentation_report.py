"""Offline tests for scripts/build_report.py: no browser, bundles, network, Podman or credentials.

They run against the committed manifest, summary, template and stylesheet, and against small
templates written into tmp_path (the builder accepts absolute template, stylesheet and user-text
paths, so no tree has to be copied)."""

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_report", REPO / "scripts" / "build_report.py")
report = importlib.util.module_from_spec(spec)
sys.modules["build_report"] = report
spec.loader.exec_module(report)

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def make_inputs(tmp_path: Path, template: str | None = None, css: str | None = None, user: str | None = None):
    paths = {}
    if template is not None:
        (tmp_path / "template.html").write_text(template, encoding="utf-8")
        paths["template_path"] = tmp_path / "template.html"
    if css is not None:
        (tmp_path / "report.css").write_text(css, encoding="utf-8")
        paths["css_path"] = tmp_path / "report.css"
    if user is not None:
        (tmp_path / "user_text.toml").write_text(user, encoding="utf-8")
        paths["user_text_path"] = tmp_path / "user_text.toml"
    return report.Inputs(REPO, **paths)


def page_template(body: str) -> str:
    pages = "".join(
        f'<section class="page" id="page-{n}"><h2>Page heading</h2><div class="pbody">{body if n == 1 else ""}</div>{{{{footer:{n}}}}}</section>'
        for n in range(1, 5)
    )
    return "{{nav}}<main>" + pages + "</main>"


@pytest.fixture(scope="module")
def real():
    inputs = report.Inputs(REPO)
    return inputs, report.build_html(inputs)


def user_toml(motivation: str = "", takeaways: str = "") -> str:
    return f'[motivation]\ndeck = ""\nreport = {json.dumps(motivation)}\n\n[takeaways]\ndeck = ""\nreport = {json.dumps(takeaways)}\n'


# --- the real report ------------------------------------------------------------


def test_real_build_is_four_pages_and_deterministic(real):
    inputs, text = real
    assert text == report.build_html(report.Inputs(REPO))
    root = report.parse(text)
    pages = [n for n in root.walk() if n.tag == "section" and "page" in n.classes()]
    assert [p.attrs["id"] for p in pages] == ["page-1", "page-2", "page-3", "page-4"]
    for number in range(1, 5):
        assert f"Page {number} / 4" in text
    assert not report.check_structure(text, root)


def test_real_check_passes_and_reports_placeholders(real):
    problems, warnings, holders = report.run_checks(real[0], real[1])
    assert problems == []
    assert any("unmeasured" in w for w in warnings)
    # the user text and the date are the user's; the report shows them as placeholders
    assert "date" in holders and "user text motivation" in holders and "user text takeaways" in holders


def test_script_free_offline_and_self_contained(real):
    _, text = real
    assert not re.search(r"<(script|iframe|object|embed|form|link|base)\b", text, re.I)
    assert not re.search(r"\son[a-z]+\s*=", text, re.I)
    assert not re.search(r'(?:src|href)="(?:https?:)?//', text)
    assert "Content-Security-Policy" in text and "img-src data:" in text
    assert '<html lang="en"' in text


def test_navigation_is_screen_only_and_outside_main(real):
    _, text = real
    root = report.parse(text)
    navs = [n for n in root.walk() if n.tag == "nav"]
    assert navs and all("screen-only" in n.classes() for n in navs)
    main = next(n for n in root.walk() if n.tag == "main")
    assert not any(n.tag == "nav" for n in main.walk())
    assert re.search(r"@media print\s*\{[^@]*\.screen-only\s*\{\s*display:\s*none", real[0].css)


def test_numbers_come_from_the_summary_and_match_the_document(real):
    inputs, text = real
    summary = inputs.summary
    doc = (REPO / "docs/prompt_comparison.md").read_text(encoding="utf-8")
    ratiopct = report.format_value(summary["comparison"]["baseline"]["primary"], "ratiopct", "x")
    assert ratiopct == "27/30 (90.0%)" and ratiopct in doc
    revised = report.format_value(summary["comparison"]["revised"]["primary"], "ratiopct", "x")
    assert revised in doc
    assert report.format_value(summary["comparison"]["revised"]["hidden_checks"], "pct", "x") == "99.2%"
    assert ratiopct in text and revised in text
    assert report.format_value(summary["protocol"]["ledger_total_chf"], "chf4", "x") == "0.0068"


def test_figures_numbered_by_appearance_with_manifest_captions(real):
    inputs, text = real
    labels = re.findall(r"<b>Figure (\d+)\.</b>", text)
    assert labels == [str(i) for i in range(1, len(labels) + 1)]
    for ident in ("outcome-overview-compact", "story-strings-01-compact"):
        assert report.esc(inputs.figures[ident]["caption"]) in text
    # every compact chart used is the manifest's compact variant
    for match in re.finditer(r'id="fig-([\w-]+-compact)"', text):
        assert inputs.figures[match.group(1)]["variant"] == "compact"
    assert 'href="#fig-story-lists-02-compact"' in text


def test_four_chart_sets_are_covered(real):
    inputs, text = real
    used = set(re.findall(r'id="fig-([\w-]+)"', text))
    sets = {
        "outcome": {"outcome-overview-compact", "outcome-by-category-compact"},
        "failure and stories": {"failure-labels-compact", "story-lists-02-compact", "story-strings-01-compact"},
        "efficiency and cost": {"efficiency-calls-compact", "cost-charged-reserved-compact", "efficiency-latency-compact"},
        "engineering": {"engineering-tests-compact", "engineering-changes-compact"},
    }
    for name, ids in sets.items():
        assert used & ids, name
    assert 'id="fig-story-lists-02-compact"' in text and 'id="fig-story-strings-01-compact"' in text


def test_limits_and_non_claim_are_quoted_from_the_summary(real):
    inputs, text = real
    assert text.count('<q class="quoted"') >= 8
    for index in range(len(inputs.summary["limits"]["items"])):
        row = report.doc_row(inputs.summary, f"limit.{index}")
        assert report.esc(report.plain(row["quote"])) in text
    assert report.esc(inputs.summary["limits"]["statement"]) in text


def test_evidence_section_prints_full_digests_and_run_ids(real):
    inputs, text = real
    for run in inputs.summary["provenance"]["runs"].values():
        assert run["run_id"] in text and run["bundle_digest"] in text
    assert "MLflow run" in text and "../docs/prompt_comparison.md" in text


def test_pending_and_empty_items_are_visible_placeholders(real):
    _, text = real
    assert 'class="slot slot-empty ph"' in text
    assert "YOUR TEXT HERE (motivation)" in text and "presentation/user_text.toml" in text
    assert "[DATE: fill in]" in text


def test_work_log_and_demo_links_are_non_fatal(real):
    _, text = real
    assert 'href="index.html"' in text and 'href="demo.html"' in text


def test_release_build_fails_while_anything_is_unfilled(capsys):
    code = report.main(["--root", str(REPO), "build", "--require-user-text", "--output", str(REPO / "report" / "never_written.html")])
    assert code == 1
    err = capsys.readouterr().err
    assert "date" in err and "motivation" in err and "takeaways" in err
    assert not (REPO / "report" / "never_written.html").exists()


def test_build_refuses_an_output_outside_the_repository(tmp_path, capsys):
    assert report.main(["--root", str(REPO), "build", "--output", str(tmp_path / "x.html")]) == 1
    assert "outside the repository root" in capsys.readouterr().err


# --- directives, slots and failures --------------------------------------------


def test_unknown_references_fail_the_build(tmp_path):
    for body, message in (
        ("{{fig:no-such-figure}}", "unknown manifest id"),
        ("{{val:comparison.nope}}", "no value at"),
        ("{{nothing:x}}", "unknown directive"),
        ("{{user:interpretation}}", "unknown user slot"),
        ("{{ref:outcome-overview-compact}}", "not placed"),
        ("{{table:nope}}", "unknown table"),
        ("{{val:protocol.tasks|bogus}}", "unknown format"),
    ):
        inputs = make_inputs(tmp_path, template=page_template(body))
        with pytest.raises(report.ReportError, match=message):
            report.build_html(inputs)


def test_slot_text_is_escaped_filled_slots_are_not_placeholders(tmp_path):
    inputs = make_inputs(tmp_path, template=page_template("{{user:motivation}}"), user=user_toml(motivation="A <b>bold</b> claim & more.\n\nSecond paragraph."))
    text = report.build_html(inputs)
    assert "A &lt;b&gt;bold&lt;/b&gt; claim &amp; more." in text and "<p>Second paragraph.</p>" in text
    assert 'class="slot slot-empty' not in text
    assert "user text motivation" not in report.placeholders(report.parse(text))


def test_over_long_slot_fails_check(tmp_path):
    inputs = make_inputs(tmp_path, template=page_template("{{user:motivation}}"), user=user_toml(motivation="word " * 200))
    assert any("motivation" in p and "characters" in p for p in report.check_slots(inputs))


def test_pending_screenshot_renders_a_visible_box_and_present_one_an_image(tmp_path):
    inputs = make_inputs(tmp_path, template=page_template("{{shot:shot-mlflow-compare}}"))
    inputs.shots["shot-mlflow-compare"]["status"] = "pending"
    text = report.build_html(inputs)
    assert "Screenshot pending (owner: coordinator)" in text
    assert "screenshot shot-mlflow-compare" in report.placeholders(report.parse(text))
    png = tmp_path / "shot.png"
    png.write_bytes(PNG)
    inputs.shots["shot-mlflow-compare"].update(status="present", path=str(png))
    text = report.build_html(inputs)
    assert "data:image/png;base64," in text and "Screenshot pending" not in text
    assert 'alt="Screenshot: Two-run comparison view."' in text


def test_logo_uses_manifest_alt_and_verifies_its_digest(tmp_path):
    inputs = make_inputs(tmp_path, template=page_template("{{logo}}"))
    text = report.build_html(inputs)
    assert f'alt="{inputs.assets["zhaw-logo"]["alt"]}"' in text
    inputs.assets["zhaw-logo"]["sha256"] = "0" * 64
    with pytest.raises(report.ReportError, match="SHA-256"):
        report.build_html(inputs)


def test_date_set_in_the_manifest_replaces_the_placeholder(tmp_path):
    inputs = make_inputs(tmp_path, template=page_template("{{title:date}}"))
    inputs.manifest["title"]["date"] = "2026-12-01"
    text = report.build_html(inputs)
    assert "2026-12-01" in text and "DATE: fill in" not in text


def test_a_diagram_with_a_script_is_rejected(tmp_path):
    bad = tmp_path / "bad.svg"
    bad.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>x</script></svg>')
    inputs = make_inputs(tmp_path, template=page_template("{{fig:diagram-architecture-logical}}"))
    inputs.diagrams["diagram-architecture-logical"]["path"] = str(bad)
    with pytest.raises(report.ReportError, match="not allowed"):
        report.build_html(inputs)


# --- lints ---------------------------------------------------------------------


def test_digits_lint_catches_a_typed_number_and_accepts_directives_and_allowlist():
    assert report.check_digits("<p>{{val:protocol.tasks}} tasks on A4, lists_02 and strings_01.</p>") == []
    assert any("27/30" in p or "27" in p for p in report.check_digits("<p>We got 27 right.</p>"))
    assert report.check_digits("<!-- 99 in a comment --><p>none</p>") == []
    # whole tokens, not substrings
    assert report.check_digits("<p>A45</p>")


def test_the_committed_template_has_no_typed_numbers():
    assert report.check_digits((REPO / report.TEMPLATE).read_text(encoding="utf-8")) == []


def test_framing_lint_scope(tmp_path):
    def problems(body, user=None):
        inputs = make_inputs(tmp_path, template=page_template(body), user=user or user_toml())
        return report.check_framing(report.parse(report.build_html(inputs)), inputs.template)

    assert problems("<p>This is a real improvement.</p>")
    assert problems("<p>A breakthrough.</p>")
    assert problems("<p>No measured gain.</p>") == []
    # a verbatim quotation of the evidence may use the word; the real report relies on it
    assert problems("{{limits}}") == []
    named = problems("{{user:motivation}}", user_toml(motivation="It was an improvement."))
    assert any("motivation" in p for p in named)
    assert problems('<q class="quoted">improvement</q>')  # the template cannot write the marker itself


def test_real_report_has_no_framing_problems(real):
    inputs, text = real
    assert report.check_framing(report.parse(text), inputs.template) == []


# --- stylesheet and legibility --------------------------------------------------


def css_with(old: str, new: str) -> str:
    css = (REPO / report.STYLESHEET).read_text(encoding="utf-8")
    assert old in css
    return css.replace(old, new, 1)


def test_committed_stylesheet_passes():
    assert report.check_css((REPO / report.STYLESHEET).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("font-size: 7.6pt", "font-size: 6pt", "below 7.5 pt"),
        ("font-size: 7.6pt", "font-size: 9px", "must be in pt"),
        ("--text-muted: #475569", "--text-muted: #a0aec0", "contrast"),
        ("size: A4; margin: 0", "size: A5; margin: 0", "@page"),
        ("height: 296mm", "height: 297mm", "296mm"),
        (".screen-only { display: none !important; }", ".screen-only { display: none !important; }\n  .fig { width: 50mm; }", "may not change layout"),
        ("  .page { box-shadow: none; }", "  .page { box-shadow: none; padding: 0; }", "geometry"),
    ],
)
def test_stylesheet_regressions_fail(old, new, message):
    assert any(message in p for p in report.check_css(css_with(old, new)))


def test_text_colour_must_use_a_token():
    assert any("must use a --text token" in p for p in report.check_css(css_with("a { color: var(--text-link); }", "a { color: #999; }")))


def test_contrast_arithmetic():
    assert report.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert report.contrast("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_chart_too_narrow_fails_legibility(tmp_path):
    inputs = make_inputs(tmp_path, template=page_template("{{fig:outcome-overview-compact}}"), css=css_with("--w-compact: 88mm", "--w-compact: 40mm"))
    problems, _ = report.check_legibility(inputs, report.parse(report.build_html(inputs)), inputs.css)
    assert any("outcome-overview-compact" in p and "below 7.5 pt" in p for p in problems)


def test_real_compact_charts_print_at_least_the_floor(real):
    inputs, text = real
    problems, warnings = report.check_legibility(inputs, report.parse(text), inputs.css)
    assert problems == []
    # draw.io diagrams are reported, not failed: see docs/presentation_report.md
    assert any("diagram" in w for w in warnings)


# --- budgets, overflow and the page counter -------------------------------------


def test_uncalibrated_budgets_fail_check(monkeypatch, real):
    monkeypatch.setitem(report.BUDGETS, "calibrated_against", "")
    problems, _, _ = report.run_checks(real[0], real[1])
    assert any("budgets not calibrated" in p for p in problems)


def test_static_estimate_flags_an_obviously_long_page(tmp_path, monkeypatch):
    monkeypatch.setitem(report.BUDGETS, "calibrated_against", "test")
    long_text = "<p>" + "word " * 4000 + "</p>"
    inputs = make_inputs(tmp_path, template=page_template(long_text))
    problems, _, _ = report.run_checks(inputs)
    assert any("page-1: static estimate" in p for p in problems)


def pdf(pages: int, root_count: int | None = None, leaves: bool = True) -> bytes:
    count = pages if root_count is None else root_count
    body = f"%PDF-1.4\n1 0 obj\n<< /Type /Pages /Count {count} /Kids [] >>\nendobj\n"
    if leaves:
        body += "".join(f"{i + 2} 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" for i in range(pages))
    return body.encode()


def test_page_counter():
    assert report.count_pdf_pages(pdf(4)) == 4
    assert report.count_pdf_pages(pdf(3)) == 3
    with pytest.raises(report.ReportError, match="could not determine"):
        report.count_pdf_pages(pdf(4, leaves=False))  # a page tree with no plain page objects
    with pytest.raises(report.ReportError, match="could not determine"):
        report.count_pdf_pages(pdf(4, root_count=5))


def test_measurement_parsing_and_evaluation():
    rows = [
        {"id": "page-1", "scroll": 1000, "client": 1000, "bodyScroll": 800, "bodyClient": 1000, "ppx": 1118},
        {"id": "page-2", "scroll": 1000, "client": 1000, "bodyScroll": 980, "bodyClient": 1000, "ppx": 1118},
        {"id": "page-3", "scroll": 1100, "client": 1000, "bodyScroll": 1100, "bodyClient": 1000, "ppx": 1118},
    ]
    dom = '<pre id="measure-result">' + json.dumps(rows).replace('"', "&quot;") + "</pre>"
    parsed = report.parse_measurements(dom)
    assert parsed == rows
    errors, warnings = report.evaluate_measurements(parsed)
    assert any("page-3" in e and "clipped" in e for e in errors)
    assert any("page-2" in w for w in warnings) and not any("page-1" in w for w in warnings)
    with pytest.raises(report.ReportError):
        report.parse_measurements("<html></html>")


def test_missing_browser_is_skipped_never_a_pass(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(report, "find_browser", lambda explicit: None)
    built = tmp_path / "p.html"
    built.write_text(report.build_html(report.Inputs(REPO)), encoding="utf-8")
    code = report.main(["--root", str(REPO), "measure"])
    assert code == report.EXIT_SKIPPED
    assert "SKIPPED" in capsys.readouterr().err


# --- discipline -----------------------------------------------------------------


def test_no_ledger_bundle_credential_or_network_access_in_the_script():
    source = (REPO / "scripts" / "build_report.py").read_text(encoding="utf-8")
    for forbidden in ("spend_ledger", ".codegen_eval", "codegen_eval", "run_bundles", "OPENROUTER", "urllib", "requests", "socket"):
        assert forbidden not in source, forbidden


def test_nothing_this_change_commits_names_a_home_path():
    for path in (REPO / "presentation" / "report").iterdir():
        assert "/Users/" not in path.read_text(encoding="utf-8")
    assert "/Users/" not in (REPO / "scripts" / "build_report.py").read_text(encoding="utf-8")


def test_the_change_creates_no_user_text_file():
    assert not list((REPO / "presentation" / "report").glob("user_text*"))
