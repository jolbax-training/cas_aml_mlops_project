#!/usr/bin/env python3
"""Render the presentation charts as plain, script-free SVG from the evidence summary.

    .venv/bin/python scripts/render_charts.py            # write presentation/charts/*.svg
    .venv/bin/python scripts/render_charts.py --check    # fail if the committed files differ

Input is presentation/evidence/summary.json only: no bundles, no network, no ledger. Output is
deterministic (integer coordinates, no timestamps, no random ids). Every chart uses a 960x540
viewBox, text of at least MIN_FONT units, only the element set that scripts/build_work_log.py
accepts (svg, title, desc, defs, marker, path, g, rect, text, tspan, style), an opaque white
background, and a solid-versus-hatched fill so the two variants differ in greyscale print.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARY = REPO_ROOT / "presentation" / "evidence" / "summary.json"
CHARTS_DIR = REPO_ROOT / "presentation" / "charts"
W, H = 960, 540
VIEWBOX = f"0 0 {W} {H}"
MIN_FONT = 20
# Compact variants for half an A4 text column: at 78 mm wide one unit is 78/480 = 0.1625 mm, so
# 17 units is 2.76 mm = 7.8 pt, above the 7.5 pt floor (7.5 pt needs 16.3 units at that width).
CW, CH = 480, 270
COMPACT_VIEWBOX = f"0 0 {CW} {CH}"
COMPACT_MIN_FONT = 17
COMPACT_MIN_MM = 78
INK, MUTED, GRID = "#1a1a1a", "#4d4d4d", "#c8c8c8"
BASE_FILL = "#1f4e8c"
REV_FILL, REV_STROKE = "#f7c999", "#a33f00"
SINGLE_FILL = "#3b6b4a"
VARIANTS = ("baseline", "revised")


# --- small SVG helpers -------------------------------------------------------------------------

def esc(text: Any) -> str:
    return escape(str(text), {'"': "&quot;"})


def text(x: float, y: float, s: Any, *, size: int = MIN_FONT, anchor: str = "start",
         weight: str = "normal", fill: str = INK) -> str:
    w = ' font-weight="bold"' if weight == "bold" else ""
    a = "" if anchor == "start" else f' text-anchor="{anchor}"'
    return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}"{w}{a} fill="{fill}">{esc(s)}</text>'


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none") -> str:
    return (f'<rect x="{x:.0f}" y="{y:.0f}" width="{max(w, 0):.0f}" height="{h:.0f}" fill="{fill}"'
            f' stroke="{stroke}" stroke-width="2"/>')


def hatch(x: int, y: int, w: int, h: int, step: int = 8) -> str:
    """Diagonal segments clipped to the rectangle, as one path (no pattern or clipPath)."""
    if w <= 0 or h <= 0:
        return ""
    parts = []
    for c in range(-h, w, step):
        hi, lo = min(h, c + h), max(0, c + h - w)
        if hi > lo:
            parts.append(f"M{x + c + h - hi} {y + hi}L{x + c + h - lo} {y + lo}")
    return f'<path d="{"".join(parts)}" fill="none" stroke="{REV_STROKE}" stroke-width="2"/>'


def bar(x: int, y: int, w: int, h: int, variant: str, step: int = 8) -> str:
    """One bar: solid for baseline (and single series), hatched and outlined for revised."""
    if variant == "revised":
        return rect(x, y, w, h, REV_FILL, REV_STROKE) + hatch(x, y, w, h, step)
    return rect(x, y, w, h, SINGLE_FILL if variant == "single" else BASE_FILL)


def swatch(x: int, y: int, variant: str) -> str:
    return bar(x, y, 28, 22, variant)


def legend(summary: Mapping[str, Any], y: int = 62) -> str:
    runs = summary["provenance"]["runs"]
    parts = []
    for i, variant in enumerate(VARIANTS):
        x = 40 + i * 440
        parts.append(swatch(x, y - 18, variant))
        parts.append(text(x + 38, y, f"{variant.capitalize()} ({runs[variant]['prompt']['version']})"))
    return "".join(parts)


def svg_doc(cid: str, title: str, desc: str, body: str, w: int = W, h: int = H) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-labelledby="{cid}-title {cid}-desc">\n'
            f'<title id="{cid}-title">{esc(title)}</title>\n'
            f'<desc id="{cid}-desc">{esc(desc)}</desc>\n'
            '<style>text{font-family:system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}</style>\n'
            f'<rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff"/>\n'
            f'{body}\n</svg>\n')


def heading(title: str) -> str:
    return text(40, 34, title, size=26, weight="bold")


def footnote(note: str) -> str:
    """At most two lines of at most 76 characters, ending at the bottom edge."""
    lines, line = [], ""
    for word in note.split():
        if line and len(line) + 1 + len(word) > 76:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    if len(lines) > 2:
        raise ValueError(f"footnote too long: {note!r}")
    return "".join(text(40, 520 - 26 * (len(lines) - 1 - i), part, fill=MUTED)
                   for i, part in enumerate(lines))


def limits_note(s: Mapping[str, Any]) -> str:
    n = s["comparison"]["baseline"]["primary"]["of"]
    return f"Not a measured improvement: {n} trials per variant, one model."


def ratio(r: Mapping[str, Any]) -> str:
    rate = "n/a" if r["rate"] is None else f"{r['rate'] * 100:.1f}%"
    return f"{r['count']}/{r['of']} ({rate})"


def grouped_bars(rows: Sequence[tuple[str, Sequence[tuple[str, float, str]]]], *, per_row_scale: bool,
                 top: int = 96, label_w: int = 260, x_end: int = 700) -> str:
    """rows: (label, [(variant, value, label text)]). Bars scale to the global or per-row maximum."""
    avail = 500 - top
    row_h = min(110, avail // max(len(rows), 1))
    bar_h = 22 if row_h >= 56 else 24
    overall = max((v for _, bars in rows for _, v, _ in bars), default=1) or 1
    x0, parts = 40 + label_w, []
    for r, (label, bars) in enumerate(rows):
        y = top + r * row_h
        top_of_group = y + (row_h - len(bars) * (bar_h + 4)) // 2
        parts.append(text(40, top_of_group + bar_h + (len(bars) - 1) * (bar_h + 4) / 2 - 2
                          if len(bars) > 1 else top_of_group + bar_h - 3, label))
        peak = (max(v for _, v, _ in bars) or 1) if per_row_scale else overall
        for i, (variant, value, label_text) in enumerate(bars):
            by = top_of_group + i * (bar_h + 4)
            width = int(round(value / peak * (x_end - x0))) if peak else 0
            parts.append(bar(x0, by, width, bar_h, variant))
            parts.append(text(x0 + width + 10, by + bar_h - 3, label_text))
    parts.append(f'<path d="M{x0} {top - 6}V{top + len(rows) * row_h}" stroke="{GRID}" stroke-width="2" fill="none"/>')
    return "".join(parts)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def seconds(ms: float) -> str:
    return f"{ms / 1000:.1f} s"


def describe(rows: Sequence[tuple[str, Sequence[tuple[str, float, str]]]]) -> str:
    return " ".join(f"{label}: " + ", ".join(f"{v} {t}" for v, _, t in bars) + "." for label, bars in rows)


def variants_rows(summary: Mapping[str, Any], items: Sequence[tuple[str, Callable[[str], tuple[float, str]]]]):
    rows = []
    for label, fn in items:
        rows.append((label, [(v, *fn(v)) for v in VARIANTS]))
    return rows


# --- charts ----------------------------------------------------------------------------------------

def chart_outcome_overview(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    keys = (("Successful trials", "primary"), ("Hidden checks", "hidden_checks"), ("Edge cases", "edge_cases"))
    rows = variants_rows(s, [(label, lambda v, k=k: (c[v][k]["rate"], ratio(c[v][k]))) for label, k in keys])
    title = "Outcome comparison: baseline versus revised prompt"
    body = (heading(title) + legend(s) + grouped_bars(rows, per_row_scale=False, x_end=720)
            + footnote("Bar length is the share of planned. " + limits_note(s)))
    return title, "Share of planned items passed. " + describe(rows), body


def chart_outcome_by_category(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    cats = sorted(c["baseline"]["categories"])
    rows = variants_rows(s, [(cat, lambda v, cat=cat: (c[v]["categories"][cat]["rate"],
                                                       ratio(c[v]["categories"][cat]))) for cat in cats])
    n = c["baseline"]["categories"][cats[0]]["of"]
    title = f"Successful trials per category (of {n})"
    body = heading(title) + legend(s) + grouped_bars(rows, per_row_scale=False, x_end=720) \
        + footnote(f"{n} planned trials per category. " + limits_note(s))
    return title, f"Successful trials per category out of {n}. " + describe(rows), body


def chart_outcome_by_task(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    gained, regressed = set(c["delta"]["gained_tasks"]), set(c["delta"]["regressed_tasks"])
    tasks = sorted(c["baseline"]["per_task"])
    n = c["baseline"]["per_task"][tasks[0]]["trials"]
    parts = [heading(f"Successful trials per task (of {n})"), text(330, 70, "Baseline", weight="bold"),
             text(560, 70, "Revised", weight="bold"), text(780, 70, "Change", weight="bold")]
    desc_parts = []
    for i, task in enumerate(tasks):
        y = 100 + i * 36
        parts.append(text(40, y + 17, task))
        for variant, x0 in (("baseline", 330), ("revised", 560)):
            won = c[variant]["per_task"][task]["succeeded"]
            for k in range(n):
                bx = x0 + k * 34
                if k < won:
                    parts.append(bar(bx, y, 28, 24, variant))
                else:
                    parts.append(rect(bx, y, 28, 24, "#ffffff", MUTED))
            parts.append(text(x0 + 34 * n + 6, y + 19, f"{won}/{n}"))
        note = "gained" if task in gained else "regressed" if task in regressed else ""
        if note:
            parts.append(text(780, y + 19, note, weight="bold"))
        desc_parts.append(f"{task} {c['baseline']['per_task'][task]['succeeded']}/{n} then "
                          f"{c['revised']['per_task'][task]['succeeded']}/{n}" + (f" ({note})" if note else ""))
    parts.append(footnote("Filled square = successful trial. " + limits_note(s)))
    title = "Per-task outcomes: baseline versus revised prompt"
    return title, f"Successful trials per task out of {n}: " + "; ".join(desc_parts) + ".", "".join(parts)


def chart_failure_labels(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    labels = sorted(set(c["baseline"]["failure_labels"]) | set(c["revised"]["failure_labels"]))
    rows = variants_rows(s, [(lab, lambda v, lab=lab: (c[v]["failure_labels"].get(lab, 0),
                                                        str(c[v]["failure_labels"].get(lab, 0)))) for lab in labels])
    title = "Failure labels of failed trials"
    body = heading(title) + legend(s) + grouped_bars(rows, per_row_scale=False, x_end=640) \
        + footnote("Trials per grade label. Failed trials: "
                 + ", ".join(f"{sum(c[v]['failure_labels'].values())} {v}" for v in VARIANTS) + ".")
    return title, "Number of trials per failure label. " + describe(rows), body


def story_title(s: Mapping[str, Any], task: str, note: str) -> str:
    b, r = (s["comparison"][v]["per_task"][task] for v in VARIANTS)
    return f"{task}: {b['succeeded']}/{b['trials']} to {r['succeeded']}/{r['trials']} ({note})"


def story_table(s: Mapping[str, Any], task: str, last_header: str, last: Callable[[Mapping[str, Any]], str],
                title: str, note: str) -> tuple[str, str, str]:
    columns = [("Trial", 80, "start"), ("Result", 270, "start"), ("Calls", 500, "end"),
               ("Tools", 600, "end"), (last_header, 640, "start")]
    rows, desc = [], []
    for variant in VARIANTS:
        for t in s["stories"][task][variant]:
            result = "pass" if t["success"] else (", ".join(t["labels"]) or "fail")
            cells = [f"{variant[:4]}-{t['trial_id'].rsplit('-', 1)[1]}", result, str(t["model_calls"]),
                     str(t["tool_attempts"]), last(t)]
            rows.append((variant, cells))
            desc.append(f"{variant} {t['trial_id']}: {result}, {t['model_calls']} model calls, "
                        f"{t['tool_attempts']} tool attempts, {last(t)}")
    body = heading(title) + legend(s) + table_rows(columns, rows, top=116) + footnote(note)
    return title, "; ".join(desc) + ".", body


def table_rows(columns, rows, top):
    parts = [text(x, top, h, anchor=a, weight="bold") for h, x, a in columns]
    parts.append(f'<path d="M40 {top + 10}H920" stroke="{INK}" stroke-width="2" fill="none"/>')
    for r, (variant, cells) in enumerate(rows):
        y = top + 38 + r * 40
        parts.append(swatch(40, y - 18, variant))
        for (_, x, anchor), cell in zip(columns, cells):
            parts.append(text(x, y, cell, anchor=anchor))
        if r == 2:
            parts.append(f'<path d="M40 {y + 14}H920" stroke="{GRID}" stroke-width="2" fill="none"/>')
    return "".join(parts)


def chart_story_lists(s: Mapping[str, Any]) -> tuple[str, str, str]:
    return story_table(s, "lists_02", "Final message", lambda t: t["final_form"],
                       story_title(s, "lists_02", "a gain, not a proof"),
                       "Final form is read from grade labels. " + limits_note(s))


def chart_story_strings(s: Mapping[str, Any]) -> tuple[str, str, str]:
    def last(t: Mapping[str, Any]) -> str:
        if not t["failed_checks"]:
            return "none failed"
        return ", ".join(f"{c['id']} (actual {c['actual']})" for c in t["failed_checks"])
    return story_table(s, "strings_01", "Failed hidden check", last,
                       story_title(s, "strings_01", "one wrong answer"),
                       "One trial of three; not linked to the added sentence. " + limits_note(s))


def chart_efficiency_calls(s: Mapping[str, Any]) -> tuple[str, str, str]:
    e = s["efficiency"]
    rows = variants_rows(s, [("Model calls", lambda v: (e[v]["model_calls"], str(e[v]["model_calls"]))),
                             ("Tool attempts", lambda v: (e[v]["tool_attempts"], str(e[v]["tool_attempts"]))),
                             ("Revisions", lambda v: (e[v]["revisions"], str(e[v]["revisions"])))])
    n = s["comparison"]["baseline"]["primary"]["of"]
    title = f"Model calls, tool attempts and revisions over {n} trials"
    body = heading(title) + legend(s) + grouped_bars(rows, per_row_scale=False, x_end=700) \
        + footnote(f"Counts over {n} trials per variant. " + limits_note(s))
    return title, f"Counts over {n} trials per variant. " + describe(rows), body


def chart_efficiency_tokens(s: Mapping[str, Any]) -> tuple[str, str, str]:
    t = {v: s["efficiency"][v]["tokens"] for v in VARIANTS}
    rows = variants_rows(s, [("Prompt tokens", lambda v: (t[v]["prompt_tokens"], fmt_int(t[v]["prompt_tokens"]))),
                             ("Completion tokens", lambda v: (t[v]["completion_tokens"],
                                                              fmt_int(t[v]["completion_tokens"])))])
    n = s["comparison"]["baseline"]["primary"]["of"]
    title = f"Tokens over {n} trials"
    body = heading(title) + legend(s) + grouped_bars(rows, per_row_scale=False, x_end=700) \
        + footnote(f"Provider-reported usage, summed over {n} trials per variant.")
    return title, f"Tokens summed over {n} trials. " + describe(rows), body


def chart_efficiency_latency(s: Mapping[str, Any]) -> tuple[str, str, str]:
    e = s["efficiency"]
    rows = variants_rows(s, [
        ("Model latency, total", lambda v: (e[v]["model_latency_ms"]["total"], seconds(e[v]["model_latency_ms"]["total"]))),
        ("Mean per trial", lambda v: (e[v]["model_latency_ms"]["mean_per_trial"],
                                      seconds(e[v]["model_latency_ms"]["mean_per_trial"])))])
    title = "Model latency"
    body = heading(title) + legend(s) + grouped_bars(rows, per_row_scale=True, x_end=700) \
        + footnote("Measured once per variant, at different times; not attributed to the prompt.")
    return title, "Model latency, each row scaled on its own. " + describe(rows) + \
        " Measured once per variant at different times and not attributed to the prompt.", body


def chart_cost(s: Mapping[str, Any]) -> tuple[str, str, str]:
    e = s["efficiency"]
    rows = variants_rows(s, [
        ("Charged (CHF)", lambda v: (e[v]["cost"]["charged_chf"], f"{e[v]['cost']['charged_chf']:.5f}")),
        ("Reserved (CHF)", lambda v: (e[v]["cost"]["reserved_before_send_chf"],
                                      f"{e[v]['cost']['reserved_before_send_chf']:.5f}"))])
    title = "Charged versus reserved cost (CHF)"
    body = heading(title) + legend(s) + grouped_bars(rows, per_row_scale=True, x_end=700) \
        + footnote("Rows use separate scales; reserved is the worst case before each send.")
    return title, "Charged and reserved-before-send cost in CHF, each row scaled on its own. " + \
        describe(rows) + " Measured once per variant, not attributed to the prompt.", body


def chart_engineering_tests(s: Mapping[str, Any]) -> tuple[str, str, str]:
    eng = s["engineering"]
    runs = eng["ci"]["runs"]
    latest = next(r for r in reversed(runs) if r.get("offline_tests"))
    rows = [("Offline, collected", [("single", eng["tests"]["offline_collected"],
                                      fmt_int(eng["tests"]["offline_collected"]))]),
            ("Sandbox, collected", [("single", eng["tests"]["sandbox_collected"],
                                      fmt_int(eng["tests"]["sandbox_collected"]))]),
            (f"CI offline, run {latest['run']}", [("single", latest["offline_tests"],
                                                             fmt_int(latest["offline_tests"]))]),
            (f"CI podman, run {latest['run']}", [("single", latest["podman_tests"],
                                                            fmt_int(latest["podman_tests"]))])]
    title = "Tests: collected locally and counted in CI"
    body = heading(title) + grouped_bars(rows, per_row_scale=False, x_end=700, label_w=350) \
        + footnote(f"Collected = pytest --collect-only at {eng['tests']['commit'][:7]}. "
                  "CI counts are those recorded in the evidence documents.")
    return title, "Test counts. " + describe(rows), body


def chart_engineering_ci(s: Mapping[str, Any]) -> tuple[str, str, str]:
    columns = [("Run", 80, "start"), ("Commit", 250, "start"), ("offline", 400, "start"),
               ("podman", 560, "start"), ("podman tests", 760, "start")]
    rows, desc = [], []
    for r in s["engineering"]["ci"]["runs"]:
        podman = r.get("podman", "n/r")
        if r.get("podman_failed"):
            podman = f"{podman} ({r['podman_failed']})"
        cells = [str(r["run"]), str(r.get("commit", "n/r")), r.get("offline", "n/r"), podman,
                 str(r["podman_tests"]) if r.get("podman_tests") is not None else "n/r"]
        rows.append(cells)
        desc.append(f"run {cells[0]} commit {cells[1]}: offline {cells[2]}, podman {cells[3]}, tests {cells[4]}")
    parts = [heading("CI runs recorded in the evidence documents")]
    top = 80
    parts += [text(x, top, h, anchor=a, weight="bold") for h, x, a in columns]
    parts.append(f'<path d="M40 {top + 10}H920" stroke="{INK}" stroke-width="2" fill="none"/>')
    for i, cells in enumerate(rows):
        y = top + 38 + i * 40
        for (h, x, a), cell in zip(columns, cells):
            parts.append(text(x, y, cell, weight="bold" if cell in ("failed",) or cell.startswith("failed") else "normal"))
    parts.append(footnote("n/r = not recorded. Failed runs are history, not completion evidence."))
    return "CI runs recorded", "CI runs: " + "; ".join(desc) + ".", "".join(parts)


def chart_engineering_changes(s: Mapping[str, Any]) -> tuple[str, str, str]:
    by_date = s["engineering"]["changes_archived"]["by_date"]
    rows = [(d, [("single", n, str(n))]) for d, n in sorted(by_date.items())]
    count = s["engineering"]["changes_archived"]["count"]
    title = f"OpenSpec changes archived: {count}"
    body = heading(title) + grouped_bars(rows, per_row_scale=False, x_end=700, label_w=200) \
        + footnote("Changes moved to the archive, by date in the archive folder name.")
    return title, f"{count} archived changes by date. " + describe(rows), body


# --- compact variants (half an A4 text column) ---------------------------------------------------

def vshort(s: Mapping[str, Any], variant: str) -> str:
    match = re.search(r"_(v\d+)$", s["provenance"]["runs"][variant]["prompt"]["version"])
    return f"{variant.capitalize()} {match.group(1)}" if match else variant.capitalize()


def climit(s: Mapping[str, Any]) -> str:
    return f"Not a measured improvement ({s['comparison']['baseline']['primary']['of']} trials each)."


def cheading(title: str) -> str:
    return text(8, 20, title, size=19, weight="bold")


def clegend(s: Mapping[str, Any], y: int = 44) -> str:
    return "".join(bar(x, y - 13, 22, 14, v, 6) + text(x + 30, y, vshort(s, v), size=COMPACT_MIN_FONT)
                   for x, v in ((8, "baseline"), (200, "revised")))


def cfoot(note: str) -> str:
    """At most two lines of at most 48 characters, ending near the bottom edge."""
    lines, line = [], ""
    for word in note.split():
        if line and len(line) + 1 + len(word) > 48:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    if len(lines) > 2:
        raise ValueError(f"compact note too long: {note!r}")
    return "".join(text(8, 262 - 22 * (len(lines) - 1 - i), part, size=COMPACT_MIN_FONT, fill=MUTED)
                   for i, part in enumerate(lines))


def cratio(r: Mapping[str, Any]) -> str:
    return f"{r['count']}/{r['of']} " + ("n/a" if r["rate"] is None else f"{r['rate'] * 100:.0f}%")


def cbars(rows: Sequence[tuple[str, Sequence[tuple[str, float, str]]]], *, per_row_scale: bool,
          label_w: int, x_end: int, top: int = 56, bottom: int = 216) -> str:
    row_h = min(56, (bottom - top) // max(len(rows), 1))
    overall = max((v for _, bars in rows for _, v, _ in bars), default=1) or 1
    x0, parts = 8 + label_w, []
    for r, (label, bars) in enumerate(rows):
        bar_h = min(14, (row_h - 4) // len(bars) - 3) if len(bars) > 1 else min(18, row_h - 6)
        group = len(bars) * (bar_h + 3)
        y0 = top + r * row_h + (row_h - group) // 2
        parts.append(text(8, y0 + group // 2 + 6, label, size=COMPACT_MIN_FONT))
        peak = (max(v for _, v, _ in bars) or 1) if per_row_scale else overall
        for i, (variant, value, label_text) in enumerate(bars):
            by = y0 + i * (bar_h + 3)
            width = int(round(value / peak * (x_end - x0))) if peak else 0
            parts.append(bar(x0, by, width, bar_h, variant, 6))
            parts.append(text(x0 + width + 6, by + bar_h - 1 if bar_h < 16 else by + bar_h - 3, label_text,
                              size=COMPACT_MIN_FONT))
    parts.append(f'<path d="M{x0} {top - 4}V{top + len(rows) * row_h}" stroke="{GRID}" stroke-width="2" fill="none"/>')
    return "".join(parts)


def ctable(columns: Sequence[tuple[str, int, str]], rows: Sequence[tuple[str, Sequence[str]]],
           top: int = 72) -> str:
    parts = [text(x, top, h, size=COMPACT_MIN_FONT, anchor=a, weight="bold") for h, x, a in columns]
    parts.append(f'<path d="M8 {top + 6}H472" stroke="{INK}" stroke-width="2" fill="none"/>')
    for r, (variant, cells) in enumerate(rows):
        y = top + 28 + r * 24
        parts.append(bar(8, y - 13, 20, 14, variant, 6))
        for (_, x, anchor), cell in zip(columns, cells):
            parts.append(text(x, y, cell, size=COMPACT_MIN_FONT, anchor=anchor))
        if r == 2:
            parts.append(f'<path d="M8 {y + 6}H472" stroke="{GRID}" stroke-width="2" fill="none"/>')
    return "".join(parts)


def c_outcome_overview(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    rows = variants_rows(s, [(label, lambda v, k=k: (c[v][k]["rate"], cratio(c[v][k])))
                             for label, k in (("Successful trials", "primary"), ("Hidden checks", "hidden_checks"),
                                              ("Edge cases", "edge_cases"))])
    title = "Outcomes: baseline vs revised"
    body = cheading(title) + clegend(s) + cbars(rows, per_row_scale=False, label_w=165, x_end=335) \
        + cfoot("Bar = share of planned. " + climit(s))
    return title, "Share of planned items passed. " + describe(rows), body


def c_outcome_by_category(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    cats = sorted(c["baseline"]["categories"])
    rows = variants_rows(s, [(cat, lambda v, cat=cat: (c[v]["categories"][cat]["rate"],
                                                       cratio(c[v]["categories"][cat]))) for cat in cats])
    title = "Successful trials per category"
    body = cheading(title) + clegend(s) + cbars(rows, per_row_scale=False, label_w=172, x_end=350, top=54, bottom=240) \
        + cfoot(climit(s))
    return title, "Successful trials per category. " + describe(rows), body


def c_failure_labels(s: Mapping[str, Any]) -> tuple[str, str, str]:
    c = s["comparison"]
    labels = sorted(set(c["baseline"]["failure_labels"]) | set(c["revised"]["failure_labels"]))
    rows = variants_rows(s, [(lab, lambda v, lab=lab: (c[v]["failure_labels"].get(lab, 0),
                                                        str(c[v]["failure_labels"].get(lab, 0)))) for lab in labels])
    title = "Failure labels per variant"
    body = cheading(title) + clegend(s) + cbars(rows, per_row_scale=False, label_w=135, x_end=330) \
        + cfoot("Failed trials: " + ", ".join(f"{sum(c[v]['failure_labels'].values())} {v}" for v in VARIANTS) + ".")
    return title, "Trials per failure label. " + describe(rows), body


def c_story(s: Mapping[str, Any], task: str, header: str, last: Callable[[Mapping[str, Any]], str],
            note: str) -> tuple[str, str, str]:
    columns = [("Trial", 36, "start"), ("Result", 112, "start"), ("Calls", 285, "end"),
               ("Tools", 335, "end"), (header, 345, "start")]
    rows, desc = [], []
    for variant in VARIANTS:
        for t in s["stories"][task][variant]:
            result = "pass" if t["success"] else (", ".join(t["labels"]) or "fail")
            rows.append((variant, [f"{variant[:4]}-{t['trial_id'].rsplit('-', 1)[1]}", result,
                                   str(t["model_calls"]), str(t["tool_attempts"]), last(t)]))
            desc.append(f"{variant} {t['trial_id']}: {result}, {t['model_calls']} calls, "
                        f"{t['tool_attempts']} tool attempts, {last(t)}")
    title = story_title(s, task, "")
    title = title.replace(" ()", "")
    return title, "; ".join(desc) + ".", cheading(title) + clegend(s) + ctable(columns, rows) + cfoot(note)


FORM_SHORT = {"prose before code": "prose", "fenced reply": "fence", "bare function": "bare"}


def c_story_lists(s: Mapping[str, Any]) -> tuple[str, str, str]:
    return c_story(s, "lists_02", "Form", lambda t: FORM_SHORT.get(t["final_form"], t["final_form"]),
                   "Form: final message. " + climit(s))


def c_story_strings(s: Mapping[str, Any]) -> tuple[str, str, str]:
    return c_story(s, "strings_01", "Failed", lambda t: ", ".join(c["id"] for c in t["failed_checks"]) or "-",
                   "Failed = hidden check. " + climit(s))


def c_efficiency_calls(s: Mapping[str, Any]) -> tuple[str, str, str]:
    e = s["efficiency"]
    rows = variants_rows(s, [("Model calls", lambda v: (e[v]["model_calls"], str(e[v]["model_calls"]))),
                             ("Tool attempts", lambda v: (e[v]["tool_attempts"], str(e[v]["tool_attempts"]))),
                             ("Revisions", lambda v: (e[v]["revisions"], str(e[v]["revisions"])))])
    n = s["comparison"]["baseline"]["primary"]["of"]
    title = "Calls, tool attempts, revisions"
    body = cheading(title) + clegend(s) + cbars(rows, per_row_scale=False, label_w=130, x_end=400) \
        + cfoot(f"Counts over {n} trials per variant.")
    return title, f"Counts over {n} trials per variant. " + describe(rows), body


def c_efficiency_latency(s: Mapping[str, Any]) -> tuple[str, str, str]:
    e = s["efficiency"]
    rows = variants_rows(s, [
        ("Total", lambda v: (e[v]["model_latency_ms"]["total"], seconds(e[v]["model_latency_ms"]["total"]))),
        ("Per trial", lambda v: (e[v]["model_latency_ms"]["mean_per_trial"],
                                 seconds(e[v]["model_latency_ms"]["mean_per_trial"])))])
    title = "Model latency"
    body = cheading(title) + clegend(s) + cbars(rows, per_row_scale=True, label_w=95, x_end=380) \
        + cfoot("Measured once per variant; not attributed to the prompt.")
    return title, "Model latency, rows scaled separately. " + describe(rows) + \
        " Measured once per variant, not attributed to the prompt.", body


def c_cost(s: Mapping[str, Any]) -> tuple[str, str, str]:
    e = s["efficiency"]
    rows = variants_rows(s, [
        ("Charged", lambda v: (e[v]["cost"]["charged_chf"], f"{e[v]['cost']['charged_chf']:.5f}")),
        ("Reserved", lambda v: (e[v]["cost"]["reserved_before_send_chf"],
                                f"{e[v]['cost']['reserved_before_send_chf']:.5f}"))])
    title = "Charged vs reserved (CHF)"
    body = cheading(title) + clegend(s) + cbars(rows, per_row_scale=True, label_w=95, x_end=380) \
        + cfoot("Rows scaled separately; not attributed to the prompt.")
    return title, "Charged and reserved cost in CHF, rows scaled separately. " + describe(rows) + \
        " Measured once per variant, not attributed to the prompt.", body


def c_tests(s: Mapping[str, Any]) -> tuple[str, str, str]:
    eng = s["engineering"]
    latest = next(r for r in reversed(eng["ci"]["runs"]) if r.get("offline_tests"))
    rows = [(label, [("single", n, fmt_int(n))]) for label, n in (
        ("Offline, collected", eng["tests"]["offline_collected"]),
        ("Sandbox, collected", eng["tests"]["sandbox_collected"]),
        ("CI offline", latest["offline_tests"]), ("CI podman", latest["podman_tests"]))]
    title = "Tests: collected and in CI"
    body = cheading(title) + cbars(rows, per_row_scale=False, label_w=175, x_end=400, top=40) \
        + cfoot(f"Collected at {eng['tests']['commit'][:7]}; CI counts as recorded in the documents.")
    return title, "Test counts. " + describe(rows), body


def c_changes(s: Mapping[str, Any]) -> tuple[str, str, str]:
    arch = s["engineering"]["changes_archived"]
    rows = [(d, [("single", n, str(n))]) for d, n in sorted(arch["by_date"].items())]
    title = f"Changes archived: {arch['count']}"
    body = cheading(title) + cbars(rows, per_row_scale=False, label_w=105, x_end=400, top=40) \
        + cfoot("Archived OpenSpec changes by archive date.")
    return title, f"{arch['count']} archived changes by date. " + describe(rows), body


CHART_META: list[dict[str, Any]] = []


def _meta(cid: str, fn: Callable[[Mapping[str, Any]], tuple[str, str, str]], caption: str, alt: str,
          keys: list[str]) -> None:
    CHART_META.append({"id": cid, "fn": fn, "caption": caption, "alt": alt, "source_keys": keys})


_meta("outcome-overview", chart_outcome_overview,
      "Successful trials, hidden checks and edge cases for the baseline and the revised prompt. "
      "A comparison of two prompts on ten tasks with one model, not a measured improvement.",
      "Paired bars with counts for successful trials, hidden checks and edge cases.",
      ["comparison.baseline.primary", "comparison.revised.primary", "comparison.baseline.hidden_checks",
       "comparison.revised.hidden_checks", "comparison.baseline.edge_cases", "comparison.revised.edge_cases"])
_meta("outcome-by-category", chart_outcome_by_category,
      "Successful trials per category for both prompts.",
      "Paired bars with counts for five task categories.",
      ["comparison.baseline.categories", "comparison.revised.categories"])
_meta("outcome-by-task", chart_outcome_by_task,
      "Successful trials per task for both prompts; the gained and the regressed task are marked.",
      "Filled squares per task for each prompt, with the gained and regressed task marked.",
      ["comparison.baseline.per_task", "comparison.revised.per_task", "comparison.delta"])
_meta("failure-labels", chart_failure_labels, "Grade labels of failed trials per prompt.",
      "Paired bars with the number of trials per failure label.",
      ["comparison.baseline.failure_labels", "comparison.revised.failure_labels"])
_meta("story-lists-02", chart_story_lists,
      "lists_02 trials: the baseline trials ended with explanation or fences after a "
      "wrong self-written check; the revised trials made one call and no tool attempt. The trace does "
      "not show the added sentence working on its trigger.",
      "Table of the lists_02 trials with result, model calls, tool attempts and final message form.",
      ["stories.lists_02"])
_meta("story-strings-01", chart_story_strings,
      "strings_01 trials: one revised trial gave a wrong answer on the edge check strings_01_d.",
      "Table of the strings_01 trials with result, calls, tool attempts and the failed hidden check.",
      ["stories.strings_01"])
_meta("efficiency-calls", chart_efficiency_calls, "Model calls, tool attempts and revisions per prompt.",
      "Paired bars with counts.", ["efficiency.baseline", "efficiency.revised"])
_meta("efficiency-tokens", chart_efficiency_tokens, "Prompt and completion tokens per prompt.",
      "Paired bars with token counts.", ["efficiency.baseline.tokens", "efficiency.revised.tokens"])
_meta("efficiency-latency", chart_efficiency_latency,
      "Model latency per prompt. Measured once per variant at different times against a remote "
      "provider; not attributed to the prompt.",
      "Paired bars with seconds.", ["efficiency.baseline.model_latency_ms", "efficiency.revised.model_latency_ms"])
_meta("cost-charged-reserved", chart_cost,
      "Charged and reserved-before-send cost in CHF per prompt. Measured once per variant; not "
      "attributed to the prompt.",
      "Paired bars with CHF values on separate scales.",
      ["efficiency.baseline.cost", "efficiency.revised.cost"])
_meta("engineering-tests", chart_engineering_tests,
      "Collected test counts at the recorded commit and the CI counts recorded in the evidence documents.",
      "Bars with test counts.", ["engineering.tests", "engineering.ci"])
_meta("engineering-ci", chart_engineering_ci,
      "CI runs recorded in the evidence documents, including failed runs kept as history.",
      "Table of CI runs with offline and podman outcomes.", ["engineering.ci.runs"])
_meta("engineering-changes", chart_engineering_changes, "OpenSpec changes archived, by date.",
      "Bars with the number of changes archived per date.", ["engineering.changes_archived"])


COMPACT_FN: dict[str, Callable[[Mapping[str, Any]], tuple[str, str, str]]] = {
    "outcome-overview": c_outcome_overview, "outcome-by-category": c_outcome_by_category,
    "failure-labels": c_failure_labels, "story-lists-02": c_story_lists,
    "story-strings-01": c_story_strings, "efficiency-calls": c_efficiency_calls,
    "efficiency-latency": c_efficiency_latency, "cost-charged-reserved": c_cost,
    "engineering-tests": c_tests, "engineering-changes": c_changes}
COMPACT_META: list[dict[str, Any]] = [
    {"id": f"{meta['id']}-compact", "full_size": meta["id"], "fn": COMPACT_FN[meta["id"]],
     "caption": meta["caption"] + " Compact variant for half a text column.",
     "alt": meta["alt"], "source_keys": meta["source_keys"]}
    for meta in CHART_META if meta["id"] in COMPACT_FN]


def render_all(summary: Mapping[str, Any]) -> dict[str, str]:
    out = {}
    for meta in CHART_META:
        title, desc, body = meta["fn"](summary)
        out[f"{meta['id']}.svg"] = svg_doc(meta["id"], title, desc, body)
    for meta in COMPACT_META:
        title, desc, body = meta["fn"](summary)
        out[f"{meta['id']}.svg"] = svg_doc(meta["id"], title, desc, body, CW, CH)
    return out


def check_charts(summary: Mapping[str, Any], directory: Path) -> list[str]:
    problems = []
    fresh = render_all(summary)
    for name, content in fresh.items():
        path = directory / name
        if not path.is_file():
            problems.append(f"{path.name}: missing (run render_charts.py)")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"{path.name}: differs from a fresh render of the summary")
    extra = sorted(p.name for p in directory.glob("*.svg") if p.name not in fresh) if directory.is_dir() else []
    problems += [f"{name}: not produced by the generator" for name in extra]
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--summary", default=str(SUMMARY))
    parser.add_argument("--out", default=str(CHARTS_DIR))
    parser.add_argument("--check", action="store_true", help="write nothing; fail on any difference")
    args = parser.parse_args(argv)
    try:
        summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"error: cannot read the summary: {error}", file=sys.stderr)
        return 1
    out = Path(args.out)
    if args.check:
        problems = check_charts(summary, out)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("charts match the summary" if not problems else "charts check FAILED")
        return 1 if problems else 0
    out.mkdir(parents=True, exist_ok=True)
    for name, content in render_all(summary).items():
        (out / name).write_text(content, encoding="utf-8")
    print(f"wrote {len(CHART_META) + len(COMPACT_META)} charts to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
