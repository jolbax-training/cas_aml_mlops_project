"""Offline tests for scripts/build_deck.py: no network, bundles, Podman or credentials.

They build from copies of the committed presentation sources in a scratch directory, so a test
may tamper with a source and the repository stays untouched.
"""

import hashlib
import json
import re
import shutil
import sys
import tomllib

import pytest

from presentation_support import REPO, blank_user_text, load_script

deck = load_script("build_deck")


@pytest.fixture
def root(tmp_path):
    target = tmp_path / "repo"
    shutil.copytree(REPO / "presentation", target / "presentation")
    blank_user_text(target)
    shutil.copytree(REPO / "docs", target / "docs", ignore=shutil.ignore_patterns("*.md"))
    (target / "scripts").mkdir()
    shutil.copy(REPO / "scripts" / "build_work_log.py", target / "scripts" / "build_work_log.py")
    (target / "report").mkdir()
    return target


def build(root):
    return deck.build(root, root / "report" / "deck.html")


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def slides_path(root):
    return root / "presentation/deck/slides.toml"


def visible_text(html_text):
    text = re.sub(r"<(script|style)\b.*?</\1>", "", html_text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


def edit_manifest(root, change):
    path = root / "presentation/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    change(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")


# --- outline and timing -------------------------------------------------------

def test_real_sources_build(root):
    page, notes, report = build(root)
    assert page.count('<section class="slide') == 13
    assert notes.count('class="note-page"') == 13


def test_outline_is_the_approved_one():
    assert [item[0] for item in deck.OUTLINE][:3] == ["title", "motivation", "problem"]
    assert len(deck.OUTLINE) == 13
    assert sum(item[2] for item in deck.OUTLINE) == 150 == deck.TOTAL_TENTHS


def test_minutes_in_sources_sum_to_fifteen(root):
    slides = tomllib.loads(slides_path(root).read_text(encoding="utf-8"))["slide"]
    assert deck.check_outline(slides) == [item[2] for item in deck.OUTLINE]


def test_edited_minutes_fail(root):
    edit(slides_path(root), 'title = "Results"\nminutes = 1.5', 'title = "Results"\nminutes = 2.0')
    with pytest.raises(deck.DeckError, match="approved outline"):
        build(root)


def test_reordered_slides_fail(root):
    slides = tomllib.loads(slides_path(root).read_text(encoding="utf-8"))["slide"]
    slides[2], slides[3] = slides[3], slides[2]
    with pytest.raises(deck.DeckError, match="id"):
        deck.check_outline(slides)


def test_a_fourteenth_slide_fails(root):
    with slides_path(root).open("a", encoding="utf-8") as handle:
        handle.write('\n[[slide]]\nid = "extra"\ntitle = "Extra"\nminutes = 1.0\nlayout = "text"\n')
    with pytest.raises(deck.DeckError, match="14 slides"):
        build(root)


def test_renamed_title_fails(root):
    edit(slides_path(root), 'title = "Reproducibility"', 'title = "Repeatability"')
    with pytest.raises(deck.DeckError, match="title"):
        build(root)


# --- numbers and figures by reference -----------------------------------------

def test_results_numbers_come_from_the_summary(root):
    page, _, _ = build(root)
    summary = json.loads((root / "presentation/evidence/summary.json").read_text(encoding="utf-8"))
    primary = summary["comparison"]["baseline"]["primary"]
    assert f"{primary['count']}/{primary['of']}" in visible_text(page)
    assert "27/30" in visible_text(page) and "29/30" in visible_text(page)


def test_results_slide_places_the_manifest_figures(root):
    slides = tomllib.loads(slides_path(root).read_text(encoding="utf-8"))["slide"]
    results = next(slide for slide in slides if slide["id"] == "results")
    assert results["figures"] == ["outcome-overview", "outcome-by-category"]


def test_unknown_figure_id_fails_naming_slide_and_id(root):
    edit(slides_path(root), 'figures = ["outcome-overview", "outcome-by-category"]',
         'figures = ["outcome-overview", "no-such-chart"]')
    with pytest.raises(deck.DeckError, match="results.*no-such-chart"):
        build(root)


def test_empty_alt_text_fails(root):
    def change(manifest):
        next(f for f in manifest["figures"] if f["id"] == "outcome-overview")["alt"] = ""
    edit_manifest(root, change)
    with pytest.raises(deck.DeckError, match="alt"):
        build(root)


def test_logo_alt_comes_from_the_manifest_assets_entry(root):
    page, _, _ = build(root)
    manifest = json.loads((root / "presentation/manifest.json").read_text(encoding="utf-8"))
    logo = next(a for a in manifest["assets"] if a["id"] == "zhaw-logo")
    assert f'alt="{logo["alt"]}"' in page

    def change(m):
        next(a for a in m["assets"] if a["id"] == "zhaw-logo")["alt"] = " "
    edit_manifest(root, change)
    with pytest.raises(deck.DeckError, match="alt"):
        build(root)


def test_unresolved_reference_fails(root):
    edit(slides_path(root), "{{summary:protocol.tasks}}", "{{summary:protocol.no_such_key}}")
    with pytest.raises(deck.DeckError, match="does not resolve"):
        build(root)


@pytest.mark.parametrize("literal", ["27 of them", "CHF 15", "a 29/30 result", "over 100 trials"])
def test_literal_numbers_are_rejected(root, literal):
    edit(slides_path(root), "Baseline first, revised later; each run once", literal)
    with pytest.raises(deck.DeckError, match="literal"):
        build(root)


@pytest.mark.parametrize("ok", ["lists_02", "strings_01-t2", "int64", "a 7 or 8 day trip"])
def test_identifiers_are_not_bare_numbers(ok):
    deck.lint_numbers(f"text {ok} text", "where", set())


def test_allow_list_lets_a_documented_token_through():
    deck.lint_numbers("15 minutes", "where", {"15"})
    with pytest.raises(deck.DeckError):
        deck.lint_numbers("15 minutes", "where", set())


def test_chf4_rounds_half_even_with_a_footnote():
    notes = []
    text = deck.apply_format("chf4", "0.0068475273497", "w", "p", notes)
    assert text == "0.0068*"
    assert notes == ["* Rounded to four decimals from the quoted total 0.0068475273497."]
    assert deck.apply_format("chf4", "0.00685", "w", "p", None) == "0.0068*"


def test_ledger_total_slide_shows_rounded_value_and_full_footnote(root):
    page, _, _ = build(root)
    text = visible_text(page)
    assert "CHF 0.0068*" in re.sub(r"\s+", " ", text)
    assert "0.0068475273497" in text


def test_formats():
    assert deck.apply_format("pct1", 0.9, "w", "p", None) == "90.0%"
    assert deck.apply_format("ratio", {"count": 3, "of": 6}, "w", "p", None) == "3/6"
    assert deck.apply_format("int", 7.0, "w", "p", None) == "7"
    with pytest.raises(deck.DeckError):
        deck.apply_format("hex", 7, "w", "p", None)


def test_protocol_facts_are_references_not_literals(root):
    slides = slides_path(root).read_text(encoding="utf-8")
    assert "{{summary:protocol.ceiling_chf}}" in slides
    assert not re.search(r"CHF\s*\d", slides)


# --- honest framing -----------------------------------------------------------

def test_forbidden_words_in_own_text_fail(root):
    edit(slides_path(root), "Baseline first, revised later; each run once", "A clear improvement")
    with pytest.raises(deck.DeckError, match="improvement"):
        build(root)


def test_captions_may_only_deny_the_claim():
    deck.check_caption("A comparison of two prompts, not a measured improvement.", "w")
    deck.check_caption("Two prompts; not a claim of improvement.", "w")
    with pytest.raises(deck.DeckError):
        deck.check_caption("The revised prompt is an improvement.", "w")


def test_built_text_never_claims_improvement(root):
    page, notes, _ = build(root)
    for text in (visible_text(page), visible_text(notes)):
        for sentence in re.split(r"(?<=[.;])\s+", text):
            if deck.FORBIDDEN_WORDS.search(sentence):
                assert deck.DENIAL.search(sentence), sentence


def test_limits_are_in_the_notes_of_the_limits_slide(root):
    _, notes, _ = build(root)
    summary = json.loads((root / "presentation/evidence/summary.json").read_text(encoding="utf-8"))
    for item in summary["limits"]["items"]:
        assert item in notes


# --- user slots, date, pending evidence ---------------------------------------

def test_empty_slots_show_visible_placeholders(root):
    page, _, report = build(root)
    assert page.count("YOUR TEXT HERE") == 2
    assert "presentation/user_text.toml" in page
    assert report.unfilled_slots == ["title date", "motivation", "takeaways"]


def test_filled_slot_renders_escaped_text_without_placeholder(root):
    path = root / "presentation/user_text.toml"
    edit(path, '[motivation]\ndeck = ""', '[motivation]\ndeck = "First <b>line</b>\\n\\nSecond"')
    page, _, report = build(root)
    assert "First &lt;b&gt;line&lt;/b&gt;" in page and "<b>line</b>" not in page
    assert page.count("YOUR TEXT HERE") == 1
    assert report.unfilled_slots == ["title date", "takeaways"]


def test_missing_slot_key_fails(root):
    path = root / "presentation/user_text.toml"
    edit(path, '[takeaways]\ndeck = ""', "[takeaways]")
    with pytest.raises(deck.DeckError, match="takeaways"):
        build(root)


def test_the_build_never_changes_the_user_text_file(root):
    path = root / "presentation/user_text.toml"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert deck.main(["--root", str(root)]) == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_strict_fails_on_notices_and_check_does_not(root, capsys):
    assert deck.main(["--root", str(root), "--check"]) == 0
    assert deck.main(["--root", str(root), "--strict"]) == 1
    assert "unfilled user slot" in capsys.readouterr().err


def test_date_placeholder_while_empty_and_date_from_the_user_text_when_set(root):
    page, _, notes = build(root)
    assert "[DATE: fill in]" in page and "title date" in notes.unfilled_slots
    edit(root / "presentation/user_text.toml", '[title]\ndate = ""', '[title]\ndate = "2026-12-01 <b>"')
    page, _, notes = build(root)
    assert "[DATE: fill in]" not in page and "2026-12-01 &lt;b&gt;" in page and "<b>" not in page.split("2026-12-01")[1][:12]
    assert "title date" not in notes.unfilled_slots


def test_the_date_is_validated_and_strict_fails_while_it_is_empty(root, capsys):
    path = root / "presentation/user_text.toml"
    assert deck.main(["--root", str(root), "--strict"]) == 1
    assert "title date" in capsys.readouterr().err
    edit(path, '[title]\ndate = ""', '[title]\ndate = "' + "x" * 41 + '"')
    with pytest.raises(deck.DeckError, match="limit is 40"):
        build(root)
    edit(path, "x" * 41, "a\\nb")
    with pytest.raises(deck.DeckError, match="control characters"):
        build(root)


def test_title_slide_has_the_approved_information(root):
    page, _, _ = build(root)
    text = visible_text(page)
    for expected in ("Jose Luis Barahona", "CAS Applied Machine Learning (ZHAW)",
                     "A trustworthy, reproducible, budget-safe evaluation pipeline for a coding agent"):
        assert expected in text


SHOT = "shot-mlflow-trace-lists02-baseline"


def set_shot_status(root, status):
    def change(manifest):
        next(s for s in manifest["screenshots"] if s["id"] == SHOT)["status"] = status
    edit_manifest(root, change)


def test_present_screenshot_is_embedded_from_the_committed_file(root):
    page, _, report = build(root)
    assert "data:image/png;base64," in page and "SCREENSHOT PENDING" not in page
    assert report.pending == []


def test_pending_screenshot_is_a_visible_placeholder(root):
    set_shot_status(root, "pending")
    page, _, report = build(root)
    assert "SCREENSHOT PENDING" in page
    assert report.pending == [SHOT]
    assert deck.main(["--root", str(root), "--strict"]) == 1


def test_present_screenshot_without_file_fails(root):
    (root / "presentation/screenshots/mlflow-trace-lists02-baseline.png").unlink()
    with pytest.raises(deck.DeckError, match="missing"):
        build(root)


def test_slides_4_and_5_use_the_slide_legible_diagrams_not_the_docs_ones(root):
    slides = {s["id"]: s for s in tomllib.loads(slides_path(root).read_text(encoding="utf-8"))["slide"]}
    assert slides["approach"]["figures"] == ["diagram-pipeline-overview"]
    assert slides["integrity"]["figures"] == ["diagram-trust-boundary"]
    for slide in slides.values():
        assert not any(item.startswith("diagram-architecture") for item in slide.get("figures", []))
    _, _, report = build(root)
    assert "diagram-pipeline-overview: 27.2px at layout single" in report.chart_fonts
    assert "diagram-trust-boundary: 22.0px at layout split" in report.chart_fonts


def test_unknown_diagram_id_fails(root):
    edit(slides_path(root), 'figures = ["diagram-trust-boundary"]', 'figures = ["diagram-no-such"]')
    with pytest.raises(deck.DeckError, match="diagram-no-such"):
        build(root)


# --- charts and legibility ----------------------------------------------------

def test_effective_chart_text_is_computed_per_layout(root):
    _, _, report = build(root)
    assert "outcome-overview: 18.6px at layout pair" in report.chart_fonts
    assert "cost-charged-reserved: 22.0px at layout split" in report.chart_fonts


def test_small_chart_text_fails_the_build(root):
    edit_manifest(root, lambda m: next(f for f in m["figures"] if f["id"] == "outcome-overview").update(min_font_units=10))
    with pytest.raises(deck.DeckError, match="below 18px"):
        build(root)


def rule_body(css, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_cqw_basis_is_the_unpadded_slide():
    """1cqw is the query container's content width: the container must carry no padding."""
    css = (REPO / "presentation/deck/deck.css").read_text(encoding="utf-8")
    slide = rule_body(css, ".slide")
    assert "container-type: inline-size" in slide and "padding" not in slide
    assert "padding" in rule_body(css, ".frame")


def test_figure_widths_match_the_stylesheet_and_fit_the_frame():
    css = (REPO / "presentation/deck/deck.css").read_text(encoding="utf-8")
    frame = rule_body(css, ".frame")
    side = float(re.search(r"padding:\s*[\d.]+cqw\s+([\d.]+)cqw", frame).group(1))
    content = 100 - 2 * side
    gap = float(re.search(r"\.stage\s*\{[^}]*gap:\s*([\d.]+)cqw", css).group(1))
    text_col = float(re.search(r"\.col-text \{ flex: 0 0 ([\d.]+)cqw", css).group(1))
    for layout in ("single", "split", "pair"):
        found = float(re.search(rf"\.stage\.{layout} > figure \{{ flex: 0 0 ([\d.]+)cqw", css).group(1))
        assert found == deck.FIGURE_CQW[layout], layout
        assert abs(found * deck.SLIDE_PX / 100 - deck.FIGURE_WIDTH_PX[layout]) < 0.01
    assert 2 * deck.FIGURE_CQW["pair"] + gap <= content
    assert text_col + gap + deck.FIGURE_CQW["split"] <= content
    assert deck.FIGURE_CQW["single"] <= content


def test_effective_chart_text_meets_the_floor_on_the_corrected_basis(root):
    """Pinned: 20 units * cqw width in px / 960 units, with 1cqw = 19.2px on the 1920px slide."""
    for layout, expected in (("pair", 18.6), ("split", 22.0), ("single", 27.2)):
        assert round(20 * deck.FIGURE_CQW[layout] * 19.2 / 960, 1) == expected
        assert expected >= deck.CHART_FLOOR_PX
    _, _, report = build(root)
    for line in report.chart_fonts:
        assert float(line.split(": ")[1].split("px")[0]) >= deck.CHART_FLOOR_PX, line


def css_text():
    return (REPO / "presentation/deck/deck.css").read_text(encoding="utf-8")


def font_sizes(css):
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        for value in re.findall(r"font-size:\s*([^;]+);", body):
            match = re.fullmatch(r"([\d.]+)(cqw|px)", value.strip())
            assert match, f"unsupported font-size {value!r} in {selector.strip()!r}"
            number = float(match.group(1))
            yield selector.strip(), number * (deck.SLIDE_PX / 100 if match.group(2) == "cqw" else 1)


def test_font_floors():
    sizes = list(font_sizes(css_text()))
    assert sizes
    for selector, px in sizes:
        if selector.startswith(".notes"):
            continue
        assert px >= deck.SLIDE_TEXT_FLOOR_PX, (selector, px)
    for selector, px in sizes:
        if selector.startswith(".body"):
            assert px >= deck.BODY_FLOOR_PX, (selector, px)


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_contrast_ratios():
    tokens = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", css_text()))
    for ink, paper, minimum in (
        ("ink", "paper", 7.0), ("muted", "paper", 7.0), ("accent", "paper", 7.0),
        ("warn-ink", "warn-bg", 7.0), ("chrome-ink", "chrome-bg", 7.0),
    ):
        assert contrast(tokens[ink], tokens[paper]) >= minimum, (ink, paper)
    assert contrast(tokens["warn-edge"], tokens["warn-bg"]) >= 3.0


def rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}@]+)\{([^{}]*)\}", css)


def test_slide_hiding_is_scoped_to_the_script_marker():
    for selector, body in rules(css_text()):
        hides = re.search(r"display:\s*none|visibility:\s*hidden", body)
        for single in selector.split(","):
            single = single.strip()
            if hides and re.search(r"\.slide", single):
                assert single.startswith("html.js-deck"), single
            if re.search(r"\.slide", single) and re.search(r"position:\s*(fixed|absolute)", body):
                assert single.startswith("html.js-deck") or single == ".slide", single


def test_print_rules():
    css = css_text()
    assert re.search(r"@page\s*\{\s*size:\s*1920px 1080px", css)
    assert "break-before: page" in css and "break-after" not in css
    print_block = css[css.index("@media print"):]
    assert ".notes" in print_block and "display: none" in print_block
    assert "print-color-adjust: exact" in print_block


def test_stacked_layout_without_script(root):
    page, _, _ = build(root)
    assert 'class="slide' in page and "js-deck" not in re.sub(r"<(style|script)\b.*?</\1>", "", page, flags=re.S)


# --- navigation script --------------------------------------------------------

def script_text():
    return (REPO / "presentation/deck/deck.js").read_text(encoding="utf-8")


def test_navigation_keys_and_counter():
    script = script_text()
    for key in ("ArrowRight", "ArrowLeft", '" "', "PageDown", "PageUp", "Home", "End"):
        assert key in script, key
    assert "js-deck" in script and "show-notes" in script and "requestFullscreen" in script
    assert len(script.splitlines()) < 60


@pytest.mark.parametrize("word", ["fetch", "XMLHttpRequest", "import", "eval", "localStorage",
                                  "sessionStorage", "http:", "https:", "WebSocket", "setTimeout", "setInterval",
                                  "document.cookie", "Function("])
def test_navigation_script_is_inert(word):
    assert word not in script_text()


# --- notes --------------------------------------------------------------------

def test_notes_are_hidden_on_slides_and_present_on_the_notes_page(root):
    page, notes, _ = build(root)
    slides_only = re.sub(r'<aside class="notes".*?</aside>', "", page, flags=re.S)
    assert "Speaker notes" not in visible_text(slides_only)
    assert "Speaker notes" in visible_text(notes)
    assert page.count('<aside class="notes"') == 13


def test_notes_header_has_minutes_and_running_total(root):
    page, notes, _ = build(root)
    assert "Slide 1 of 13: Title | 0.5 min | running total 0.5 of 15 min" in page
    assert "Slide 13 of 13: Questions | 0.5 min | running total 15 of 15 min" in notes


def test_notes_for_an_unknown_slide_or_a_missing_slide_fail(root):
    with (root / "presentation/deck/notes.toml").open("a", encoding="utf-8") as handle:
        handle.write('ghost = ["x"]\n')
    with pytest.raises(deck.DeckError, match="unknown slide ids"):
        build(root)


def test_every_slide_has_notes(root):
    notes = tomllib.loads((root / "presentation/deck/notes.toml").read_text(encoding="utf-8"))
    assert set(notes) == {item[0] for item in deck.OUTLINE}


def test_notes_never_carry_the_users_slot_text(root):
    edit(root / "presentation/user_text.toml", '[motivation]\ndeck = ""', '[motivation]\ndeck = "My own reason XYZZY"')
    page, notes, _ = build(root)
    assert "XYZZY" in page and "XYZZY" not in notes
    assert "XYZZY" not in re.findall(r'<aside class="notes".*?</aside>', page, flags=re.S)[1]


# --- links --------------------------------------------------------------------

def test_missing_link_targets_are_text_marked_not_built_and_not_fatal(root):
    page, _, report = build(root)
    assert "presentation_report.html (not built)" in page
    assert set(report.fallbacks) == {"presentation_report.html", "demo.html", "index.html"}
    assert deck.REPORT_PAGE == "presentation_report.html"


def test_present_link_targets_become_anchors(root):
    for name in ("presentation_report.html", "demo.html", "index.html"):
        (root / "report" / name).write_text("x", encoding="utf-8")
    page, _, report = build(root)
    assert report.fallbacks == []
    for name in ("presentation_report.html", "demo.html", "index.html"):
        assert f'<a href="{name}">' in page
    assert f'href="{deck.REPO_URL}"' in page


# --- output safety, determinism, files ----------------------------------------

def test_output_has_no_external_loading_and_no_private_strings(root):
    page, notes, _ = build(root)
    for text in (page, notes):
        assert "/Users/" not in text and not deck.KEY_LIKE.search(text)
        assert not re.search(r"<link\b|<iframe\b|<script[^>]*\ssrc=", text)
        assert not re.search(r"<img[^>]*\ssrc=\"(?!data:)", text)
    assert page.startswith("<!doctype html>") and '<html lang="en">' in page and "<title>" in page


def test_validate_output_rejects_external_resources():
    for bad in ('<img src="https://example.org/x.png">', '<link rel="stylesheet" href="x.css">',
                "<style>a{background:url(http://x/y.png)}</style>", "/Users/someone/x"):
        with pytest.raises(deck.DeckError):
            deck.validate_output(bad)


def test_every_image_has_alt_text(root):
    page, _, _ = build(root)
    images = re.findall(r"<img\b[^>]*>", page)
    assert images and all(re.search(r'alt="[^"]+"', tag) for tag in images)


def test_build_is_byte_identical_twice(root):
    first = build(root)[:2]
    second = build(root)[:2]
    assert first == second


def test_cli_writes_both_files_and_check_writes_nothing(root):
    out = root / "report" / "deck.html"
    assert deck.main(["--root", str(root), "--check"]) == 0
    assert not out.exists()
    assert deck.main(["--root", str(root)]) == 0
    assert out.is_file() and (root / "report" / "deck_notes.html").is_file()


def test_failed_build_keeps_previous_output_and_the_work_log(root):
    work_log = root / "report" / "index.html"
    work_log.write_text("work log", encoding="utf-8")
    assert deck.main(["--root", str(root)]) == 0
    before = (root / "report" / "deck.html").read_bytes()
    edit(slides_path(root), 'title = "Results"\nminutes = 1.5', 'title = "Results"\nminutes = 3.0')
    assert deck.main(["--root", str(root)]) == 1
    assert (root / "report" / "deck.html").read_bytes() == before
    assert work_log.read_text(encoding="utf-8") == "work log"


def test_word_and_bullet_lint_warns_without_failing(root):
    edit(slides_path(root), "Baseline first, revised later; each run once", " ".join(["word"] * 30))
    _, _, report = build(root)
    assert any("more than 25 words" in w for w in report.warnings)


def test_sources_have_no_home_path_or_key():
    for path in (REPO / "presentation/deck").iterdir():
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text and not deck.KEY_LIKE.search(text), path.name


def test_script_never_touches_the_ledger_or_api_keys():
    source = (REPO / "scripts/build_deck.py").read_text(encoding="utf-8")
    for word in ("ledger", "OPENROUTER", "environ", "codegen_eval", "subprocess", "urllib", "socket"):
        assert word not in source, word


# --- review follow-ups --------------------------------------------------------

@pytest.mark.parametrize("literal", ["rate 0.90", "pi is 3.14", "about 9 of them", "9 trials", "7%"])
def test_decimals_and_counted_single_digits_are_literals(literal):
    with pytest.raises(deck.DeckError, match="literal"):
        deck.lint_numbers(literal, "where", set())


def test_prose_digits_without_a_count_are_not_literals():
    deck.lint_numbers("a 7 or 8 day trip, lists_02, int64", "where", set())


@pytest.mark.parametrize("figures", ['[]', '["outcome-overview"]'])
def test_pair_layout_needs_two_figures(root, figures):
    edit(slides_path(root), 'figures = ["outcome-overview", "outcome-by-category"]', f"figures = {figures}")
    with pytest.raises(deck.DeckError, match="needs 2 figure"):
        build(root)


def test_single_layout_without_a_figure_is_a_deck_error_not_a_crash(root):
    edit(slides_path(root), 'figures = ["diagram-pipeline-overview"]', "figures = []")
    with pytest.raises(deck.DeckError, match="needs 1 figure"):
        build(root)
    assert deck.main(["--root", str(root)]) == 1


def test_slide_6_screenshot_is_a_css_crop_of_the_same_image(root):
    page, _, _ = build(root)
    assert 'class="crop"' in page and "Detail: the span tree of the trace." in page
    manifest = json.loads((root / "presentation/manifest.json").read_text(encoding="utf-8"))
    shot = next(s for s in manifest["screenshots"] if s["id"] == "shot-mlflow-trace-lists02-baseline")
    assert f'alt="{shot["alt"]}"' in page
    x, y, w, h = 144, 90, 616, 400
    assert f"width:{1440 / w * 100:.4f}%;left:{-x / w * 100:.4f}%;top:{-y / h * 100:.4f}%" in page


def test_crop_box_must_lie_inside_the_screenshot(root):
    edit(slides_path(root), "box = [144, 90, 616, 400]", "box = [144, 90, 6160, 400]")
    with pytest.raises(deck.DeckError, match="outside"):
        build(root)


def test_a_failure_before_the_renames_leaves_both_previous_files(root, monkeypatch):
    out = root / "report" / "deck.html"
    notes = root / "report" / "deck_notes.html"
    assert deck.main(["--root", str(root)]) == 0
    before = (out.read_bytes(), notes.read_bytes())
    edit(root / "presentation/deck/notes.toml", "Introduce the headline", "Open with the headline")
    new_deck, new_notes, _ = build(root)
    real = deck.tempfile.NamedTemporaryFile
    calls = []

    def failing(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(deck.tempfile, "NamedTemporaryFile", failing)
    with pytest.raises(OSError):
        deck.write_pair(root, out, new_deck, new_notes)
    assert (out.read_bytes(), notes.read_bytes()) == before
    assert not list((root / "report").glob(".deck-*.tmp"))
