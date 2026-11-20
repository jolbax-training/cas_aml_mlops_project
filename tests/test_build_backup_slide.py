"""Offline tests for scripts/build_backup_slide.py: committed evidence only, no bundle, Podman or key."""

import copy
import json
import re
from pathlib import Path

import pytest

from codegen_eval.scale_analysis import wilson_interval
from presentation_support import REPO, load_script

slide = load_script("build_backup_slide")
V1 = json.loads(slide.V1_JSON.read_text(encoding="utf-8"))
V2 = json.loads(slide.V2_JSON.read_text(encoding="utf-8"))


def write(path: Path, data) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def inputs(tmp_path):
    def make(v1=None, v2=None, takeaway=""):
        user = tmp_path / "user_text.toml"
        user.write_text(f"takeaway = {json.dumps(takeaway)}\n", encoding="utf-8")
        return {"v1": write(tmp_path / "v1.json", v1 or V1), "v2": write(tmp_path / "v2.json", v2 or V2),
                "user_text": user}
    return make


def page(**kw) -> str:
    return slide.build(**kw)


def test_headline_names_all_three_v2_results_and_the_users_framing():
    first, sub = slide.headline(slide.collect())
    assert first.startswith("Small samples mislead: ")
    assert ("at 30 trials per prompt the revised prompt was ahead by 2 trials (27/30 vs 29/30); "
            "at 100 trials per run: baseline 99/100, revised 99/100, baseline repeated 97/100.") in first
    assert sub == ("Repeating the same baseline prompt moved the result by 2 trials (99 -> 97); "
                   "changing the prompt moved it by 0.")
    assert not re.search(r"\b(better|worse|improv|prove|win)", first + sub, re.I)


def test_headline_fails_when_the_facts_do_not_hold(inputs):
    v1 = copy.deepcopy(V1)
    v1["runs"]["revised"]["primary"]["count"] = 27
    v1["runs"]["revised"]["metrics"]["failure_labels"] = {"wrong_answer": 3}
    paths = inputs(v1=v1)
    with pytest.raises(slide.SlideError, match="not ahead"):
        slide.headline(slide.collect(paths["v1"], paths["v2"]))
    v2 = copy.deepcopy(V2)
    v2["runs"]["revised"]["primary"]["count"] = 95
    v2["runs"]["revised"]["metrics"]["failure_labels"] = {"wrong_answer": 5}
    paths = inputs(v2=v2)
    with pytest.raises(slide.SlideError, match="not less than"):
        slide.headline(slide.collect(paths["v1"], paths["v2"]))


def test_chart_has_five_rows_with_counts_and_axis_words():
    svg = slide.chart_svg(slide.collect())
    for label in ("v1 baseline", "v1 revised", "v2 baseline", "v2 revised", "v2 baseline repeat"):
        assert f">{label}<" in svg
    for kn in ("27/30", "29/30", "99/100", "97/100"):
        assert f">{kn}<" in svg
    assert svg.count('class="dot ') == 5
    assert "success rate, axis starts at 0.70" in svg
    assert "2026-11-03" in svg and "2026-11-19" in svg


def test_interval_below_the_axis_start_fails(inputs):
    v1 = copy.deepcopy(V1)
    v1["runs"]["baseline"]["wilson_95"]["lower"] = 0.69
    paths = inputs(v1=v1)
    with pytest.raises(slide.SlideError, match="outside the chart axis"):
        slide.collect(paths["v1"], paths["v2"])


def test_intervals_in_the_evidence_match_the_wilson_function():
    for source in (V1, V2):
        for run in source["runs"].values():
            low, high = wilson_interval(run["primary"]["count"], run["primary"]["of"])
            assert (round(low, 4), round(high, 4)) == (run["wilson_95"]["lower"], run["wilson_95"]["upper"])


def test_grid_has_fifty_task_cells_and_marks_misses_and_lists_02():
    columns = slide.collect()
    grid = slide.grid_html(columns)
    task_rows = re.findall(r'<tr(?: class="focus")?><th scope="row" class="task">(\w+)</th>(.*?)</tr>', grid)
    cells = [c for name, body in task_rows if name not in ("formatting failures", "other failures")
             for c in re.findall(r"<td", body)]
    assert len(cells) == 50
    assert '<tr class="focus"><th scope="row" class="task">lists_02</th>' in grid
    lists = re.search(r"lists_02</th>(.*?)</tr>", grid).group(1)
    assert re.findall(r">(\d+/\d+)<", lists) == ["0/3", "3/3", "9/10", "10/10", "9/10"]
    assert 'class="miss">0/3<' in grid and 'class="ok">10/10<' in grid


def test_failure_rows_split_formatting_from_other():
    grid = slide.grid_html(slide.collect())
    fmt = re.search(r"formatting failures</th>(.*?)</tr>", grid).group(1)
    other = re.search(r"other failures</th>(.*?)</tr>", grid).group(1)
    assert re.findall(r">(\d+/\d+)<", fmt) == ["3/30", "0/30", "1/100", "0/100", "3/100"]
    assert re.findall(r">(\d+/\d+)<", other) == ["0/30", "1/30", "0/100", "1/100", "0/100"]
    assert "small signal, few trials" in grid
    assert "4/200 baseline trials vs 0/100 revised" in grid


def test_failure_label_sum_check(inputs):
    v2 = copy.deepcopy(V2)
    v2["runs"]["repeat"]["metrics"]["failure_labels"]["syntax_error"] = 5
    paths = inputs(v2=v2)
    with pytest.raises(slide.SlideError, match="failure labels sum to 6"):
        slide.collect(paths["v1"], paths["v2"])


def test_unknown_label_counts_as_other(inputs):
    v2 = copy.deepcopy(V2)
    v2["runs"]["baseline"]["metrics"]["failure_labels"] = {"timeout": 1}
    paths = inputs(v2=v2)
    column = slide.collect(paths["v1"], paths["v2"])[2]
    assert (column["formatting"], column["other"]) == (0, 1)


def test_task_lists_must_match(inputs):
    v1 = copy.deepcopy(V1)
    v1["runs"]["baseline"]["per_task"].pop("strings_02")
    paths = inputs(v1=v1)
    with pytest.raises(slide.SlideError, match="task list differs"):
        slide.collect(paths["v1"], paths["v2"])


def test_date_comes_from_the_run_id(inputs):
    v1 = copy.deepcopy(V1)
    v1["runs"]["baseline"]["run_id"] = "nodate"
    paths = inputs(v1=v1)
    with pytest.raises(slide.SlideError, match="no date prefix"):
        slide.collect(paths["v1"], paths["v2"])
    assert [c["date"] for c in slide.collect()] == ["2026-11-03"] * 2 + ["2026-11-19"] * 3


def test_wrong_experiment_file_is_refused(inputs):
    paths = inputs()
    with pytest.raises(slide.SlideError, match="expected"):
        slide.collect(paths["v2"], paths["v1"])


def test_empty_takeaway_shows_a_placeholder_and_release_flag_fails(inputs):
    paths = inputs(takeaway="   ")
    text = page(**paths)
    assert 'class="takeaway unset"' in text and "to be written by the student" in text
    with pytest.raises(slide.SlideError, match="takeaway is empty"):
        page(**paths, require_user_text=True)
    out = REPO / "backup_slide" / "never_written.html"
    assert slide.main(["--v1", str(paths["v1"]), "--v2", str(paths["v2"]), "--user-text",
                       str(paths["user_text"]), "--output", str(out), "--require-user-text"]) == 1
    assert not out.exists()


def test_takeaway_is_shown_escaped_and_limited(inputs):
    paths = inputs(takeaway="Ten tasks <b>only</b> & one model.")
    text = page(**paths, require_user_text=True)
    assert "Ten tasks &lt;b&gt;only&lt;/b&gt; &amp; one model." in text and "unset" not in text.split("<main")[1]
    assert len(slide.read_takeaway(inputs(takeaway="x" * 180)["user_text"])) == 180
    with pytest.raises(slide.SlideError, match="limit is 180"):
        slide.read_takeaway(inputs(takeaway="x" * 181)["user_text"])


def test_user_text_must_be_a_string(tmp_path):
    bad = tmp_path / "u.toml"
    bad.write_text("takeaway = 3\n")
    with pytest.raises(slide.SlideError, match="must be a string"):
        slide.read_takeaway(bad)


def test_builder_never_writes_the_user_text(tmp_path, inputs):
    paths = inputs(takeaway="kept")
    before = paths["user_text"].read_bytes()
    out = tmp_path / "out" / "p.html"
    assert slide.main(["--v1", str(paths["v1"]), "--v2", str(paths["v2"]), "--user-text",
                       str(paths["user_text"]), "--output", str(out)]) == 0
    assert paths["user_text"].read_bytes() == before and out.is_file()
    source = (REPO / "scripts/build_backup_slide.py").read_text()
    assert source.count("write_text(") == 0 and "USER_TEXT, \"w" not in source


def test_build_is_deterministic():
    assert page() == page()


def test_committed_page_equals_a_fresh_build():
    assert slide.OUTPUT.read_text(encoding="utf-8") == page()
    assert slide.main(["--check"]) == 0


def test_check_fails_on_drift_and_when_missing(tmp_path, inputs):
    paths = inputs()
    args = ["--v1", str(paths["v1"]), "--v2", str(paths["v2"]), "--user-text", str(paths["user_text"])]
    out = tmp_path / "p.html"
    assert slide.main(args + ["--output", str(out), "--check"]) == 1
    assert slide.main(args + ["--output", str(out)]) == 0
    assert slide.main(args + ["--output", str(out), "--check"]) == 0
    out.write_text(out.read_text().replace("Small samples", "Large samples"))
    assert slide.main(args + ["--output", str(out), "--check"]) == 1


def test_page_is_self_contained():
    text = slide.OUTPUT.read_text(encoding="utf-8")
    for needle in ("<script", "<link", "@import", "url(", "http", "xmlns"):
        assert needle not in text, needle
    assert not re.search(r'(?:src|href)="(?!data:)', text)
    assert text.count("<svg") == 1 and text.count("<img") == 1


def test_css_tokens_equal_the_deck():
    deck = (REPO / "presentation/deck/deck.css").read_text(encoding="utf-8")
    root = re.search(r":root\s*\{(.*?)\}", deck, re.S).group(1)
    deck_tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]+);", root))
    for name, value in slide.TOKENS.items():
        assert deck_tokens[name] == value
    assert "font-family: system-ui, sans-serif" in deck


def test_font_floors_at_1920():
    text = slide.OUTPUT.read_text(encoding="utf-8")
    css = text.split("<style>")[1].split("</style>")[0].split("@page")[0]
    sizes = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        match = re.search(r"font-size:\s*([\d.]+)cqw", body)
        if match:
            sizes[selectors.strip()] = float(match.group(1)) * 19.2
    assert min(sizes.values()) >= 20 - 1e-9
    for sentence in (".headline", ".subline", ".takeaway"):
        assert sizes[sentence] >= 28 - 1e-9, sentence
    assert sizes[".limits"] >= 24 - 1e-9          # the deck's footnote size, exempt from the 28px floor
    vb = re.search(r'viewBox="0 0 (\d+) \d+"', text)
    scale = slide.CHART_CQW * 19.2 / int(vb.group(1))
    svg_sizes = [float(s) * scale for s in re.findall(r'font-size="([\d.]+)"', text)]
    assert svg_sizes and min(svg_sizes) >= 18 - 1e-9


def test_print_geometry_is_explicit():
    text = slide.OUTPUT.read_text(encoding="utf-8")
    assert "@page { size: A4 landscape; margin: 6mm; }" in text
    for rule in ("width: 285mm", "height: 160.3mm", "aspect-ratio: auto", "break-inside: avoid",
                 "break-after: avoid", "print-color-adjust: exact", "-webkit-print-color-adjust: exact",
                 "container-type: inline-size"):
        assert rule in text.split("@media print")[1], rule
    assert "100vh" not in text.split("@media print")[1]


def test_logo_hash_matches_the_manifest_and_a_wrong_logo_is_refused(tmp_path):
    manifest = json.loads(slide.MANIFEST.read_text())
    (asset,) = [a for a in manifest["assets"] if a["id"] == "zhaw-logo"]
    assert asset["sha256"] == slide.LOGO_SHA256 and asset["alt"] == slide.LOGO_ALT
    wrong = tmp_path / "logo.jpg"
    wrong.write_bytes(b"not the logo")
    with pytest.raises(slide.SlideError, match="sha256 differs"):
        slide._logo_uri(wrong)


def test_the_committed_user_text_is_only_read_by_the_builder():
    assert slide.USER_TEXT.is_file() and slide.USER_TEXT.parent == REPO / "backup_slide"
