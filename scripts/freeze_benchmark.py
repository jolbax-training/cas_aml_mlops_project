"""Record or verify the benchmark freeze: `freeze_benchmark.py` writes data/benchmark_v1.freeze.json
from the current files; `freeze_benchmark.py --check` fails if they no longer match it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codegen_eval.tasks import FREEZE_FILE, check_freeze, freeze_manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        check_freeze(ROOT)
        print("benchmark freeze matches")
    else:
        manifest = freeze_manifest(ROOT)
        (ROOT / FREEZE_FILE).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(manifest["content_hash"])
