"""Fail a CI job whose pytest JUnit report contains skips, errors, or no tests.

The Podman group must really run its container tests; a skip there means Podman or the
pinned image was unusable and must not pass silently."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: ci_require_no_skips.py JUNIT_XML", file=sys.stderr)
        return 2
    report = Path(argv[0])
    if not report.is_file():
        print(f"missing JUnit report: {report}", file=sys.stderr)
        return 1
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ("tests", "skipped", "failures", "errors")}
    print("junit totals:", ", ".join(f"{key}={value}" for key, value in totals.items()))
    if totals["tests"] == 0:
        print("no tests ran in the Podman group", file=sys.stderr)
        return 1
    if totals["skipped"]:
        for case in root.iter("testcase"):
            skipped = case.find("skipped")
            if skipped is not None:
                print(f"SKIPPED {case.get('classname')}::{case.get('name')}: {skipped.get('message')}",
                      file=sys.stderr)
        print("Podman-dependent tests were skipped; treating this as a failure", file=sys.stderr)
        return 1
    return 1 if totals["failures"] or totals["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
