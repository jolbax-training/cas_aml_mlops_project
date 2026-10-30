"""Emit GitHub Actions annotations for the failed tests in a pytest JUnit report.

Job logs are not always readable by whoever needs the result, but annotations are: one
`::error` per failed or errored test (at most 20, messages truncated) plus a `::notice`
with the totals. Always exits 0; the no-skip guard and pytest own the job's verdict."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_ANNOTATIONS = 20
MAX_MESSAGE = 500


def _data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _property(text: str) -> str:
    return _data(text).replace(":", "%3A").replace(",", "%2C")


def _short(text: str) -> str:
    text = " | ".join(line.strip() for line in text.strip().splitlines() if line.strip())
    return text if len(text) <= MAX_MESSAGE else text[: MAX_MESSAGE - 3] + "..."


def annotations(report: Path) -> list[str]:
    if not report.is_file():
        return [f"::error title=pytest produced no JUnit report::{_data(str(report))} is missing"]
    root = ET.parse(report).getroot()
    lines = []
    totals = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    for suite in ([root] if root.tag == "testsuite" else root.iter("testsuite")):
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    failed = []
    for case in root.iter("testcase"):
        problem = case.find("failure") if case.find("failure") is not None else case.find("error")
        if problem is not None:
            failed.append((case, problem))
    for case, problem in failed[:MAX_ANNOTATIONS]:
        test_id = f"{case.get('classname')}::{case.get('name')}"
        detail = problem.get("message") or ""
        body = (problem.text or "").strip().splitlines()[-6:]
        lines.append(f"::error title={_property(test_id)}::{_data(_short(detail + chr(10) + chr(10).join(body)))}")
    if len(failed) > MAX_ANNOTATIONS:
        lines.append(f"::error title=more failures::{len(failed) - MAX_ANNOTATIONS} further failed tests not annotated")
    summary = ", ".join(f"{key}={value}" for key, value in totals.items())
    lines.append(f"::notice title=pytest totals::{_data(summary)}")
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: ci_annotate_junit.py JUNIT_XML", file=sys.stderr)
        return 2
    for line in annotations(Path(argv[0])):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
