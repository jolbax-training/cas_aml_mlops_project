"""Shared helpers for the presentation-evidence tests: scripts loaded by path, a copyable repo."""

import importlib.util
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
FIXTURE = REPO / "tests" / "fixtures" / "presentation" / "live.json"
# The committed user_text.toml holds the user's own words once written; tests use this unwritten copy.
BLANK_USER_TEXT = REPO / "tests" / "fixtures" / "presentation" / "user_text_blank.toml"


def load_script(name):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def copy_repo(tmp_path):
    """The files the offline check reads, in a scratch directory a test may edit."""
    root = tmp_path / "repo"
    shutil.copytree(REPO / "docs", root / "docs")
    shutil.copytree(REPO / "presentation", root / "presentation")
    blank_user_text(root)
    return root


def blank_user_text(root):
    """Replace the copied user text with the unwritten one, so tests do not depend on what the user wrote."""
    shutil.copy(BLANK_USER_TEXT, root / "presentation" / "user_text.toml")
