"""Current-status figures and pages must agree with the status-sources file and its cited evidence.

Offline: reads only checked-in files (no network, Podman, MLflow, draw.io, or retained bundles)."""

import html
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
SVG_NS = "{http://www.w3.org/2000/svg}"
DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>")
LABEL = re.compile(r"PARTIAL: NO LIVE RUN YET|IMPLEMENTED|PENDING|EXTERNAL")
SOURCES = tomllib.loads((DOCS / "architecture_status_sources.toml").read_text(encoding="utf-8"))
COMPONENTS = SOURCES["component"]
TWINS = ["architecture_logical.md", "architecture_physical.md", "run_flow_activity.md", "run_flow_sequence.md",
         "work_log_architecture.md"]
DRAWINGS = ["architecture_logical.drawio.svg", "architecture_physical.drawio.svg", "run_flow_activity.drawio.svg",
            "run_flow_sequence.drawio.svg"]
# Phrases that only a pre-paid-phase status could contain (matched case-insensitively).
STALE = [r"no live run", r"no live (call|model|spend)", r"no live or real run", r"has not been run live",
         r"has not run\b", r"built offline only", r"no paid", r"not yet run", r"does not exist yet",
         r"only a fixture", r"no live client", r"\bunset\b", r"until the human writes",
         r"\bPENDING\b", r"NO LIVE RUN"]
# README.md and docs/demo.md also use "pending" for the work log's pending sections, so they get the run-related subset.
STALE_PROSE = [p for p in STALE if p not in (r"\bPENDING\b", r"\bunset\b")]
# (file, text that must be part of the line, why the stale phrase is fine there)
ALLOWED = [
    ("*", "reserved", "the status vocabulary: partial and pending stay defined but no component uses them"),
    ("*", "no box uses it now", "the status vocabulary"),
    ("*", "no lane uses it now", "the status vocabulary"),
    ("*", "no element uses it now", "the status vocabulary"),
    ("*", "no participant uses them now", "the status vocabulary"),
    ("*", "none is pending now", "the status vocabulary"),
    ("*", "is labelled pending in the report", "the report's own pending sections still exist as a mechanism"),
    ("README.md", 'kind = "pending"', "describes the work log's pending-section mechanism, not a component status"),
    ("run_flow_activity.md", "refuses a variant whose prompt is unset", "code semantics of the `variant_prompt` check"),
]


def read(path):
    return (REPO / path).read_text(encoding="utf-8")


def svg_root(name):
    return ET.fromstring(DOCTYPE.sub("", (DOCS / name).read_text(encoding="utf-8"), count=1))


def svg_lines(name):
    """Every rendered text, title, and desc of an SVG as separate lines."""
    return [(t.text or "").strip() for t in svg_root(name).iter() if (t.text or "").strip()]


def model_items(name):
    """(cell id, label lines) of every draw.io cell with a value."""
    payload = svg_root(name).get("content")
    model = ET.fromstring(payload).find("diagram").find("mxGraphModel")
    return [(c.get("id"), [x.strip() for x in html.unescape(c.get("value")).split("\n") if x.strip()])
            for c in model.iter("mxCell") if c.get("value")]


def figure_items():
    """(view, name text, status text) for every status-bearing box of the four drawings and the work-log figure."""
    out = []
    for name in DRAWINGS:
        for cid, lines in model_items(name):
            if lines[0].startswith("STATUS KEY"):
                continue
            found = [m for line in lines for m in LABEL.findall(line)]
            if found:
                out.append((f"{name}:{cid}", lines[0], found[-1], lines))
    svg = read("docs/work_log_architecture.svg")
    for kind, body in re.findall(r'<g class="arch-box arch-(impl|part|plan)">(.*?)</g>', svg, re.S):
        texts = [html.unescape(t) for t in re.findall(r"<text[^>]*>([^<]*)</text>", body)]
        if texts:
            out.append(("work_log_architecture.svg", " ".join(texts[1:3]), texts[0], texts))
    return out


def matches(component, head):
    for m in component["match"]:
        if (head.startswith(m[1:]) if m.startswith("^") else m in head):
            return True
    return False


@pytest.mark.parametrize("component", COMPONENTS, ids=[c["name"] for c in COMPONENTS])
def test_every_status_cites_a_committed_phrase(component):
    evidence = REPO / component["evidence"]
    assert evidence.is_file(), f"{component['name']}: {component['evidence']} is missing"
    assert component["phrase"] in evidence.read_text(encoding="utf-8"), (
        f"{component['name']}: {component['evidence']} lacks {component['phrase']!r}")


def test_the_mlflow_status_does_not_rest_on_the_superseded_sentence():
    entry = next(c for c in COMPONENTS if c["name"].startswith("MLflow"))
    assert entry["evidence"] == "docs/progress.md" and "read-only verification" not in entry["phrase"]


def test_every_figure_status_follows_the_sources_file():
    items = figure_items()
    assert len(items) > 40, "the figures yielded suspiciously few status-bearing boxes"
    wrong = []
    for view, head, status, _lines in items:
        for component in COMPONENTS:
            if component["status"] != "open" and matches(component, head) and component["status"] != status:
                wrong.append((view, head, status, component["status"], component["name"]))
    assert wrong == []


def test_no_box_uses_a_reserved_status():
    used = {c["status"] for c in COMPONENTS}
    reserved = [(view, head, status) for view, head, status, _ in figure_items()
                if status in ("PARTIAL: NO LIVE RUN YET", "PENDING") and status not in used]
    assert reserved == []


def _lines_of(path):
    if path.endswith(".drawio.svg") or path.endswith(".svg"):
        return svg_lines(Path(path).name)
    text = read(path)
    if path == "docs/progress.md":
        text = text.split("## Current status", 1)[1].split("\n## ", 1)[0]
    return text.split("\n")


SCANNED = (["docs/work_log_architecture.svg"] + [f"docs/{n}" for n in DRAWINGS + TWINS]
           + ["README.md", "docs/demo.md", "docs/progress.md"])


@pytest.mark.parametrize("path", SCANNED)
def test_no_current_status_text_claims_a_stale_status(path):
    name = Path(path).name
    bad = []
    for line in _lines_of(path):
        if any(re.search(p, line, re.I) for p in (STALE_PROSE if name in ("README.md", "demo.md") else STALE)):
            if not any(f in ("*", name) and part in line for f, part, _ in ALLOWED):
                bad.append(line[:160])
    assert bad == [], f"{path}: stale status text: {bad}"


@pytest.mark.parametrize("twin", TWINS)
def test_every_twin_states_the_completed_runs_and_the_open_interpretation(twin):
    text = read(f"docs/{twin}").lower()
    assert SOURCES["completed_runs_sentence"] in text
    for component in (c for c in COMPONENTS if c["status"] == "open"):
        assert "interpretation" in text and "still open" in text, component["name"]


def test_the_supersession_note_follows_the_original_sentence():
    text = read("docs/comparison_evidence.md")
    original = text.index("5 of the 60 traces")
    note = text.index("Superseded the same day")
    assert original < note and "60 of 60 traces read back" in text[note:]
