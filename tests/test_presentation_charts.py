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


def is_compact(name):
    return name.endswith("-compact.svg")


def test_thirteen_full_charts_in_the_four_requested_sets(rendered):
    ids = {name[:-4] for name in rendered if not is_compact(name) and not name.startswith("diagram-")}
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
        assert root.get("role") == "img", name
        assert root.get("viewBox") == ("0 0 480 270" if is_compact(name) else "0 0 960 540"), name
        ids = {e.get("id"): local(e.tag) for e in root.iter() if e.get("id")}
        assert set(root.get("aria-labelledby").split()) <= set(ids), name
        assert sorted(ids.values()) == ["desc", "title"], name
        assert "<script" not in svg and "http" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', ""), name
        assert "javascript:" not in svg and "href" not in svg and "url(" not in svg, name
        first = [e for e in root if local(e.tag) == "rect"][0]
        size = ("480", "270") if is_compact(name) else ("960", "540")
        assert (first.get("width"), first.get("height"), first.get("fill")) == (*size, "#ffffff"), name


def test_every_chart_uses_only_the_work_log_element_set_and_passes_its_validator(rendered):
    for name, svg in rendered.items():
        assert {local(e.tag) for e in parse(svg).iter()} <= ALLOWED, name
        work_log.validate_svg(svg)


def test_every_text_is_at_least_the_minimum_font_size(rendered):
    assert charts.MIN_FONT == 20 and charts.COMPACT_MIN_FONT == 17
    for name, svg in rendered.items():
        floor = charts.COMPACT_MIN_FONT if is_compact(name) else charts.MIN_FONT
        texts = [e for e in parse(svg).iter() if local(e.tag) == "text"]
        assert texts, name
        for element in texts:
            assert element.get("font-size") is not None, (name, element.text)
            assert int(element.get("font-size")) >= floor, (name, element.text)


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


def test_compact_font_arithmetic_gives_at_least_7_5_pt_at_half_a_column():
    mm_per_unit = charts.COMPACT_MIN_MM / charts.CW
    assert charts.COMPACT_MIN_MM == 78 and (charts.CW, charts.CH) == (480, 270)
    printed_pt = charts.COMPACT_MIN_FONT * mm_per_unit / 25.4 * 72
    assert printed_pt >= 7.5
    assert 7.5 / 72 * 25.4 / mm_per_unit <= charts.COMPACT_MIN_FONT


def test_every_text_stays_inside_its_viewbox(rendered):
    """A rough extent estimate (0.56 em per character) so a label cannot run off the chart."""
    for name, svg in rendered.items():
        root = parse(svg)
        width = float(root.get("viewBox").split()[2])
        for element in root.iter():
            if local(element.tag) != "text":
                continue
            size, x = int(element.get("font-size")), float(element.get("x"))
            extent = len(element.text or "") * size * 0.56
            if element.get("text-anchor") == "end":
                assert x - extent >= 0, (name, element.text)
            elif element.get("text-anchor") == "middle":
                assert x - extent / 2 >= 0 and x + extent / 2 <= width, (name, element.text)
            else:
                assert x + extent <= width, (name, element.text)


def test_compact_charts_cover_all_four_sets_and_link_to_full_charts(rendered):
    manifest = json.loads((REPO / "presentation/manifest.json").read_text(encoding="utf-8"))
    figures = {f["id"]: f for f in manifest["figures"]}
    compact = [f for f in figures.values() if f["variant"] == "compact"]
    assert len(compact) == 10
    for entry in compact:
        assert entry["id"] == f"{entry['full_size']}-compact"
        assert figures[entry["full_size"]]["variant"] == "full"
        assert entry["viewbox"] == "0 0 480 270" and entry["min_render_mm"] == 78
        assert entry["min_font_units"] == 17 and entry["uses"] == ["report"]
        assert f"{entry['id']}.svg" in rendered
    covered = {f["full_size"] for f in compact}
    assert {"outcome-overview", "outcome-by-category"} <= covered
    assert {"failure-labels", "story-lists-02", "story-strings-01"} <= covered
    assert {"efficiency-calls", "efficiency-latency", "cost-charged-reserved"} <= covered
    assert {"engineering-tests", "engineering-changes"} <= covered
    assert all(f["variant"] == "full" and f["full_size"] is None for f in figures.values() if f["id"] not in {c["id"] for c in compact})


def test_compact_charts_keep_counts_beside_rates_and_the_limits(rendered):
    overview = rendered["outcome-overview-compact.svg"]
    assert "27/30 90%" in overview and "29/30 97%" in overview and "119/120 99%" in overview
    joined = " ".join(e.text or "" for e in parse(overview).iter() if local(e.tag) == "text")
    assert "Not a measured improvement" in joined
    for name in ("efficiency-latency-compact", "cost-charged-reserved-compact"):
        joined = " ".join(e.text or "" for e in parse(rendered[f"{name}.svg"]).iter() if local(e.tag) == "text")
        assert "not attributed to the" in joined or "not attributed" in rendered[f"{name}.svg"]
    assert "Baseline v1" in overview and "Revised v2" in overview


def test_compact_charts_are_deterministic_and_numbers_come_from_the_summary(summary, rendered):
    assert charts.render_all(summary) == rendered
    changed = json.loads(json.dumps(summary))
    changed["comparison"]["baseline"]["primary"].update(count=11, rate=11 / 30)
    assert "11/30 37%" in charts.render_all(changed)["outcome-overview-compact.svg"]


def test_compact_note_wraps_and_rejects_overlong_notes():
    assert charts.cfoot("short").count("<text") == 1
    assert charts.cfoot("word " * 14).count("<text") == 2
    with pytest.raises(ValueError):
        charts.cfoot("word " * 30)


ASCENT = 0.80   # em above the baseline: ascenders (l, d, b, f) reach about 0.76 em, capitals 0.72 em
DESCENT = 0.22  # em below the baseline, only for strings with descenders or parentheses
CLEARANCE = 2   # user units of air required between a text box and anything else


def boxes(root):
    """Estimated text boxes (0.56 em per character, ascent and descent) and shapes with their stroke."""
    texts, shapes = [], []
    rects = [e for e in root.iter() if local(e.tag) == "rect"][1:]  # the first is the background
    for e in rects:
        if e.get("fill") == "none":
            continue  # a region outline, not a filled shape
        x, y, w, h = (float(e.get(k)) for k in ("x", "y", "width", "height"))
        stroke = float(e.get("stroke-width", 0)) / 2 if e.get("stroke", "none") != "none" else 0
        shapes.append((x - stroke, y - stroke, x + w + stroke, y + h + stroke, "rect"))
    for e in root.iter():
        if local(e.tag) != "text":
            continue
        size, x, y = int(e.get("font-size")), float(e.get("x")), float(e.get("y"))
        width = len(e.text or "") * size * 0.56
        anchor = e.get("text-anchor")
        left = x - width if anchor == "end" else x - width / 2 if anchor == "middle" else x
        descends = any(ch in "gjpqy()," for ch in (e.text or ""))
        texts.append((left, y - ASCENT * size, left + width, y + (DESCENT * size if descends else 0), e.text))
    return texts, shapes


def overlaps(a, b, clearance=CLEARANCE):
    return (min(a[2], b[2]) - max(a[0], b[0]) > -clearance
            and min(a[3], b[3]) - max(a[1], b[1]) > -clearance)


def inside(text_box, shape):
    """A label wholly inside a filled box is intended; a partial overlap is a collision."""
    return (text_box[0] >= shape[0] + CLEARANCE and text_box[1] >= shape[1] + CLEARANCE
            and text_box[2] <= shape[2] - CLEARANCE and text_box[3] <= shape[3] - CLEARANCE)


def collisions(svg):
    texts, shapes = boxes(parse(svg))
    found = []
    for i, a in enumerate(texts):
        found += [(a[4], b[4]) for b in texts[i + 1:] if overlaps(a, b)]
        found += [(a[4], shape) for shape in shapes if overlaps(a, shape) and not inside(a, shape)]
    return found


def test_the_overlap_check_detects_a_collision():
    svg = charts.svg_doc("x", "t", "d", charts.text(40, 100, "label text") + charts.rect(50, 90, 60, 12, "#000"))
    assert collisions(svg)
    svg = charts.svg_doc("y", "t", "d", charts.text(40, 100, "aaaa") + charts.text(40, 104, "bbbb"))
    assert collisions(svg)
    svg = charts.svg_doc("z", "t", "d", charts.text(40, 100, "aaaa") + charts.text(40, 140, "bbbb"))
    assert not collisions(svg)


def test_the_old_category_chart_geometry_is_caught():
    """Regression for the footnote that touched the last bar in a browser (code review round 3).

    The old chart put the last revised bar (stroke included) down to y=479 and a footnote line
    with ascenders at baseline 494; the round 2 test used a 0.72 em box with no stroke and
    no clearance, so it saw a 2-unit gap and passed. This fixture is that chart as committed.
    """
    old = (REPO / "tests/fixtures/presentation/old_outcome_by_category.svg").read_text(encoding="utf-8")
    assert collisions(old), "the stricter box model must flag the old chart"
    root = parse(old)
    bars = [e for e in root.iter() if local(e.tag) == "rect"][1:]
    assert max(float(e.get("y")) + float(e.get("height")) for e in bars) == 478


def test_no_chart_has_a_collision(rendered):
    for name, svg in rendered.items():
        assert collisions(svg) == [], name


# --- the two slide-legible diagrams ---------------------------------------------------------------

DIAGRAM_IDS = ("diagram-pipeline-overview", "diagram-trust-boundary")
DESIGN = (REPO / "openspec/changes/add-presentation-evidence/design.md").read_text(encoding="utf-8")


def svg_texts(svg):
    return [e for e in parse(svg).iter() if local(e.tag) == "text"]


def test_diagrams_follow_the_full_size_rules(rendered):
    for cid in DIAGRAM_IDS:
        svg = rendered[f"{cid}.svg"]
        root = parse(svg)
        assert root.get("viewBox") == "0 0 960 540" and root.get("role") == "img"
        assert {local(e.tag) for e in root.iter()} <= ALLOWED
        work_log.validate_svg(svg)
        assert "<script" not in svg and "href" not in svg and "url(" not in svg and "http" not in svg.replace(
            'xmlns="http://www.w3.org/2000/svg"', "")
        assert all(int(t.get("font-size")) >= charts.MIN_FONT for t in svg_texts(svg))
        assert collisions(svg) == []


def test_diagrams_are_deterministic(summary, rendered):
    assert charts.render_all(summary)["diagram-pipeline-overview.svg"] == rendered["diagram-pipeline-overview.svg"]
    assert charts.render_all(summary)["diagram-trust-boundary.svg"] == rendered["diagram-trust-boundary.svg"]


def test_diagram_text_is_at_least_7_5_pt_at_a_full_text_column():
    pt = charts.MIN_FONT * 160 / 960 / 25.4 * 72
    assert pt >= 7.5 and round(pt, 1) == 9.4


def test_every_box_and_flow_label_is_in_the_documented_mapping(rendered):
    keys = set(charts.BOX_SOURCES)
    for cid in DIAGRAM_IDS:
        texts = svg_texts(rendered[f"{cid}.svg"])
        bold = [t.text for t in texts if t.get("font-weight") == "bold" and t.get("font-size") != "26"]
        assert bold and set(bold) <= keys, (cid, set(bold) - keys)
        words = {w for t in texts for w in (t.text or "").replace(",", " ").split()}
        flows = {"pipeline": ("final submission", "grades", "record", "re-grade", "compare"),
                 "trust": ("code + case", "signed report")}["pipeline" if "pipeline" in cid else "trust"]
        for flow in flows:
            assert all(word in words for word in flow.split()), (cid, flow)
    ci = [t.text for t in svg_texts(rendered["diagram-pipeline-overview.svg"])]
    assert "CI: tests and probes on fixtures, no model API" in ci


def test_the_mapping_is_written_in_design_md_and_its_sources_exist():
    for label, sources in charts.BOX_SOURCES.items():
        assert re.search(rf"^\| (pipeline|trust) \| {re.escape(label)} \|", DESIGN, re.M), label
        assert sources
        for source in sources:
            assert (REPO / source).is_file(), (label, source)
    rows = re.findall(r"^\| (?:pipeline|trust) \| (.+?) \|", DESIGN, re.M)
    assert set(rows) == set(charts.BOX_SOURCES)


def test_diagrams_have_few_boxes_and_no_status_labels(rendered):
    for cid in DIAGRAM_IDS:
        svg = rendered[f"{cid}.svg"]
        boxes_drawn = len([e for e in parse(svg).iter() if local(e.tag) == "rect" and e.get("rx")])
        assert boxes_drawn <= 10, cid
        everything = " ".join((e.text or "") for e in parse(svg).iter()).lower()
        for word in charts.STATUS_WORDS:
            assert word not in everything, (cid, word)
    pipeline = [e for e in parse(rendered["diagram-pipeline-overview.svg"]).iter()
                if local(e.tag) == "rect" and e.get("rx") and e.get("stroke-dasharray") is None]
    assert len(pipeline) == 7


def test_diagrams_are_registered_for_the_deck_and_the_report():
    manifest = json.loads((REPO / "presentation/manifest.json").read_text(encoding="utf-8"))
    entries = {d["id"]: d for d in manifest["diagrams"]}
    assert manifest["schema_version"] == 1
    for cid in DIAGRAM_IDS:
        entry = entries[cid]
        assert entry["uses"] == ["deck", "report"] and entry["path"] == f"presentation/charts/{cid}.svg"
        assert entry["viewbox"] == "0 0 960 540" and entry["min_render_mm"] == 160 and entry["min_font_units"] == 20
        assert entry["alt"].strip() and entry["caption"].strip() and (REPO / entry["path"]).is_file()
    assert [d["id"] for d in manifest["diagrams"]][:4] == [
        "diagram-architecture-logical", "diagram-architecture-physical",
        "diagram-run-flow-activity", "diagram-run-flow-sequence"]
