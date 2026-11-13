import json
import re
import xml.etree.ElementTree as ET

import pytest

from presentation_support import REPO, load_script

charts = load_script("render_charts")
work_log = load_script("build_work_log")

ALLOWED = {"svg", "title", "desc", "defs", "marker", "path", "g", "rect", "text", "tspan", "style"}


@pytest.fixture(scope="module")
def summary():
    return json.loads((REPO / "presentation/evidence/summary.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rendered(summary):
    return charts.render_all(summary)


def parse(svg):
    return ET.fromstring(svg)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def test_thirteen_charts_in_the_four_requested_sets(rendered):
    ids = {name[:-4] for name in rendered}
    assert len(ids) == 13
    assert {"outcome-overview", "outcome-by-category", "outcome-by-task"} <= ids
    assert {"failure-labels", "story-lists-02", "story-strings-01"} <= ids
    assert {"efficiency-calls", "efficiency-tokens", "efficiency-latency", "cost-charged-reserved"} <= ids
    assert {"engineering-tests", "engineering-ci", "engineering-changes"} <= ids


def test_rendering_is_deterministic(summary, rendered):
    assert charts.render_all(summary) == rendered


def test_committed_charts_equal_a_fresh_render(summary):
    assert charts.check_charts(summary, REPO / "presentation/charts") == []


def test_check_reports_missing_stale_and_extra_files(summary, tmp_path):
    for name, content in charts.render_all(summary).items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    (tmp_path / "outcome-overview.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "failure-labels.svg").unlink()
    (tmp_path / "stray.svg").write_text("<svg/>", encoding="utf-8")
    problems = charts.check_charts(summary, tmp_path)
    assert any("outcome-overview" in p and "differs" in p for p in problems)
    assert any("failure-labels" in p and "missing" in p for p in problems)
    assert any("stray" in p for p in problems)


def test_every_chart_is_accessible_and_script_free(rendered):
    for name, svg in rendered.items():
        root = parse(svg)
        assert root.get("role") == "img" and root.get("viewBox") == "0 0 960 540", name
        ids = {e.get("id"): local(e.tag) for e in root.iter() if e.get("id")}
        assert set(root.get("aria-labelledby").split()) <= set(ids), name
        assert sorted(ids.values()) == ["desc", "title"], name
        assert "<script" not in svg and "http" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', ""), name
        assert "javascript:" not in svg and "href" not in svg and "url(" not in svg, name
        first = [e for e in root if local(e.tag) == "rect"][0]
        assert (first.get("width"), first.get("height"), first.get("fill")) == ("960", "540", "#ffffff"), name


def test_every_chart_uses_only_the_work_log_element_set_and_passes_its_validator(rendered):
    for name, svg in rendered.items():
        assert {local(e.tag) for e in parse(svg).iter()} <= ALLOWED, name
        work_log.validate_svg(svg)


def test_every_text_is_at_least_the_minimum_font_size(rendered):
    assert charts.MIN_FONT == 20
    for name, svg in rendered.items():
        texts = [e for e in parse(svg).iter() if local(e.tag) == "text"]
        assert texts, name
        for element in texts:
            assert element.get("font-size") is not None, (name, element.text)
            assert int(element.get("font-size")) >= charts.MIN_FONT, (name, element.text)


def test_counts_sit_beside_rates(rendered):
    for name in ("outcome-overview", "outcome-by-category"):
        labels = [e.text for e in parse(rendered[f"{name}.svg"]).iter() if local(e.tag) == "text"]
        assert any(re.fullmatch(r"\d+/\d+ \(\d+\.\d%\)", t or "") for t in labels), name
    overview = rendered["outcome-overview.svg"]
    assert "27/30 (90.0%)" in overview and "29/30 (96.7%)" in overview
    assert "108/120" in overview and "119/120" in overview


def test_two_variant_charts_differ_by_hatching_not_only_colour(rendered):
    for name in ("outcome-overview", "outcome-by-category", "efficiency-calls", "failure-labels"):
        svg = rendered[f"{name}.svg"]
        assert 'fill="#1f4e8c"' in svg and 'fill="#f7c999"' in svg
        assert re.search(r'<path d="M[^"]+" fill="none" stroke="#a33f00"', svg), name


def test_hatch_stays_inside_its_rectangle():
    d = re.search(r'd="([^"]+)"', charts.hatch(100, 50, 60, 22)).group(1)
    for x, y in re.findall(r"(\d+) (\d+)", d):
        assert 100 <= int(x) <= 160 and 50 <= int(y) <= 72
    assert charts.hatch(0, 0, 0, 10) == "" and charts.hatch(0, 0, 10, 0) == ""


def test_stories_show_the_recorded_trials(rendered):
    lists = rendered["story-lists-02.svg"]
    assert "prose before code" in lists and "fenced reply" in lists and "bare function" in lists
    strings = rendered["story-strings-01.svg"]
    assert "strings_01_d (actual 0)" in strings and "wrong_answer" in strings


def test_efficiency_captions_make_no_unsupported_claim(rendered):
    manifest = json.loads((REPO / "presentation/manifest.json").read_text(encoding="utf-8"))
    captions = {f["id"]: f["caption"] for f in manifest["figures"]}
    assert "not attributed to the prompt" in captions["efficiency-latency"]
    assert "not attributed to the prompt" in captions["cost-charged-reserved"]
    for cid, caption in captions.items():
        assert not re.search(r"breakthrough|significant|proves", caption, re.I), cid
        assert not re.search(r"\b(improvement)\b", caption) or "not a measured improvement" in caption, cid
    for name in ("efficiency-latency", "cost-charged-reserved"):
        assert "not attributed to the prompt" in rendered[f"{name}.svg"]


def test_chart_numbers_come_from_the_summary(summary):
    changed = json.loads(json.dumps(summary))
    changed["comparison"]["baseline"]["primary"]["count"] = 11
    changed["comparison"]["baseline"]["primary"]["rate"] = 11 / 30
    assert "11/30 (36.7%)" in charts.render_all(changed)["outcome-overview.svg"]


def test_footnote_wraps_and_rejects_overlong_notes():
    assert charts.footnote("short").count("<text") == 1
    assert charts.footnote("word " * 20).count("<text") == 2
    with pytest.raises(ValueError):
        charts.footnote("word " * 40)


def test_cli_writes_and_checks(tmp_path, capsys):
    out = tmp_path / "charts"
    assert charts.main(["--out", str(out)]) == 0
    assert charts.main(["--out", str(out), "--check"]) == 0
    (out / "outcome-overview.svg").write_text("<svg/>", encoding="utf-8")
    assert charts.main(["--out", str(out), "--check"]) == 1
    assert charts.main(["--summary", str(tmp_path / "missing.json")]) == 1
