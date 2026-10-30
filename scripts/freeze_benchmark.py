"""Record or verify the benchmark freeze.

`--check` fails if the benchmark, references, or review no longer match
data/benchmark_v1.freeze.json. `--write` records the freeze; it refuses to replace an
existing record whose files differ (a frozen version is not edited; make a new version)
unless `--force` is given."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codegen_eval.tasks import FREEZE_FILE, check_freeze, freeze_manifest  # noqa: E402


def main(argv: list[str], root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify the recorded freeze")
    mode.add_argument("--write", action="store_true", help="record the freeze")
    parser.add_argument("--force", action="store_true", help="with --write, replace a differing record")
    args = parser.parse_args(argv)

    if args.check:
        check_freeze(root)
        print("benchmark freeze matches")
        return 0

    record = root / FREEZE_FILE
    if record.exists() and not args.force:
        try:
            check_freeze(root)
        except ValueError as error:
            print(f"refusing to overwrite {FREEZE_FILE}: {error}", file=sys.stderr)
            return 1
    manifest = freeze_manifest(root)
    record.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest["content_hash"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
