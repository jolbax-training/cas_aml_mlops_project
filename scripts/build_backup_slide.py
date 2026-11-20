#!/usr/bin/env python3
"""Build the one-page backup slide (second experiment against the first) from committed evidence.

    .venv/bin/python scripts/build_backup_slide.py                      # write backup_slide/backup_slide.html
    .venv/bin/python scripts/build_backup_slide.py --check              # fail when the committed page drifts
    .venv/bin/python scripts/build_backup_slide.py --require-user-text  # release: fail while the takeaway is empty

Inputs, all committed: experiments/evidence_v2/analysis/scale_analysis.json (second experiment),
scale_analysis_v1.json (first experiment, made by `codegen_eval.scale_analysis` read-only on the v1
bundles), the user's backup_slide/user_text.toml (read only, never written) and the logo already
committed for the deck. No bundle, ledger, key or network is used. The page is plain HTML with inline
SVG, no script and no external request, and the same inputs always give the same bytes.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V1_JSON = REPO / "experiments/evidence_v2/analysis/scale_analysis_v1.json"
V2_JSON = REPO / "experiments/evidence_v2/analysis/scale_analysis.json"
USER_TEXT = REPO / "backup_slide/user_text.toml"
OUTPUT = REPO / "backup_slide/backup_slide.html"
LOGO = REPO / "presentation/assets/zhaw_rgb.jpg"
MANIFEST = REPO / "presentation/manifest.json"

LOGO_SHA256 = "bd181c824bd8ff3a50d02436f1bdc0db775c50797e41c555c4f457a8edd8e311"
LOGO_ALT = "ZHAW logo: the blue lowercase letters zh above aw"
TAKEAWAY_LIMIT = 180
AXIS_START = 0.70
FORMATTING_LABELS = ("syntax_error", "contract_error")

# The deck's tokens (presentation/deck/deck.css :root); a test compares them with the file.
TOKENS = {
    "ink": "#111111", "paper": "#ffffff", "muted": "#3d3d3d", "accent": "#0b4f8a",
    "warn-bg": "#fff3c4", "warn-ink": "#1a1400", "warn-edge": "#8a5a00", "chrome-bg": "#000000",
}

# (column key, source file, run key, label). Order is the order on the page.
COLUMNS = (
    ("v1_baseline", "v1", "baseline", "v1 baseline"),
    ("v1_revised", "v1", "revised", "v1 revised"),
    ("v2_baseline", "v2", "baseline", "v2 baseline"),
    ("v2_revised", "v2", "revised", "v2 revised"),
    ("v2_repeat", "v2", "repeat", "v2 baseline repeat"),
)
EXPERIMENT_IDS = {"v1": "prompt_comparison_v1", "v2": "prompt_comparison_v2"}

CHART_VB_W, CHART_VB_H, CHART_CQW = 768, 440, 40


class SlideError(Exception):
    pass


def _load(path: Path, which: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SlideError(f"{which}: cannot read {path}: {exc}") from exc
    if data.get("experiment_id") != EXPERIMENT_IDS[which]:
        raise SlideError(f"{which}: {path} is for experiment {data.get('experiment_id')!r}, "
                         f"expected {EXPERIMENT_IDS[which]!r}")
    return data


def _date(run_id: str, column: str) -> str:
    match = re.match(r"^(\d{4})(\d{2})(\d{2})T", str(run_id))
    if not match:
        raise SlideError(f"{column}: run id {run_id!r} has no date prefix")
    return "-".join(match.groups())


def collect(v1_path: Path = V1_JSON, v2_path: Path = V2_JSON) -> list[dict]:
    """One entry per column, with only the fields the page uses; validates the data it relies on."""
    sources = {"v1": _load(v1_path, "v1"), "v2": _load(v2_path, "v2")}
    columns = []
    for key, which, run_key, label in COLUMNS:
        try:
            run = sources[which]["runs"][run_key]
            primary, wilson = run["primary"], run["wilson_95"]
            per_task = run["per_task"]
            labels = dict(run["metrics"]["failure_labels"])
            incomplete = run["metrics"]["trials_incomplete"]
            count, total = int(primary["count"]), int(primary["of"])
            lower, upper = float(wilson["lower"]), float(wilson["upper"])
            run_id = run["run_id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise SlideError(f"{key}: missing or malformed field {exc}") from exc
        if not (AXIS_START <= lower <= upper <= 1.0):
            raise SlideError(f"{key}: Wilson interval [{lower}, {upper}] lies outside the chart axis "
                             f"[{AXIS_START}, 1.0]")
        failed = total - count - int(incomplete)
        if sum(labels.values()) != failed:
            raise SlideError(f"{key}: failure labels sum to {sum(labels.values())} but "
                             f"of - count - trials_incomplete is {failed}")
        formatting = sum(labels.get(name, 0) for name in FORMATTING_LABELS)
        columns.append({
            "key": key, "label": label, "run_id": run_id, "date": _date(run_id, key), "count": count,
            "of": total, "lower": lower, "upper": upper, "formatting": formatting,
            "other": failed - formatting, "per_task": {t: (int(v["succeeded"]), int(v["trials"]))
                                                      for t, v in per_task.items()},
        })
    tasks = list(columns[0]["per_task"])
    for column in columns:
        if list(column["per_task"]) != tasks:
            raise SlideError(f"{column['key']}: task list differs from {columns[0]['key']}")
    return columns


def facts(columns: list[dict]) -> dict:
    """The numbers the headline states, with the assertions that make the sentences true."""
    by = {c["key"]: c for c in columns}
    v1_gain = by["v1_revised"]["count"] - by["v1_baseline"]["count"]
    v2_change = by["v2_revised"]["count"] - by["v2_baseline"]["count"]
    v2_repeat = by["v2_repeat"]["count"] - by["v2_baseline"]["count"]
    if v1_gain <= 0:
        raise SlideError(f"headline: v1 revised is not ahead of v1 baseline (difference {v1_gain})")
    if abs(v2_change) >= abs(v2_repeat):
        raise SlideError(f"headline: v2 revised differs from v2 baseline by {v2_change}, not less than "
                         f"the repeat's {v2_repeat}")
    return {"v1_gain": v1_gain, "v2_change": v2_change, "v2_repeat": v2_repeat, "by": by}


def headline(columns: list[dict]) -> tuple[str, str]:
    f = facts(columns)
    by = f["by"]

    def kn(key: str) -> str:
        return f"{by[key]['count']}/{by[key]['of']}"

    first = (f"Small samples mislead: at {by['v1_baseline']['of']} trials per prompt the revised prompt "
             f"was ahead by {f['v1_gain']} trials ({kn('v1_baseline')} vs {kn('v1_revised')}); at "
             f"{by['v2_baseline']['of']} trials per run: baseline {kn('v2_baseline')}, revised "
             f"{kn('v2_revised')}, baseline repeated {kn('v2_repeat')}.")
    sub = (f"Repeating the same baseline prompt moved the result by {abs(f['v2_repeat'])} trials "
           f"({by['v2_baseline']['count']} -> {by['v2_repeat']['count']}); changing the prompt moved it "
           f"by {abs(f['v2_change'])}.")
    return first, sub


def read_takeaway(path: Path = USER_TEXT) -> str:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SlideError(f"cannot read the user text {path}: {exc}") from exc
    text = data.get("takeaway")
    if not isinstance(text, str):
        raise SlideError(f"{path}: `takeaway` must be a string")
    text = text.strip()
    if len(text) > TAKEAWAY_LIMIT:
        raise SlideError(f"{path}: takeaway has {len(text)} characters, the limit is {TAKEAWAY_LIMIT}")
    return text


def _logo_uri(logo: Path = LOGO) -> str:
    data = logo.read_bytes()
    if hashlib.sha256(data).hexdigest() != LOGO_SHA256:
        raise SlideError(f"{logo}: sha256 differs from the committed logo ({LOGO_SHA256[:8]}...)")
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def chart_svg(columns: list[dict]) -> str:
    left, right = 215, 610            # plot x range (0.70 .. 1.00); k/n labels start at 622
    top, pitch = 6, 70

    def x(value: float) -> float:
        return left + (value - AXIS_START) / (1.0 - AXIS_START) * (right - left)

    parts = [f'<svg class="chart" viewBox="0 0 {CHART_VB_W} {CHART_VB_H}" role="img" '
             f'aria-label="Success rate with Wilson 95% interval for the five runs">']
    axis_y = top + pitch * len(columns) + 4
    for tick in (0.70, 0.80, 0.90, 1.00):
        parts.append(f'<line x1="{x(tick):.1f}" y1="{top}" x2="{x(tick):.1f}" y2="{axis_y}" class="grid"/>'
                     f'<text x="{x(tick):.1f}" y="{axis_y + 24}" text-anchor="middle" font-size="18" '
                     f'class="axis">{tick:.2f}</text>')
    parts.append(f'<line x1="{left}" y1="{axis_y}" x2="{right}" y2="{axis_y}" class="axisline"/>')
    for i, c in enumerate(columns):
        mid = top + pitch * i + pitch / 2
        css = "v1" if c["key"].startswith("v1") else "v2"
        if i == 2:
            sep = top + pitch * i
            parts.append(f'<line x1="0" y1="{sep}" x2="{CHART_VB_W}" y2="{sep}" class="divider"/>')
        rate = c["count"] / c["of"]
        parts.append(
            f'<text x="0" y="{mid - 2:.1f}" font-size="20" class="rowlabel">{esc(c["label"])}</text>'
            f'<text x="0" y="{mid + 21:.1f}" font-size="18" class="rowdate">{esc(c["date"])}</text>'
            f'<line x1="{x(c["lower"]):.1f}" y1="{mid:.1f}" x2="{x(c["upper"]):.1f}" y2="{mid:.1f}" '
            f'class="bar {css}"/>'
            f'<line x1="{x(c["lower"]):.1f}" y1="{mid - 9:.1f}" x2="{x(c["lower"]):.1f}" y2="{mid + 9:.1f}" '
            f'class="bar {css}"/>'
            f'<line x1="{x(c["upper"]):.1f}" y1="{mid - 9:.1f}" x2="{x(c["upper"]):.1f}" y2="{mid + 9:.1f}" '
            f'class="bar {css}"/>'
            f'<circle cx="{x(rate):.1f}" cy="{mid:.1f}" r="8" class="dot {css}"/>'
            f'<text x="622" y="{mid + 7:.1f}" font-size="22" class="kn">{c["count"]}/{c["of"]}</text>')
    parts.append(f'<text x="{(left + right) / 2:.0f}" y="{axis_y + 50}" text-anchor="middle" font-size="18" '
                 f'class="axis">success rate, axis starts at 0.70</text>')
    parts.append(f'<text x="0" y="{CHART_VB_H - 8}" font-size="18" class="axis">'
                 f'dot: observed rate; bar: Wilson 95% interval, trials treated as independent</text>')
    parts.append("</svg>")
    return "".join(parts)


def grid_html(columns: list[dict]) -> str:
    tasks = list(columns[0]["per_task"])
    head = "".join(f"<th scope=\"col\">{esc(c['label'])}</th>" for c in columns)
    rows = [f'<tr><th scope="col" class="task">task</th>{head}</tr>']
    for task in tasks:
        cells = []
        for c in columns:
            k, n = c["per_task"][task]
            cells.append(f'<td class="{"miss" if k < n else "ok"}">{k}/{n}</td>')
        cls = ' class="focus"' if task == "lists_02" else ""
        rows.append(f'<tr{cls}><th scope="row" class="task">{esc(task)}</th>{"".join(cells)}</tr>')
    by = {c["key"]: c for c in columns}
    pooled = by["v2_baseline"]["formatting"] + by["v2_repeat"]["formatting"]
    pooled_n = by["v2_baseline"]["of"] + by["v2_repeat"]["of"]
    rows.append(f'<tr class="section"><th scope="colgroup" colspan="{len(columns) + 1}">Failure types, '
                f'small signal, few trials: v2 formatting failures {pooled}/{pooled_n} baseline trials vs '
                f'{by["v2_revised"]["formatting"]}/{by["v2_revised"]["of"]} revised</th></tr>')
    for label, field in (("formatting failures", "formatting"), ("other failures", "other")):
        cells = "".join(f'<td class="{"miss" if c[field] else "ok"}">{c[field]}/{c["of"]}</td>' for c in columns)
        rows.append(f'<tr><th scope="row" class="task">{label}</th>{cells}</tr>')
    return '<table class="grid-table">' + "".join(rows) + "</table>"


CSS = """\
:root { --ink: %(ink)s; --paper: %(paper)s; --muted: %(muted)s; --accent: %(accent)s; --warn-bg: %(warn-bg)s; --warn-ink: %(warn-ink)s; --warn-edge: %(warn-edge)s; --chrome-bg: %(chrome-bg)s; }
* { box-sizing: border-box; }
html { background: var(--chrome-bg); }
body { margin: 0; color: var(--ink); font-family: system-ui, sans-serif; }
.slide { container-type: inline-size; position: relative; overflow: hidden; width: min(100vw, 177.78vh); aspect-ratio: 16 / 9; margin: 0 auto; background: var(--paper); color: var(--ink); display: flex; flex-direction: column; }
.frame { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 1cqw; padding: 1.8cqw 2.5cqw 1.2cqw; }
.logo { position: absolute; top: 1.4cqw; right: 2.5cqw; width: 5cqw; height: auto; }
header { padding-right: 6.5cqw; }
.headline { margin: 0; font-size: 2.2cqw; line-height: 1.15; color: var(--accent); }
.subline { margin: 0.5cqw 0 0; font-size: 1.5cqw; line-height: 1.2; color: var(--muted); }
.main { display: flex; gap: 2cqw; align-items: flex-start; }
.chart { flex: 0 0 %(cqw)dcqw; width: %(cqw)dcqw; height: auto; }
.chart .grid { stroke: #bdbdbd; stroke-width: 1; }
.chart .axisline, .chart .divider { stroke: var(--muted); stroke-width: 1.5; }
.chart .divider { stroke-dasharray: 6 5; }
.chart .axis, .chart .rowdate { fill: var(--muted); }
.chart .rowlabel, .chart .kn { fill: var(--ink); font-weight: 700; }
.chart .bar { stroke-width: 4; }
.chart .dot { stroke: var(--paper); stroke-width: 2; }
.chart .v1 { stroke: var(--muted); fill: var(--muted); }
.chart .v2 { stroke: var(--accent); fill: var(--accent); }
.chart .dot.v1, .chart .dot.v2 { stroke: var(--paper); }
.grid-table { flex: 1; border-collapse: collapse; font-size: 1.05cqw; line-height: 1.2; }
.grid-table th, .grid-table td { border: 1px solid var(--muted); padding: 0.28cqw 0.5cqw; text-align: center; }
.grid-table th.task { text-align: left; font-weight: 700; }
.grid-table thead th, .grid-table tr:first-child th[scope="col"] { color: var(--accent); }
.grid-table td.miss { background: var(--warn-bg); color: var(--warn-ink); font-weight: 700; border-color: var(--warn-edge); }
.grid-table tr.focus th, .grid-table tr.focus td { border-top: 0.2cqw solid var(--accent); border-bottom: 0.2cqw solid var(--accent); }
.grid-table tr.section th { text-align: left; font-weight: 700; background: #ececec; }
.takeaway { margin: 0; font-size: 1.6cqw; line-height: 1.3; padding: 0.7cqw 1.2cqw; border: 0.15cqw solid var(--muted); }
.takeaway.unset { border: 0.25cqw dashed var(--warn-edge); background: var(--warn-bg); color: var(--warn-ink); }
.takeaway strong { margin-right: 0.8cqw; }
.limits { margin: auto 0 0; font-size: 1.25cqw; line-height: 1.25; color: var(--muted); }
@page { size: A4 landscape; margin: 6mm; }
@media print {
  html, body { margin: 0; height: auto; background: #fff; }
  .slide { width: 285mm; height: 160.3mm; margin: 0; aspect-ratio: auto; container-type: inline-size; overflow: hidden; break-inside: avoid; break-after: avoid; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
}
"""


def render(columns: list[dict], takeaway: str, logo_uri: str) -> str:
    first, sub = headline(columns)
    by = {c["key"]: c for c in columns}
    if takeaway:
        slot = f'<p class="takeaway"><strong>Takeaway</strong>{esc(takeaway)}</p>'
    else:
        slot = ('<p class="takeaway unset"><strong>Takeaway: to be written by the student.</strong>'
                'This slot is intentionally empty.</p>')
    limits = ("Limits: the same ten benchmark-informed tasks; one model; trials treated as independent; "
              "no significance claim; the first experiment "
              f"({by['v1_baseline']['date']}) and the second ({by['v2_baseline']['date']}) ran on "
              "different days, so a change of the provider over time cannot be separated.")
    css = CSS % {**TOKENS, "cqw": CHART_CQW}
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Backup slide: prompt comparison at scale</title>\n"
        f"<style>\n{css}</style>\n</head>\n<body>\n<main class=\"slide\">\n<div class=\"frame\">\n"
        f"<header><h1 class=\"headline\">{esc(first)}</h1><p class=\"subline\">{esc(sub)}</p></header>\n"
        f"<img class=\"logo\" src=\"{logo_uri}\" alt=\"{esc(LOGO_ALT)}\">\n"
        f"<div class=\"main\">{chart_svg(columns)}{grid_html(columns)}</div>\n"
        f"{slot}\n<p class=\"limits\">{esc(limits)}</p>\n</div>\n</main>\n</body>\n</html>\n"
    )


def build(v1: Path = V1_JSON, v2: Path = V2_JSON, user_text: Path = USER_TEXT, logo: Path = LOGO,
          require_user_text: bool = False) -> str:
    columns = collect(v1, v2)
    takeaway = read_takeaway(user_text)
    if require_user_text and not takeaway:
        raise SlideError(f"{user_text}: the takeaway is empty (--require-user-text)")
    return render(columns, takeaway, _logo_uri(logo))


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".backup_slide.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail when the committed page differs; write nothing")
    parser.add_argument("--require-user-text", action="store_true", help="fail while the takeaway is empty")
    parser.add_argument("--v1", type=Path, default=V1_JSON)
    parser.add_argument("--v2", type=Path, default=V2_JSON)
    parser.add_argument("--user-text", type=Path, default=USER_TEXT)
    parser.add_argument("--logo", type=Path, default=LOGO)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    try:
        page = build(args.v1, args.v2, args.user_text, args.logo, args.require_user_text)
    except SlideError as exc:
        print(f"build_backup_slide: {exc}", file=sys.stderr)
        return 1
    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError:
            print(f"build_backup_slide: {args.output} is missing; run the script without --check", file=sys.stderr)
            return 1
        if current != page:
            diff = list(difflib.unified_diff(current.splitlines(), page.splitlines(), "committed", "fresh", n=0))
            print(f"build_backup_slide: {args.output} differs from a fresh build ({len(diff)} diff lines); "
                  "rebuild and commit it", file=sys.stderr)
            return 1
        print(f"check passed: {args.output} equals a fresh build")
        return 0
    _write_atomic(args.output, page)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
