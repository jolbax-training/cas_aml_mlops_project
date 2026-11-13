#!/usr/bin/env python3
"""Record the credential-free demo path as an asciicast v2 file and build a self-contained player.

    .venv/bin/python scripts/record_demo.py record        # needs Podman, uv env, empty run_bundles/
    .venv/bin/python scripts/record_demo.py build-player  # report/demo.html (Git-ignored)
    .venv/bin/python scripts/record_demo.py check         # validate the committed cast (offline)

The steps are the credential-free commands of docs/demo.md, run exactly as written in the
repository root with no inherited environment (`env -i`), so no key can reach them and no model
is called. Timing in the cast is synthetic (fixed typing rate, fixed pauses), so it does not
depend on machine speed. Output is scrubbed of the repository root, the home directory and
temporary paths; a secret-looking string aborts the recording instead of being masked. No
voice, no third-party recorder, no JavaScript library: the player is hand-written HTML.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
CAST = Path("presentation/recording/demo.cast")
TEMPLATE = Path("presentation/recording/player.html")
PLAYER_OUT = Path("report/demo.html")
DEMO_DOC = Path("docs/demo.md")
# The credential-free PATH of docs/demo.md (Podman first); uv is not needed after `uv sync`.
CLEAN_PATH = "/opt/podman/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
WIDTH, HEIGHT = 110, 32
TYPE_DELAY, LINE_DELAY, STEP_PAUSE = 0.035, 0.04, 1.2
MAX_OUTPUT_LINES = 60
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{6}")
RUN_PLACEHOLDER = "{run_id}"

PY = "PYTHONPATH=src .venv/bin/python -m codegen_eval"
# ("comment", text) is typed as a shell comment and not run; ("run", command, allowed exit codes).
STEPS: Sequence[tuple[Any, ...]] = (
    ("comment", "Credential-free demo path (docs/demo.md). Every command runs under env -i: no API key, no OPENROUTER_* variable."),
    ("run", "sh -c 'env | grep -c OPENROUTER'", (0, 1)),
    ("comment", "Fixture bundle with scripted model responses: it shows the tooling, not model quality."),
    ("run", f"{PY}.run_recording --scenario tool_use_and_revision --task strings_01 --trials 2 --grade", (0,)),
    ("comment", "Trace inspection reads the retained records: no model API, no Podman."),
    ("run", f"{PY}.trace_inspect list", (0,)),
    ("run", f"{PY}.trace_inspect verify {RUN_PLACEHOLDER}", (0,)),
    ("run", f"{PY}.trace_inspect show {RUN_PLACEHOLDER} --trial strings_01-t1", (0,)),
    ("comment", "Grading replay REGRADES the saved final candidates with Podman. It is not a fresh agent trial and calls no model."),
    ("run", f"{PY}.replay {RUN_PLACEHOLDER}", (0,)),
    ("comment", "The offline work-log sources check."),
    ("run", ".venv/bin/python scripts/build_work_log.py --check", (0,)),
)
SECRET_PATTERNS = (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{12,}"),
                   re.compile(r"OPENROUTER_API_KEY\s*=\s*\S+"), re.compile(r"(?i)authorization\s*:"))


class RecordError(Exception):
    """The recording cannot be made or the cast is invalid; the message is the diagnostic."""


def step_commands() -> list[str]:
    return [step[1] for step in STEPS if step[0] == "run"]


def normalize(command: str) -> str:
    """A command with its run id replaced by the placeholder docs/demo.md uses."""
    return RUN_ID.sub("<run_id>", command.replace(RUN_PLACEHOLDER, "<run_id>"))


def documented(command: str, demo_text: str) -> bool:
    """Whether the command text occurs in docs/demo.md (a trial id may be its `<trial_id>`)."""
    plain = normalize(command)
    return plain in demo_text or re.sub(r"strings_01-t\d", "<trial_id>", plain) in demo_text


# --- scrubbing and scanning --------------------------------------------------------------------

def scrubber(root: Path) -> Any:
    tmp = {str(Path(tempfile.gettempdir())), str(Path(tempfile.gettempdir()).resolve()), "/tmp", "/private/tmp"}
    replacements = [(str(root), "."), (str(root.resolve()), ".")]
    replacements += [(str(Path.home()), "~")] + [(t, "<tmp>") for t in sorted(tmp, key=len, reverse=True)]

    def scrub(text: str) -> str:
        for old, new in replacements:
            text = text.replace(old, new)
        return text
    return scrub


def scan(name: str, text: str, root: Path | None = None) -> list[str]:
    problems = [f"{name}: secret-like text ({p.pattern})" for p in SECRET_PATTERNS if p.search(text)]
    for token in ("/Users/", str(Path.home()), str(root) if root else ""):
        if token and token in text:
            problems.append(f"{name}: contains the path {token!r}")
    return problems


# --- recording -----------------------------------------------------------------------------------

class Cast:
    def __init__(self) -> None:
        self.events: list[list[Any]] = []
        self.t = 0.0

    def emit(self, text: str, delay: float) -> None:
        self.t += delay
        self.events.append([round(self.t, 3), "o", text])

    def type_line(self, text: str) -> None:
        for char in text:
            self.emit(char, TYPE_DELAY)
        self.emit("\r\n", 0.4)

    def output(self, lines: Sequence[str]) -> None:
        for line in lines[:MAX_OUTPUT_LINES]:
            self.emit(line + "\r\n", LINE_DELAY)
        if len(lines) > MAX_OUTPUT_LINES:
            self.emit(f"[... {len(lines) - MAX_OUTPUT_LINES} more lines not recorded]\r\n", LINE_DELAY)

    def render(self) -> str:
        header = {"version": 2, "width": WIDTH, "height": HEIGHT,
                  "title": "Credential-free demo path (docs/demo.md)"}
        return "\n".join([json.dumps(header)] + [json.dumps(e, ensure_ascii=False) for e in self.events]) + "\n"


def run_step(command: str, root: Path) -> tuple[int, str]:
    home = str(Path.home())
    result = subprocess.run(["env", "-i", f"HOME={home}", f"PATH={CLEAN_PATH}", "sh", "-c", command],
                            cwd=root, capture_output=True, text=True, timeout=600)
    return result.returncode, result.stdout + result.stderr


def record(root: Path = REPO_ROOT) -> Cast:
    bundles = root / "run_bundles"
    if bundles.exists() and any(bundles.iterdir()):
        raise RecordError("run_bundles/ is not empty: record in a fresh checkout or worktree so "
                          "retained evidence is never touched")
    scrub = scrubber(root)
    cast, run_id = Cast(), None
    for step in STEPS:
        if step[0] == "comment":
            cast.type_line("# " + step[1])
            cast.t += 0.3
            continue
        _, template, allowed = step
        command = template.replace(RUN_PLACEHOLDER, run_id or "")
        if RUN_PLACEHOLDER in template and not run_id:
            raise RecordError("no run id was printed by the fixture step")
        cast.type_line("$ " + command)
        code, output = run_step(command, root)
        if code not in allowed:
            raise RecordError(f"step failed with exit code {code}: {command}\n{output[-800:]}")
        lines = scrub(output).rstrip("\n").split("\n") if output.strip() else []
        problems = scan(command, "\n".join(lines))
        if problems:
            raise RecordError("; ".join(problems))
        if run_id is None:
            match = RUN_ID.search(output)
            run_id = match.group(0) if match else None
        cast.output(lines)
        cast.t += STEP_PAUSE
    return cast


# --- cast validation and player --------------------------------------------------------------------

def parse_cast(text: str) -> tuple[dict[str, Any], list[list[Any]]]:
    rows = [r for r in text.split("\n") if r]
    if not rows:
        raise RecordError("empty cast")
    try:
        header = json.loads(rows[0])
        events = [json.loads(r) for r in rows[1:]]
    except ValueError as error:
        raise RecordError(f"cast is not valid JSON lines: {error}") from error
    return header, events


def check_cast(text: str, demo_text: str | None = None, root: Path | None = None) -> list[str]:
    try:
        header, events = parse_cast(text)
    except RecordError as error:
        return [str(error)]
    problems = []
    if header.get("version") != 2 or not isinstance(header.get("width"), int) \
            or not isinstance(header.get("height"), int):
        problems.append("header must be an asciicast v2 header with width and height")
    last = 0.0
    for i, event in enumerate(events, 2):
        if not (isinstance(event, list) and len(event) == 3 and event[1] == "o"
                and isinstance(event[0], (int, float)) and isinstance(event[2], str)):
            problems.append(f"line {i}: expected [time, \"o\", text]")
            continue
        if event[0] < last:
            problems.append(f"line {i}: time goes backwards")
        last = max(last, event[0])
    transcript = "".join(e[2] for e in events if isinstance(e, list) and len(e) == 3).replace("\r\n", "\n")
    problems += scan("cast", text, root)
    if demo_text is not None:
        for line in transcript.split("\n"):
            if line.startswith("$ ") and not documented(line[2:], demo_text):
                problems.append(f"command not in {DEMO_DOC}: {line[2:]}")
    return problems


def build_player(cast_text: str, template: str) -> str:
    _, events = parse_cast(cast_text)
    transcript = "".join(e[2] for e in events).replace("\r\n", "\n")
    page = template.replace("<!--TRANSCRIPT-->", html.escape(transcript))
    return page.replace("<!--CAST-->", cast_text.replace("</", "<\\/"))


# --- commands -------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("record", help="run the steps and write presentation/recording/demo.cast")
    sub.add_parser("build-player", help="write report/demo.html from the cast and the template")
    sub.add_parser("check", help="validate the committed cast and the step list (offline)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "record":
            cast = record(root)
            problems = check_cast(cast.render(), (root / DEMO_DOC).read_text(encoding="utf-8"), root)
            if problems:
                raise RecordError("; ".join(problems))
            (root / CAST).parent.mkdir(parents=True, exist_ok=True)
            (root / CAST).write_text(cast.render(), encoding="utf-8")
            print(f"wrote {CAST} ({len(cast.events)} events, {cast.t:.1f} s)")
        elif args.command == "build-player":
            page = build_player((root / CAST).read_text(encoding="utf-8"),
                                (root / TEMPLATE).read_text(encoding="utf-8"))
            (root / PLAYER_OUT).parent.mkdir(parents=True, exist_ok=True)
            (root / PLAYER_OUT).write_text(page, encoding="utf-8")
            print(f"wrote {PLAYER_OUT}")
        else:
            demo = (root / DEMO_DOC).read_text(encoding="utf-8")
            problems = [f"step not documented in {DEMO_DOC}: {c}" for c in step_commands()
                        if not documented(c, demo)]
            cast_path = root / CAST
            if cast_path.is_file():
                problems += check_cast(cast_path.read_text(encoding="utf-8"), demo, root)
            if problems:
                for problem in problems:
                    print(f"  {problem}", file=sys.stderr)
                print("recording check FAILED", file=sys.stderr)
                return 1
            print("recording check passed" + ("" if cast_path.is_file() else " (no cast committed yet)"))
    except (RecordError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
