#!/usr/bin/env python3
"""Build and check the four-page printable HTML report.

    python scripts/build_report.py build [--require-user-text]   write report/presentation_report.html
    python scripts/build_report.py check                         offline structural, legibility, lint and budget checks
    python scripts/build_report.py measure [--pdf PATH]          headless-browser fit and printed page count

The report is one self-contained, script-free file made from presentation/report/template.html
and report.css, the evidence summary and manifest of `add-presentation-evidence`, and the
shared user text. Numbers, captions, alt text and figures come only from those inputs through a
closed set of template directives; nothing is typed into the prose. The build reads no
credential, no bundle and no ledger, and makes no network call. See docs/presentation_report.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path("presentation/report/template.html")
STYLESHEET = Path("presentation/report/report.css")
MANIFEST = Path("presentation/manifest.json")
USER_TEXT = Path("presentation/user_text.toml")
OUTPUT = Path("report/presentation_report.html")
PAGES = 4
EXIT_SKIPPED = 3

# Layout constants the stylesheet must agree with; `check` compares them with report.css.
PAGE_HEIGHT_MM = 296.0
MIN_PRINT_PT = 7.5
MIN_MM = MIN_PRINT_PT * 25.4 / 72  # 2.646 mm
HEADROOM = 0.94
CONTRAST_MIN = 4.5
SLOTS = ("motivation", "takeaways")
# A filled slot is a fixed box with hidden overflow, so its text must fit by a deterministic rule:
# greedy word wrap at SLOT_CPL characters per line (conservative: Chrome fits about 105 at 9.5 pt in
# the 177 mm text width), one line costs SLOT_LINE_MM and each paragraph break SLOT_PARA_GAP_MM,
# against the box height from report.css minus padding and border.
SLOT_CPL = 96
SLOT_LINE_MM = 4.56
SLOT_PARA_GAP_MM = 1.8
SLOT_PADDING_MM = 4.6

# Tokens with digits that the template prose may contain; whole tokens, never substrings.
DIGIT_ALLOWLIST = frozenset({"A4", "SHA-256"})

# Static height model. `calibrated_against` is empty until `measure` has been run and the
# constants below have been fitted to it; `check` refuses to pass while it is empty.
# The `measure` result the estimator was checked against (commit 3b520fa): content height used and
# body box height per page, in mm. `check` requires each static estimate to stay within
# CALIBRATION_TOLERANCE of the measured content height, so a template or stylesheet change that
# moves a page by more than that fails offline until `measure` is run again and these are updated.
MEASURED_MM = {1: (220.3, 272.8), 2: (229.3, 258.8), 3: (253.5, 258.8), 4: (232.1, 258.8)}
CALIBRATION_TOLERANCE = 0.10

BUDGETS = {
    "calibrated_against": "Chrome 157.0.8103.52, macOS arm64, 2026-11-13, commit 3b520fa (coordinator's `measure` run)",
    "body_mm": 258.8,  # usable height of a page body (page box minus padding, header, footer)
    "char_mm": 1.8,  # average character advance at body size
    "line_mm": 5.0,  # body line height
    "small_char_mm": 1.30,  # captions and footnotes
    "small_line_mm": 3.55,
    "row_mm": 4.2,  # one table row
    "block_gap_mm": 2.4,  # margin below a block
    "heading_mm": 7.5,
}

NAV_HIDE_RULE = ".screen-only"

DIRECTIVE = re.compile(r"\{\{([a-z_]+)(?::([^|}]*))?(?:\|([a-z0-9_]+))?\}\}")
FRAMING = re.compile(r"\b(improvement|breakthrough)s?\b", re.I)


class ReportError(Exception):
    """An input, template or output problem; the message is the diagnostic."""


# --- inputs -------------------------------------------------------------------


def load_work_log(root: Path):
    """Load scripts/build_work_log.py by path for its SVG validator and draw.io sanitizer."""
    path = root / "scripts" / "build_work_log.py"
    spec = importlib.util.spec_from_file_location("build_work_log", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("build_work_log", module)
    spec.loader.exec_module(module)
    return module


class Inputs:
    def __init__(self, root: Path, manifest_path: Path = MANIFEST, template_path: Path = TEMPLATE,
                 css_path: Path = STYLESHEET, user_text_path: Path | None = None):
        self.root = root
        try:
            self.manifest = json.loads((root / manifest_path).read_text(encoding="utf-8"))
            self.summary = json.loads((root / self.manifest["summary"]).read_text(encoding="utf-8"))
        except (OSError, KeyError, ValueError) as error:
            raise ReportError(f"cannot read the manifest or the summary: {error}") from None
        if self.manifest.get("schema_version") != 1:
            raise ReportError("manifest schema_version is not 1")
        self.template = (root / template_path).read_text(encoding="utf-8")
        self.css = (root / css_path).read_text(encoding="utf-8")
        user_rel = user_text_path or Path(self.manifest["user_text"]["path"])
        try:
            self.user_text = tomllib.loads((root / user_rel).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ReportError(f"cannot read the user text file {user_rel}: {error}") from None
        self.work_log = load_work_log(root)
        self.figures = {e["id"]: e for e in self.manifest["figures"]}
        self.diagrams = {e["id"]: e for e in self.manifest["diagrams"]}
        self.shots = {e["id"]: e for e in self.manifest["screenshots"]}
        self.assets = {e["id"]: e for e in self.manifest["assets"]}

    def entry(self, ident: str) -> tuple[str, dict]:
        for kind, table in (("figure", self.figures), ("diagram", self.diagrams), ("shot", self.shots)):
            if ident in table:
                return kind, table[ident]
        raise ReportError(f"unknown manifest id {ident!r}")


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def lookup(summary: dict, path: str):
    """Resolve a dotted summary path; a missing key is an error, never an empty value."""
    node = summary
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part == "last" and node:
            node = node[-1]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            raise ReportError(f"summary has no value at {path!r}")
    return node


def format_value(value, fmt: str | None, path: str) -> str:
    """The closed format set: int, id, short, count, chf, chf4, ratio, pct, ratiopct, ms, text."""
    if fmt in ("ratio", "pct", "ratiopct"):
        if not (isinstance(value, dict) and {"count", "of", "rate"} <= set(value)):
            raise ReportError(f"{path!r}: format {fmt!r} needs an object with count, of and rate")
        ratio = f"{value['count']}/{value['of']}"
        pct = f"{value['rate'] * 100:.1f}%"
        return {"ratio": ratio, "pct": pct, "ratiopct": f"{ratio} ({pct})"}[fmt]
    if fmt == "count":
        if not isinstance(value, (dict, list)):
            raise ReportError(f"{path!r}: format 'count' needs an object or a list")
        return str(len(value))
    if isinstance(value, (dict, list)):
        raise ReportError(f"{path!r} is not a single value")
    if fmt in (None, "text", "id"):
        return str(value)
    if fmt == "short":
        return str(value)[:7]
    if fmt == "int":
        return f"{int(value)}"
    if fmt == "ms":
        return f"{round(float(value))}"
    if fmt == "chf":
        return f"{value}"
    if fmt == "chf4":
        return f"{float(value):.4f}"
    raise ReportError(f"unknown format {fmt!r}")


def plain(markdown: str) -> str:
    """Strip the Markdown of a quoted document line to readable text."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"^\s*(?:-|\d+\.)\s+", "", text.strip())


# --- rendering ----------------------------------------------------------------


class Numbers:
    """`Figure N` and `Table N` by order of first appearance in the template."""

    def __init__(self, template: str, inputs: Inputs):
        self.labels: dict[str, str] = {}
        figure = table = 0
        for kind, arg, _ in DIRECTIVE.findall(template):
            if kind in ("fig", "shot") and arg not in self.labels:
                inputs.entry(arg)
                figure += 1
                self.labels[arg] = f"Figure {figure}"
            elif kind == "table" and arg not in self.labels:
                if arg not in TABLES:
                    raise ReportError(f"unknown table {arg!r}")
                table += 1
                self.labels[arg] = f"Table {table}"

    def ref(self, ident: str) -> str:
        if ident not in self.labels:
            raise ReportError(f"reference to {ident!r}, which is not placed in the report")
        return self.labels[ident]


def data_uri(path: Path, media: str) -> str:
    return f"data:{media};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def svg_for_inline(inputs: Inputs, kind: str, entry: dict) -> tuple[str, float]:
    """Validated inline SVG and its aspect ratio (height over width)."""
    text = (inputs.root / entry["path"]).read_text(encoding="utf-8")
    wl = inputs.work_log
    try:
        if kind == "diagram" and entry["path"].endswith(".drawio.svg"):
            markup = wl.sanitize_drawio_svg(text, entry["id"], entry["caption"], entry["alt"])
        else:
            markup = wl.validate_svg(text)
    except wl.WorkLogError as error:
        raise ReportError(f"{entry['id']}: {error}") from None
    root_tag = re.match(r"<svg\b[^>]*>", markup)
    if not root_tag:
        raise ReportError(f"{entry['id']}: no svg root")
    tag = root_tag.group(0)
    view = re.search(r'viewBox="([^"]+)"', tag)
    if view:
        box = [float(v) for v in view.group(1).split()]
    else:
        width = float(re.search(r'\bwidth="([\d.]+)', tag).group(1))
        height = float(re.search(r'\bheight="([\d.]+)', tag).group(1))
        box = [0, 0, width, height]
    new_tag = re.sub(r'\s(?:width|height)="[^"]*"', "", tag)
    if not view:
        new_tag = new_tag[:-1] + f' viewBox="0 0 {box[2]:g} {box[3]:g}">'
    markup = markup.replace(tag, new_tag, 1)
    return markup, box[3] / box[2]


def render_figure(inputs: Inputs, numbers: Numbers, ident: str) -> str:
    kind, entry = inputs.entry(ident)
    if kind == "shot":
        return render_shot(inputs, numbers, entry)
    markup, aspect = svg_for_inline(inputs, kind, entry)
    variant = entry.get("variant") or ("diagram" if kind == "diagram" else "full")
    css_class = {"compact": "fig-compact", "full": "fig-full", "diagram": f"fig-{entry.get('role', 'diagram')}"}[variant]
    sources = entry.get("source_keys")
    source = f'<span class="src">Source: {esc(", ".join(sources))}.</span>' if sources else ""
    label = numbers.ref(ident)
    return (
        f'<figure class="fig {css_class}" id="fig-{esc(ident)}" data-evidence="manifest" '
        f'data-est-aspect="{aspect:.4f}" data-est-class="{css_class}" data-est-caption="{len(entry["caption"]) + len(" ".join(sources or []))}">'
        f'<div class="figbox">{markup}</div>'
        f'<figcaption><b>{label}.</b> {esc(entry["caption"])} {source}</figcaption></figure>'
    )


def render_shot(inputs: Inputs, numbers: Numbers, entry: dict) -> str:
    label = numbers.ref(entry["id"])
    path = inputs.root / entry["path"]
    if entry.get("status") == "present" and path.is_file():
        body = (f'<img src="{data_uri(path, "image/png")}" alt="{esc(entry["alt"])}">')
        state = "present"
    else:
        body = (f'<div class="ph ph-shot">Screenshot pending (owner: {esc(entry["owner"])}): '
                f'{esc(entry["shows"])}.</div>')
        state = "pending"
    return (
        f'<figure class="fig fig-shot" id="fig-{esc(entry["id"])}" data-evidence="manifest" data-shot="{state}" '
        f'data-est-aspect="0.5625" data-est-class="fig-shot" data-est-caption="{len(entry["caption"])}">'
        f'<div class="figbox">{body}</div><figcaption><b>{label}.</b> {esc(entry["caption"])}</figcaption></figure>'
    )


def render_logo(inputs: Inputs) -> str:
    asset = inputs.assets["zhaw-logo"]
    path = inputs.root / asset["path"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != asset["sha256"]:
        raise ReportError("the logo does not match the SHA-256 recorded in the manifest")
    return f'<img class="logo" src="{data_uri(path, "image/jpeg")}" alt="{esc(asset["alt"])}">'


def render_title(inputs: Inputs, field: str) -> str:
    title = inputs.manifest["title"]
    if field not in {"author", "course", "date", "headline"}:
        raise ReportError(f"unknown title field {field!r}")
    if field == "date" and not title.get("date"):
        return f'<span class="ph ph-inline" data-placeholder="date">{esc(title["date_placeholder"])}</span>'
    return esc(title[field])


def user_slot_state(inputs: Inputs, slot: str) -> str:
    try:
        return inputs.user_text[slot]["report"]
    except KeyError:
        raise ReportError(f"user text has no [{slot}] report key") from None


def render_user(inputs: Inputs, slot: str) -> str:
    if slot not in SLOTS:
        raise ReportError(f"unknown user slot {slot!r}")
    text = user_slot_state(inputs, slot).strip()
    if not text:
        return (f'<div class="slot slot-{slot} slot-empty ph" data-slot="{slot}" data-placeholder="{slot}" data-est-kind="slot">'
                f'<b>YOUR TEXT HERE ({slot}).</b> Write the {slot} in the <code>report</code> key of '
                f'<code>[{slot}]</code> in <code>presentation/user_text.toml</code>; this box is a placeholder.</div>')
    paragraphs = "".join(f"<p>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", text) if p.strip())
    return f'<div class="slot slot-{slot} slot-filled" data-slot="{slot}" data-est-kind="slot">{paragraphs}</div>'


def doc_row(summary: dict, field: str) -> dict:
    for row in summary["documents"]:
        if row["field"] == field:
            return row
    raise ReportError(f"summary has no document row {field!r}")


def render_limits(inputs: Inputs) -> str:
    summary = inputs.summary
    items = []
    for index, label in enumerate(summary["limits"]["items"]):
        row = doc_row(summary, f"limit.{index}")
        items.append(f'<li><q class="quoted" data-source="{esc(row["file"])}">{esc(plain(row["quote"]))}</q></li>')
        if not label:
            raise ReportError(f"limit {index} has no label")
    non_claim = doc_row(summary, "non_claim")
    return (
        f'<ol class="limits">{"".join(items)}</ol>'
        f'<p class="nonclaim"><q class="quoted" data-source="{esc(non_claim["file"])}">{esc(summary["limits"]["statement"])}</q></p>'
    )


def render_failures(inputs: Inputs) -> str:
    """Failed trials per label and variant, iterated from the summary so no label can be omitted."""
    parts = []
    for variant in ("baseline", "revised"):
        labels = inputs.summary["comparison"][variant]["failure_labels"]
        listed = ", ".join(f"{esc(label)} {esc(count)}" for label, count in labels.items()) or "none"
        parts.append(f"{variant}: {listed}")
    return "; ".join(parts)


def render_delta(inputs: Inputs) -> str:
    delta = inputs.summary["comparison"]["delta"]
    gained = ", ".join(esc(t) for t in delta["gained_tasks"]) or "none"
    regressed = ", ".join(esc(t) for t in delta["regressed_tasks"]) or "none"
    return f"gained {gained}; regressed {regressed}; unchanged {len(delta['unchanged_tasks'])} tasks"


def render_evidence(inputs: Inputs) -> str:
    runs = inputs.summary["provenance"]["runs"]
    rows = []
    for key, label in (("baseline", "Baseline run"), ("revised", "Revised run"), ("smoke_forced_pass", "Forced passing smoke")):
        run = runs[key]
        mlflow = f'<br>MLflow run <code>{esc(run["mlflow_run_id"])}</code>' if run.get("mlflow_run_id") else ""
        prompt = (f'<br>Prompt <code>{esc(run["prompt"]["version"])}</code> SHA-256 <code>{esc(run["prompt"]["sha256"])}</code>'
                  if run.get("prompt") else "")
        rows.append(
            f'<tr><th scope="row">{label}</th><td><code>{esc(run["run_id"])}</code>{mlflow}{prompt}<br>'
            f'Bundle digest (SHA-256) <code class="digest">{esc(run["bundle_digest"])}</code></td></tr>'
        )
    return (f'<table class="dtab evidence" data-est-rows="{len(rows) * 3}"><tbody>{"".join(rows)}</tbody></table>')


# Tables replace the figures that are not charted in the report (decision D1). Each pairs a
# manifest id (whose caption it shows) with a function of the summary.
def _cells(*cells: str, head: bool = False) -> str:
    tag = "th" if head else "td"
    return "<tr>" + "".join(f'<{tag}{" scope=\"col\"" if head else ""}>{c}</{tag}>' for c in cells) + "</tr>"


def table_per_task(summary: dict) -> tuple[str, int]:
    base, rev = summary["comparison"]["baseline"]["per_task"], summary["comparison"]["revised"]["per_task"]
    delta = summary["comparison"]["delta"]
    rows = [_cells("Task", "Baseline", "Revised", head=True)]
    for name in base:
        mark = " (gained)" if name in delta["gained_tasks"] else " (regressed)" if name in delta["regressed_tasks"] else ""
        rows.append(_cells(esc(name) + mark, f"{base[name]['succeeded']}/{base[name]['trials']}", f"{rev[name]['succeeded']}/{rev[name]['trials']}"))
    return "".join(rows), len(rows)


def table_resources(summary: dict) -> tuple[str, int]:
    eff = summary["efficiency"]
    columns = [
        ("Model calls", lambda e: e["model_calls"]),
        ("Tool attempts", lambda e: e["tool_attempts"]),
        ("Revisions", lambda e: e["revisions"]),
        ("Prompt tokens", lambda e: e["tokens"]["prompt_tokens"]),
        ("Completion tokens", lambda e: e["tokens"]["completion_tokens"]),
        ("Latency total (ms)", lambda e: format_value(e["model_latency_ms"]["total"], "ms", "latency")),
        ("Charged (CHF)", lambda e: f"{e['cost']['charged_chf']:.6f}"),
        ("Reserved (CHF)", lambda e: f"{e['cost']['reserved_before_send_chf']:.4f}"),
    ]
    head = _cells("", *[name for name, _ in columns], head=True)
    rows = [_cells(f"<b>{label}</b>", *[esc(fn(eff[key])) for _, fn in columns]) for key, label in (("baseline", "Baseline"), ("revised", "Revised"))]
    return head + "".join(rows), 3


def table_ci(summary: dict) -> tuple[str, int]:
    runs = summary["engineering"]["ci"]["runs"]
    head = _cells("Run", "Commit", "offline", "offline tests", "podman", "podman tests", "podman failed", head=True)
    rows = [_cells(f"<code>{esc(r['run'])}</code>", f"<code>{esc(r.get('commit', 'not recorded'))}</code>", esc(r.get("offline", "-")),
                   esc(r.get("offline_tests", "-")), esc(r.get("podman", "-")), esc(r.get("podman_tests", "-")),
                   esc(r.get("podman_failed", "-"))) for r in runs]
    return head + "".join(rows), len(rows) + 1


def table_changes(summary: dict) -> tuple[str, int]:
    by_date = summary["engineering"]["changes_archived"]["by_date"]
    head = _cells("Archived on", *by_date, head=True)
    return head + _cells("Changes", *[esc(v) for v in by_date.values()]), 2


TABLES = {
    "per-task": ("outcome-by-task", table_per_task, None, None),
    "resources": ("efficiency-latency", table_resources,
                  "Resources per prompt: model calls, tool attempts, revisions, tokens, model latency and cost.",
                  ["efficiency.baseline", "efficiency.revised"]),
    "ci-runs": ("engineering-ci", table_ci, None, None),
    "changes": ("engineering-changes", table_changes, None, None),
}


def render_table(inputs: Inputs, numbers: Numbers, name: str) -> str:
    if name not in TABLES:
        raise ReportError(f"unknown table {name!r}")
    caption_id, fn, title, source_keys = TABLES[name]
    body, rows = fn(inputs.summary)
    entry = inputs.figures[caption_id]
    caption = entry["caption"]
    if title:
        # the table shows more than its manifest figure: its own title, then the manifest's
        # measurement note (everything after the first sentence) unchanged
        caption = f"{title} {caption.split('. ', 1)[1] if '. ' in caption else ''}".strip()
    sources = ", ".join(source_keys or entry["source_keys"])
    return (
        f'<figure class="tab" id="tab-{name}" data-evidence="manifest" data-est-rows="{rows}" data-est-caption="{len(caption) + len(sources)}">'
        f'<figcaption><b>{numbers.ref(name)}.</b> {esc(caption)} <span class="src">Source: {esc(sources)}.</span></figcaption>'
        f'<table class="dtab"><tbody>{body}</tbody></table></figure>'
    )


def render_nav() -> str:
    links = " ".join(f'<a href="#page-{n}">Page {n}</a>' for n in range(1, PAGES + 1))
    return f'<nav class="screen-only" aria-label="Report pages">{links}</nav>'


def render_footer(n: int) -> str:
    prev_next = []
    if n > 1:
        prev_next.append(f'<a href="#page-{n - 1}">previous</a>')
    if n < PAGES:
        prev_next.append(f'<a href="#page-{n + 1}">next</a>')
    return (f'<footer class="pfoot"><span class="screen-only">{" | ".join(prev_next)}</span>'
            f'<span class="pnum">Page {n} / {PAGES}</span></footer>')


def sibling_note(root: Path, name: str) -> str:
    """A non-fatal note for generated, Git-ignored siblings."""
    return "" if (root / "report" / name).is_file() else " (not built here yet)"


def render_link(inputs: Inputs, target: str) -> str:
    allowed = {"index": ("index.html", "work log", "scripts/build_work_log.py"),
               "demo": ("demo.html", "recorded demo player", "scripts/record_demo.py build-player")}
    if target not in allowed:
        raise ReportError(f"unknown link {target!r}")
    name, label, script = allowed[target]
    note = sibling_note(inputs.root, name)
    return (f'<a href="{name}">{label}</a> <code>report/{name}</code>'
            f'<span class="screen-only">{esc(note)}{"; build it with " + script if note else ""}</span>')


def substitute(inputs: Inputs, numbers: Numbers, template: str) -> str:
    def replace(match: re.Match) -> str:
        kind, arg, fmt = match.group(1), match.group(2), match.group(3)
        if kind == "val":
            return esc(format_value(lookup(inputs.summary, arg), fmt, arg))
        if kind == "fig":
            return render_figure(inputs, numbers, arg)
        if kind == "shot":
            return render_figure(inputs, numbers, arg)
        if kind == "table":
            return render_table(inputs, numbers, arg)
        if kind == "ref":
            return f'<a class="ref" href="#{"tab" if arg in TABLES else "fig"}-{esc(arg)}">{numbers.ref(arg)}</a>'
        if kind == "logo":
            return render_logo(inputs)
        if kind == "title":
            return render_title(inputs, arg)
        if kind == "user":
            return render_user(inputs, arg)
        if kind == "limits":
            return render_limits(inputs)
        if kind == "failures":
            return render_failures(inputs)
        if kind == "delta":
            return render_delta(inputs)
        if kind == "evidence_table":
            return render_evidence(inputs)
        if kind == "nav":
            return render_nav()
        if kind == "footer":
            return render_footer(int(arg))
        if kind == "link":
            return render_link(inputs, arg)
        raise ReportError(f"unknown directive {{{{{kind}}}}}")

    return DIRECTIVE.sub(replace, template)


CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"


def build_html(inputs: Inputs) -> str:
    template = re.sub(r"<!--.*?-->\s*", "", inputs.template, flags=re.S)
    numbers = Numbers(template, inputs)
    body = substitute(inputs, numbers, template)
    title = f'{inputs.manifest["title"]["headline"]} (report)'
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        f"<title>{esc(title)}</title><style>\n{inputs.css}</style></head>\n<body>\n{body}</body></html>\n"
    )


# --- parsing and checks -------------------------------------------------------


class Node:
    def __init__(self, tag: str, attrs: dict, parent: "Node | None"):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: list[Node] = []
        self.text: list[str] = []

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def visible_text(self, skip=lambda n: False) -> str:
        if skip(self):
            return ""
        parts = list(self.text)
        for child in self.children:
            parts.append(child.visible_text(skip))
        return " ".join(p for p in parts if p)


VOID = {"meta", "img", "br", "hr", "link", "input", "path", "rect", "use", "circle", "line"}


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, dict(attrs), self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent

    def handle_data(self, data):
        if data.strip():
            self.current.text.append(data.strip())


def parse(text: str) -> Node:
    parser = Parser()
    parser.feed(text)
    return parser.root


def rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(value: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def css_blocks(css: str) -> list[tuple[str, str]]:
    """Top-level (selector-or-at-rule, body) pairs, with @media bodies kept as one block."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks, depth, start, head = [], 0, 0, ""
    for index, char in enumerate(css):
        if char == "{":
            if depth == 0:
                head = css[start:index].strip()
                start = index + 1
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                blocks.append((head, css[start:index]))
                start = index + 1
    return blocks


def css_vars(css: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;}]+)", css))


def mm_var(css: str, name: str) -> float:
    value = css_vars(css).get(name)
    match = re.fullmatch(r"\s*([\d.]+)mm\s*", value or "")
    if not match:
        raise ReportError(f"report.css must define {name} in mm")
    return float(match.group(1))


ZERO = re.compile(r"0(?:mm|px|pt)?(?:\s+0(?:mm|px|pt)?)*")


def print_declaration_problems(head: str, body: str) -> list[str]:
    """Only declarations that cannot move a page: colour, shadow, and zeroed spacing on body and main."""
    problems = []
    for declaration in filter(None, (d.strip() for d in body.split(";"))):
        prop, _, value = declaration.partition(":")
        prop, value = prop.strip(), value.strip()
        if prop in {"print-color-adjust", "-webkit-print-color-adjust"} or (prop == "background" and head == "body"):
            continue
        if head == ".page" and prop == "box-shadow" and value == "none":
            continue
        if head in {"body", "main"} and prop in {"margin", "padding", "gap", "row-gap", "column-gap"} and ZERO.fullmatch(value):
            continue
        problems.append(f"print block rule {head!r} may not change geometry or type ({prop}: {value})")
    return problems


def check_css(css: str) -> list[str]:
    problems = []
    for rule in ("@page", "break-after: page", "296mm"):
        if rule not in css:
            problems.append(f"report.css lacks {rule!r}")
    if not re.search(r"@page\s*\{[^}]*size:\s*A4[^}]*margin:\s*0", css.replace("\n", " ")):
        problems.append("report.css must declare @page { size: A4; margin: 0 }")
    for head, body in css_blocks(css):
        if head.startswith("@media") and "print" in head:
            for inner_head, inner_body in css_blocks(body):
                if inner_head not in {".screen-only", "body", "main", ".page"}:
                    problems.append(f"print block rule {inner_head!r} may not change layout")
                if inner_head == ".screen-only" and "display: none" not in inner_body:
                    problems.append("print block must hide .screen-only")
                if inner_head != ".screen-only":
                    problems += print_declaration_problems(inner_head, inner_body)
    if not any(h.startswith("@media") and "print" in h and ".screen-only" in b for h, b in css_blocks(css)):
        problems.append("report.css has no print rule hiding .screen-only")
    # font sizes: only pt, never below the floor
    shorthand = re.findall(r"(?<![-\w])font\s*:\s*(?:(?:italic|bold|normal|\d{3})\s+)*([\d.]+[a-z%]*)", css)
    for size in re.findall(r"font-size\s*:\s*([^;}]+)", css) + shorthand:
        match = re.fullmatch(r"\s*([\d.]+)pt\s*", size)
        if not match:
            problems.append(f"font-size {size.strip()!r} must be in pt")
        elif float(match.group(1)) < MIN_PRINT_PT:
            problems.append(f"font-size {size.strip()} is below {MIN_PRINT_PT} pt")
    variables = css_vars(css)
    background = [variables[v].strip() for v in variables if v.startswith("--bg")]
    for name, value in variables.items():
        if name.startswith("--text"):
            value = value.strip()
            if not re.fullmatch(r"#[0-9a-fA-F]{3,6}", value):
                problems.append(f"{name} must be a hex colour")
                continue
            for bg in background:
                if contrast(value, bg) < CONTRAST_MIN:
                    problems.append(f"{name} {value} on {bg} has contrast {contrast(value, bg):.2f}, below {CONTRAST_MIN}")
    for colour in re.findall(r"(?<![-\w])color\s*:\s*([^;}]+)", css):
        if not colour.strip().startswith("var(--text"):
            problems.append(f"text colour {colour.strip()!r} must use a --text token")
    return problems


def svg_min_font(markup: str) -> float | None:
    sizes = [float(s) for s in re.findall(r'font-size="([\d.]+)"', markup)]
    return min(sizes) if sizes else None


def check_legibility(inputs: Inputs, root: Node, css: str) -> tuple[list[str], list[str]]:
    problems, warnings = [], []
    for node in root.walk():
        if node.tag != "figure" or "data-est-class" not in node.attrs or node.attrs["data-est-class"] == "fig-shot":
            continue
        ident = node.attrs["id"].removeprefix("fig-")
        kind, entry = inputs.entry(ident)
        markup, _ = svg_for_inline(inputs, kind, entry)
        cls = node.attrs["data-est-class"]
        width = mm_var(css, {"fig-compact": "--w-compact", "fig-full": "--w-full"}.get(cls, f"--w-{cls.removeprefix('fig-')}"))
        view = [float(v) for v in re.search(r'viewBox="([^"]+)"', markup).group(1).split()]
        fonts = [float(v) for v in re.findall(r'font-size[=:]\s*"?([\d.]+)(?:px)?', markup)]
        smallest = min(fonts) if fonts else None
        if entry.get("min_font_units") and smallest is not None and smallest < entry["min_font_units"]:
            problems.append(f"{ident}: smallest font {smallest} units is below the manifest min_font_units")
        if smallest is None:
            problems.append(f"{ident}: no font size found, so legibility cannot be shown")
            continue
        mm = smallest * width / view[2]
        if mm < MIN_MM - 1e-9:
            problems.append(f"{ident}: smallest text {smallest:g} units at {width:g} mm wide prints {mm * 72 / 25.4:.1f} pt, below {MIN_PRINT_PT} pt")
    return problems, warnings


def visible(node: Node) -> str:
    return node.visible_text(skip=lambda n: n.tag in {"style", "title", "svg", "script"})


def check_digits(template: str) -> list[str]:
    prose = re.sub(r"<!--.*?-->", " ", template, flags=re.S)
    prose = DIRECTIVE.sub(" ", prose)
    root = parse(prose)
    text = visible(root)
    problems = []
    for token in re.findall(r"[\w][\w\-]*", text):
        if re.search(r"\d", token) and token not in DIGIT_ALLOWLIST:
            problems.append(f"template prose contains the number {token!r}; use a {{{{val:...}}}} directive")
    return sorted(set(problems))


def check_framing(output: Node, template: str) -> list[str]:
    problems = []
    if re.search(r'class="[^"]*\bquoted\b|data-evidence', template):
        problems.append("the template may not write the quotation or evidence markers itself")

    def skip(n: Node) -> bool:
        return n.tag in {"style", "title"} or "quoted" in n.classes() or "data-evidence" in n.attrs

    for node in output.walk():
        if node.tag == "div" and "slot" in node.classes():
            for hit in FRAMING.findall(node.visible_text(skip)):
                problems.append(f"user slot {node.attrs.get('data-slot')!r} uses the word {hit!r}; say 'no measured gain' instead")
    text = output.visible_text(lambda n: skip(n) or ("slot" in n.classes()))
    for hit in FRAMING.findall(text):
        problems.append(f"the report uses {hit!r} outside a quoted element")
    return problems


def check_structure(html_text: str, root: Node) -> list[str]:
    problems = []
    if not html_text.startswith("<!doctype html>"):
        problems.append("missing doctype")
    if not re.search(r'<html lang="en"', html_text):
        problems.append("missing lang=en")
    if not re.search(r"<title>[^<]+</title>", html_text):
        problems.append("missing title")
    if re.search(r"<(script|iframe|object|embed|form|link|base)\b", html_text, re.I):
        problems.append("contains a tag that could run or load a resource")
    if re.search(r"\son[a-z]+\s*=", html_text, re.I):
        problems.append("contains an event-handler attribute")
    if re.search(r"(?:src|href)=\"(?:https?:)?//", html_text) or re.search(r"url\((?!#|data:)", html_text):
        problems.append("contains an external reference")
    pages = [n for n in root.walk() if n.tag == "section" and "page" in n.classes()]
    if [p.attrs.get("id") for p in pages] != [f"page-{n}" for n in range(1, PAGES + 1)]:
        problems.append(f"expected exactly {PAGES} page sections page-1..page-{PAGES}")
    for page in pages:
        if not any(n.tag in {"h1", "h2"} for n in page.walk()):
            problems.append(f"{page.attrs.get('id')} has no heading")
    for node in root.walk():
        if node.tag == "nav" and "screen-only" not in node.classes():
            problems.append("a nav element is not marked screen-only")
        if node.tag == "main":
            for descendant in node.walk():
                if descendant.tag == "nav":
                    problems.append("nav must be outside main")
    ids = re.findall(r'\bid="([^"]+)"', html_text)
    problems += [f"duplicate id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for target in re.findall(r'href="#([^"]+)"', html_text):
        if target not in ids:
            problems.append(f"link to missing anchor #{target}")
    labels = re.findall(r"<b>(Figure|Table) (\d+)\.</b>", html_text)
    for word in ("Figure", "Table"):
        numbers = [int(n) for w, n in labels if w == word]
        if numbers != list(range(1, len(numbers) + 1)):
            problems.append(f"{word} numbers are not contiguous in document order: {numbers}")
    return problems


def wrap_lines(paragraph: str) -> int:
    """Lines needed by a paragraph under greedy word wrap at SLOT_CPL characters."""
    lines, width = 1, 0
    for word in paragraph.split():
        while len(word) > SLOT_CPL:  # a very long word breaks across lines
            lines += 1 if width else 0
            word, width = word[SLOT_CPL:], 0
        if width and width + 1 + len(word) > SLOT_CPL:
            lines, width = lines + 1, len(word)
        else:
            width += (1 if width else 0) + len(word)
    return lines


def slot_fit(text: str, box_mm: float) -> tuple[int, float, float, int]:
    """(lines, needed mm, capacity mm, lines one paragraph could use) for a slot text."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    lines = sum(wrap_lines(p) for p in paragraphs)
    needed = lines * SLOT_LINE_MM + max(len(paragraphs) - 1, 0) * SLOT_PARA_GAP_MM
    capacity = box_mm - SLOT_PADDING_MM
    return lines, needed, capacity, int(capacity // SLOT_LINE_MM)


def slot_limits(css: str, slot: str) -> str:
    """The limit as the user sees it, from the box height."""
    _, _, capacity, one = slot_fit("x", mm_var(css, f"--slot-h-{slot}"))
    return f"{one} lines of about {SLOT_CPL} characters (about {one * SLOT_CPL} characters in one paragraph; each paragraph break costs part of a line)"


def check_slots(inputs: Inputs) -> list[str]:
    problems = []
    for slot in SLOTS:
        text = user_slot_state(inputs, slot).strip()
        if not text:
            continue
        box = mm_var(inputs.css, f"--slot-h-{slot}")
        lines, needed, capacity, _ = slot_fit(text, box)
        if needed > capacity + 1e-9:
            problems.append(
                f"user text {slot!r} does not fit its box: it needs {lines} lines ({needed:.1f} mm) and the box holds "
                f"{capacity:.1f} mm; the limit is {slot_limits(inputs.css, slot)}; shorten it, because text beyond the box would be cut off")
    return problems


def placeholders(root: Node) -> list[str]:
    found = []
    for node in root.walk():
        if "data-placeholder" in node.attrs:
            found.append(f"user text {node.attrs['data-placeholder']}" if node.attrs["data-placeholder"] != "date" else "date")
        if node.attrs.get("data-shot") == "pending":
            found.append(f"screenshot {node.attrs['id'].removeprefix('fig-')}")
    return found


def estimate_page_mm(page: Node, css: str, budgets: dict) -> float:
    """A static height estimate: exact figure heights, fixed slots, table rows, prose by characters."""
    def figure_mm(node: Node) -> float:
        cls = node.attrs["data-est-class"]
        width = mm_var(css, {"fig-compact": "--w-compact", "fig-full": "--w-full"}.get(cls, f"--w-{cls.removeprefix('fig-')}"))
        caption = math.ceil(int(node.attrs["data-est-caption"]) * budgets["small_char_mm"] / width) * budgets["small_line_mm"]
        return width * float(node.attrs["data-est-aspect"]) + caption + budgets["block_gap_mm"]

    inline = {"a", "b", "code", "q", "span", "i", "em", "strong", "br"}

    def inline_text(node: Node) -> str:
        parts = list(node.text)
        for child in node.children:
            if child.tag in inline and "screen-only" not in child.classes():
                parts.append(inline_text(child))
        return " ".join(parts)

    def prose_mm(node: Node, width: float, scale: float = 1.0) -> float:
        total = 0.0
        text = inline_text(node)
        if text:
            lines = math.ceil(len(text) * budgets["char_mm"] * scale / width)
            total += lines * budgets["line_mm"] * scale + budgets["block_gap_mm"] * (node.tag in {"p", "li"})
        for child in node.children:
            if child.tag not in inline:
                total += height(child, width) if scale == 1.0 else prose_mm(child, width, scale)
        return total

    def height_plain(node: Node, width: float, scale: float) -> float:
        return prose_mm(node, width, scale)

    def height(node: Node, width: float) -> float:
        if node.tag in {"svg", "style", "nav"} or "screen-only" in node.classes():
            return 0.0
        if node.tag == "footer":
            return 0.0
        if node.tag == "figure" and "data-est-class" in node.attrs:
            return figure_mm(node)
        if node.tag == "figure" and "data-est-rows" in node.attrs:
            caption = math.ceil(int(node.attrs["data-est-caption"]) * budgets["small_char_mm"] / width) * budgets["small_line_mm"]
            return int(node.attrs["data-est-rows"]) * budgets["row_mm"] + caption + budgets["block_gap_mm"]
        if node.tag == "table" and "data-est-rows" in node.attrs:
            return int(node.attrs["data-est-rows"]) * budgets["row_mm"]
        if node.attrs.get("data-est-kind") == "slot":
            return mm_var(css, f"--slot-h-{node.attrs['data-slot']}") + budgets["block_gap_mm"]
        if node.tag in {"h1", "h2", "h3"}:
            return budgets["heading_mm"]
        if "side" in node.classes():
            return prose_mm(node, mm_var(css, "--w-side"))
        if "figrow" in node.classes():
            return max((height(k, width) for k in node.children), default=0.0)
        if node.classes() & {"cols2", "chartgrid"}:
            kids = [c for c in node.children if height(c, width / 2) or c.tag]
            rows = [kids[i:i + 2] for i in range(0, len(kids), 2)]
            return sum(max(height(k, width / 2) for k in row) for row in rows)
        if "limits" in node.classes():
            return height_plain(node, width / 2, 0.83) / 2
        if "docs" in node.classes():
            return height_plain(node, width / 3, 0.86) / 3
        if "stats" in node.classes():
            return mm_var(css, "--stats-h") + budgets["block_gap_mm"]
        return prose_mm(node, width)

    body = [c for c in page.children if "pbody" in c.classes()]
    inner = body[0] if body else page
    return sum(height(child, mm_var(css, "--page-w")) for child in inner.children) + 0.0


def estimates(inputs: Inputs, root: Node) -> list[float]:
    pages = [n for n in root.walk() if n.tag == "section" and "page" in n.classes()]
    return [estimate_page_mm(p, inputs.css, BUDGETS) for p in pages]


def run_checks(inputs: Inputs, html_text: str | None = None) -> tuple[list[str], list[str], list[str]]:
    html_text = html_text or build_html(inputs)
    root = parse(html_text)
    problems = check_structure(html_text, root) + check_css(inputs.css) + check_digits(inputs.template)
    problems += check_framing(root, inputs.template) + check_slots(inputs)
    legibility, warnings = check_legibility(inputs, root, inputs.css)
    problems += legibility
    if not BUDGETS["calibrated_against"]:
        problems.append("budgets not calibrated: run `build_report.py measure` and fill BUDGETS['calibrated_against']")
    else:
        if BUDGETS["calibrated_against"].startswith("UNMEASURED"):
            warnings.append("budgets are an unmeasured estimate; only `build_report.py measure` shows the printed fit")
        for index, used in enumerate(estimates(inputs, root), start=1):
            measured, body = MEASURED_MM[index]
            if used > body * HEADROOM:
                problems.append(f"page-{index}: static estimate {used:.0f} mm exceeds {HEADROOM:.0%} of the {body:.0f} mm body")
            if abs(used - measured) > measured * CALIBRATION_TOLERANCE:
                problems.append(f"page-{index}: static estimate {used:.0f} mm differs from the measured {measured:.0f} mm by more than "
                                f"{CALIBRATION_TOLERANCE:.0%}; run `build_report.py measure` and update MEASURED_MM and BUDGETS")
    return problems, warnings, placeholders(root)


# --- measure ------------------------------------------------------------------

MEASURE_SCRIPT = """<script>
window.addEventListener('load', function () {
  var out = [];
  document.querySelectorAll('section.page').forEach(function (p) {
    var b = p.querySelector('.pbody') || p;
    var top = b.getBoundingClientRect().top, bottom = top;
    Array.prototype.forEach.call(b.children, function (c) {
      var r = c.getBoundingClientRect(), m = parseFloat(getComputedStyle(c).marginBottom) || 0;
      bottom = Math.max(bottom, r.bottom + m);
    });
    var clipped = [];
    p.querySelectorAll('.slot, .figbox').forEach(function (e) {
      if (e.scrollHeight > e.clientHeight + 1) {
        var fig = e.closest('figure');
        clipped.push({name: e.dataset.slot ? 'user text ' + e.dataset.slot : (fig ? fig.id : 'box'), over: e.scrollHeight - e.clientHeight});
      }
    });
    out.push({id: p.id, clipped: clipped, scroll: p.scrollHeight, client: p.clientHeight,
              bodyScroll: b.scrollHeight, bodyClient: b.clientHeight, used: bottom - top,
              ppx: p.getBoundingClientRect().height});
  });
  var pre = document.createElement('pre'); pre.id = 'measure-result'; pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script>"""

BROWSER_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)


def find_browser(explicit: str | None) -> str | None:
    """An explicit path (argument or $REPORT_BROWSER) must exist; it is never silently replaced."""
    requested = explicit or os.environ.get("REPORT_BROWSER")
    if requested:
        if Path(requested).is_file() or shutil.which(requested):
            return requested
        raise ReportError(f"browser {requested!r} not found")
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file() or shutil.which(candidate):
            return candidate
    return None


def count_pdf_pages(data: bytes) -> int:
    """Page count from the page tree; raises ReportError when it cannot be determined."""
    text = data.decode("latin-1")
    leaves = len(re.findall(r"/Type\s*/Page\b", text))
    counts = [int(m) for m in re.findall(r"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", text)]
    counts += [int(m) for m in re.findall(r"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", text)]
    root_count = max(counts) if counts else None
    if root_count is None or leaves == 0 or leaves != root_count:
        raise ReportError(f"could not determine page count (page objects {leaves}, root count {root_count})")
    return leaves


def parse_measurements(dom: str) -> list[dict]:
    match = re.search(r'<pre id="measure-result">(.*?)</pre>', dom, re.S)
    if not match:
        raise ReportError("could not read the measurement result from the browser")
    return json.loads(html.unescape(match.group(1)))


def evaluate_measurements(rows: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for row in rows:
        # the body box is a flex item that stretches, so its scrollHeight is never below its
        # client height; the content height is the lowest child edge ("used")
        for box in row.get("clipped", []):
            errors.append(f"{row['id']}: {box['name']} is clipped by {box['over']} px (text or figure beyond its box)")
        used = row.get("used", row["bodyScroll"])
        spare = row["bodyClient"] - used
        if row["scroll"] > row["client"] or row["bodyScroll"] > row["bodyClient"] or used > row["bodyClient"]:
            errors.append(f"{row['id']}: content is {max(row['bodyScroll'], used) - row['bodyClient']:.0f} px taller than its box (clipped)")
        elif used > row["bodyClient"] * HEADROOM:
            warnings.append(f"{row['id']}: body is {used / row['bodyClient']:.0%} full, above {HEADROOM:.0%} headroom ({spare:.0f} px spare)")
    return errors, warnings


BROWSER_TIMEOUT_S = 60


def run_browser(browser: str, args: list[str], timeout: int = BROWSER_TIMEOUT_S) -> subprocess.CompletedProcess:
    """Run the browser headless with a hard timeout; its whole process group is killed on expiry."""
    with tempfile.TemporaryDirectory() as scratch:
        out, err = Path(scratch, "out"), Path(scratch, "err")
        command = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                   "--disable-extensions", "--disable-background-networking", f"--user-data-dir={scratch}/profile", *args]
        with out.open("wb") as o, err.open("wb") as e:
            process = subprocess.Popen(command, stdout=o, stderr=e, stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, 9)
                except ProcessLookupError:
                    pass
                process.wait()
                raise ReportError(f"the browser did not finish within {timeout} s and was killed; nothing was measured") from None
        return subprocess.CompletedProcess(command, process.returncode, out.read_bytes(), err.read_bytes())


def measure(inputs: Inputs, built: Path, browser: str, pdf_out: Path | None) -> int:
    try:
        version = subprocess.run([browser, "--version"], capture_output=True, text=True, timeout=15).stdout.strip()
    except subprocess.TimeoutExpired:
        raise ReportError("the browser did not answer --version within 15 s") from None
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "measure.html"
        text = built.read_text(encoding="utf-8")
        copy.write_text(text.replace("</body>", MEASURE_SCRIPT + "</body>").replace(
            "default-src 'none';", "default-src 'none'; script-src 'unsafe-inline';"), encoding="utf-8")
        dom = run_browser(browser, ["--virtual-time-budget=4000", "--window-size=1200,1600", "--dump-dom", copy.as_uri()]).stdout.decode("utf-8", "replace")
        rows = parse_measurements(dom)
        pdf = Path(tmp) / "report.pdf"
        run_browser(browser, ["--no-pdf-header-footer", f"--print-to-pdf={pdf}", built.as_uri()])
        if not pdf.is_file():
            raise ReportError("the browser did not write a PDF")
        data = pdf.read_bytes()
        if pdf_out:
            pdf_out.parent.mkdir(parents=True, exist_ok=True)
            pdf_out.write_bytes(data)
    print(f"browser: {version}")
    print("page      used mm  available mm  fill")
    mm_per_px = PAGE_HEIGHT_MM / rows[0]["ppx"] if rows else 0
    for row in rows:
        used = row.get("used", row["bodyScroll"])
        print(f"{row['id']:<8} {used * mm_per_px:8.1f} {row['bodyClient'] * mm_per_px:13.1f}  {used / row['bodyClient']:.0%}")
    errors, warnings = evaluate_measurements(rows)
    pages = count_pdf_pages(data)
    print(f"printed pages: {pages}")
    for line in warnings:
        print(f"warning: {line}")
    if pages != PAGES:
        errors.append(f"printed page count is {pages}, not {PAGES}")
    for line in errors:
        print(f"error: {line}", file=sys.stderr)
    return 1 if errors else 0


# --- CLI ----------------------------------------------------------------------


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and check the four-page printable HTML report.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this repository)")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help=f"write {OUTPUT}")
    build.add_argument("--require-user-text", action="store_true", help="release build: fail while any placeholder remains")
    build.add_argument("--output", type=Path, help=f"output file (default: {OUTPUT})")
    sub.add_parser("check", help="offline structural, legibility, lint and budget checks; writes nothing")
    meas = sub.add_parser("measure", help="headless-browser fit and printed page count")
    meas.add_argument("--browser", help="browser binary (default: $REPORT_BROWSER, then known locations)")
    meas.add_argument("--pdf", type=Path, help="keep the printed PDF at this path")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        inputs = Inputs(root)
        if args.command == "check":
            problems, warnings, holders = run_checks(inputs)
            for line in warnings:
                print(f"warning: {line}")
            for line in problems:
                print(f"error: {line}", file=sys.stderr)
            if problems:
                return 1
            print(f"check passed ({PAGES} pages); placeholders: {len(holders)}" + (f" ({', '.join(holders)})" if holders else ""))
            return 0
        output = (getattr(args, "output", None) or root / OUTPUT)
        if args.command == "build":
            try:
                output.resolve().relative_to(root)
            except ValueError:
                raise ReportError(f"output {output} is outside the repository root") from None
            html_text = build_html(inputs)
            holders = placeholders(parse(html_text))
            if args.require_user_text and holders:
                for line in holders:
                    print(f"error: unfilled: {line}", file=sys.stderr)
                return 1
            problems = check_structure(html_text, parse(html_text)) + check_slots(inputs)
            if problems:
                raise ReportError("; ".join(problems))
            write_atomic(output, html_text)
            print(f"wrote {output}; placeholders: {len(holders)}" + (f" ({', '.join(holders)})" if holders else ""))
            return 0
        browser = find_browser(args.browser)
        if not browser:
            print("SKIPPED: no browser found (set REPORT_BROWSER or pass --browser); nothing was measured", file=sys.stderr)
            return EXIT_SKIPPED
        if not output.is_file():
            raise ReportError(f"{output} does not exist; run `build` first")
        return measure(inputs, output, browser, args.pdf)
    except ReportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
