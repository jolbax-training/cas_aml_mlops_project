"""The architecture diagrams, their text twins, and the source tree must agree.

Offline: needs no Podman and no draw.io; it reads only the checked-in files."""

import collections
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "codegen_eval"
SVG_NS = "{http://www.w3.org/2000/svg}"
NAMES = ("logical", "physical")
STATUSES = {"IMPLEMENTED", "PARTIAL: NO LIVE RUN YET", "PENDING"}
# Files under src/codegen_eval/ that the logical twin does not need to name, with the reason.
NOT_DRAWN = {"__init__.py": "package marker"}
DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>")


def read(name):
    return (REPO / "docs" / name).read_text(encoding="utf-8")


def svg_root(kind):
    return ET.fromstring(DOCTYPE.sub("", read(f"architecture_{kind}.drawio.svg"), count=1))


def model(kind):
    """The embedded mxGraphModel as an element; fails clearly if draw.io compressed it."""
    payload = svg_root(kind).get("content")
    assert payload, f"{kind}: the root <svg> has no embedded draw.io `content`"
    diagram = ET.fromstring(payload).find("diagram")
    inline = diagram.find("mxGraphModel")
    assert inline is not None, (
        f"{kind}: the embedded diagram is compressed; in draw.io turn off File > Properties > Compressed")
    return inline


def cells(kind):
    """All cells except the root pair and the layer cells (which have no rendered text)."""
    return [c for c in model(kind).iter("mxCell") if c.get("parent") not in (None, "0")]


def vertices(kind):
    return [c for c in cells(kind) if c.get("vertex") and c.get("value")]


def lines(value):
    return [part.strip() for part in html.unescape(value).split("\n") if part.strip()]


def rendered_texts(kind):
    return [t.text.strip() for t in svg_root(kind).iter(f"{SVG_NS}text") if (t.text or "").strip()]


def twin(kind):
    return read(f"architecture_{kind}.md")


@pytest.mark.parametrize("kind", NAMES)
def test_embedded_xml_decodes_and_matches_the_rendered_labels(kind):
    embedded = collections.Counter(line for c in cells(kind) if c.get("value") for line in lines(c.get("value")))
    assert embedded == collections.Counter(rendered_texts(kind))


@pytest.mark.parametrize("kind", NAMES)
def test_file_is_a_draw_io_svg_without_scripts_or_external_loads(kind):
    text = read(f"architecture_{kind}.drawio.svg")
    assert "<mxfile" not in text or "content=" in text  # editable payload is an attribute
    assert not re.search(r"<(script|image|foreignObject|style|a)\b|href=|url\(|data:", text)


def _names(text):
    return set(re.findall(r"[A-Za-z0-9_./-]+\.(?:py|sh)\b", text))


def _resolves(name):
    return any(candidate.exists() for candidate in (REPO / name, SRC / name, REPO / "scripts" / name))


@pytest.mark.parametrize("kind", NAMES)
def test_every_file_name_written_in_the_diagram_or_twin_exists(kind):
    names = _names(" ".join(rendered_texts(kind))) | _names(twin(kind))
    assert names
    assert [n for n in sorted(names) if not _resolves(n)] == []
    # directories and fixed paths named in the figure
    for path in ("prompts", "model_configs"):
        assert (SRC / path).is_dir()
    assert (REPO / "data" / "benchmark_v1.json").exists() and (REPO / ".github" / "workflows" / "ci.yml").exists()


def test_every_module_is_drawn_or_explicitly_not_drawn():
    logical = twin("logical") + " ".join(rendered_texts("logical"))
    missing = [p.name for p in sorted(SRC.glob("*.py")) if p.name not in NOT_DRAWN and p.name not in logical]
    assert missing == []
    assert "prompts/" in logical and "model_configs/" in logical
    assert all((SRC / name).exists() for name in NOT_DRAWN)


@pytest.mark.parametrize("kind", NAMES)
def test_every_box_has_a_status_or_an_external_tag(kind):
    boxes = [c for c in vertices(kind)
             if c.get("style").startswith("rounded=0;html=0;fillColor=") and "verticalAlign=top" not in c.get("style")]
    assert len(boxes) >= 10
    for cell in boxes:
        ls = lines(cell.get("value"))
        ok = ls[-1] in STATUSES or any("PHASE 2" in l or "EXTERNAL" in l for l in ls) or ls[0].startswith("STATUS KEY")
        assert ok, f"{kind}: box without a status label: {ls[0]!r}"


@pytest.mark.parametrize("kind", NAMES)
def test_every_box_title_appears_in_the_text_twin(kind):
    text = twin(kind)
    for cell in vertices(kind):
        if cell.get("style").startswith("text;"):
            continue
        title = lines(cell.get("value"))[0]
        assert title in text, f"{kind}: {title!r} is not in the text twin"


@pytest.mark.parametrize("kind", NAMES)
def test_trust_boundary_is_stated_in_diagram_and_twin(kind):
    both = (" ".join(rendered_texts(kind)) + " " + twin(kind)).lower()
    for phrase in ("no network", "no credentials", "no mlflow", "no podman"):
        assert phrase in both, (kind, phrase)
    assert "trust boundary" in both


def test_physical_twin_marks_both_phases_and_the_external_subsystems():
    text = twin("physical")
    for phrase in ("PHASE 1", "PHASE 2", "EXTERNAL", "OpenRouter", "GitHub Actions", "IMAGE REGISTRIES",
                   "127.0.0.1", "No live", "no live"):
        assert phrase in text, phrase
    labels = " ".join(rendered_texts("physical"))
    assert labels.count("PHASE 2") >= 5 and "EXTERNAL" in labels


@pytest.mark.parametrize("kind", NAMES)
def test_no_invented_results_urls_or_identifiers(kind):
    text = " ".join(rendered_texts(kind)) + "\n" + twin(kind)
    assert not re.search(r"\b(run|wf|task|ctx)_[0-9a-f]{6,}\b|sha256:[0-9a-f]{8,}", text)
    urls = set(re.findall(r"https?://[^\s)`*]+", text))
    assert urls <= {"https://openrouter.ai/api/v1/chat/completions"}, urls
    assert set(re.findall(r"CHF\s*(\d+)", text)) <= {"10", "15"}
    assert not re.search(r"\b\d+(\.\d+)?\s*%|pass rate|\bwins?\b|improv", text, re.I)


def test_claims_match_the_source():
    sandbox = (SRC / "sandbox.py").read_text(encoding="utf-8")
    twin_text = twin("physical")
    for flag, wording in (("--network=none", "--network=none"), ("--read-only", "read-only root"),
                          ("--cap-drop=ALL", "--cap-drop=ALL"), ("no-new-privileges", "no-new-privileges"),
                          ("--user=65534", "user 65534"), ("noexec", "noexec")):
        assert flag in sandbox and wording in twin_text, flag
    script = (REPO / "scripts" / "mlflow_service.sh").read_text(encoding="utf-8")
    assert '--publish "127.0.0.1:' in script and "ghcr.io/mlflow/mlflow@sha256:" in script
    assert "127.0.0.1:5000" in twin_text and "mlflow_data" in script
    ledger = (SRC / "ledger.py").read_text(encoding="utf-8")
    assert 'CEILING_CHF = Decimal("15")' in ledger and 'CHECKPOINT_CHF = Decimal("10")' in ledger
    assert "https://openrouter.ai/api/v1/chat/completions" in (SRC / "openrouter_config.py").read_text(encoding="utf-8")
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert re.search(r"^  offline:", workflow, re.M) and re.search(r"^  podman:", workflow, re.M)
    assert workflow.count("runs-on: ubuntu-24.04") == 2


def test_flow_claims_match_the_imports():
    imports = {p.name: p.read_text(encoding="utf-8") for p in SRC.glob("*.py")}
    # comparison and summaries read bundles, never MLflow
    assert "mlflow" not in imports["comparison.py"].lower() and "mlflow" not in imports["summary.py"].lower()
    # the recorder is built only by experiment_cli.py and injected as a callable
    users = sorted(n for n, t in imports.items() if re.search(r"import[^\n]*mlflow_tracking|from codegen_eval\.mlflow_tracking|from codegen_eval import[^\n]*mlflow_tracking", t))
    assert users == ["experiment_cli.py"], users
    # nothing reads MLflow back: the tracking module only creates, logs, and uploads
    tracking = imports["mlflow_tracking.py"]
    assert not re.search(r"\.(get_run|get_metric_history|download_artifacts|load_table)\(", tracking)
    # the key is read from the environment only by the two CLIs
    key_readers = sorted(n for n, t in imports.items() if "OPENROUTER_API_KEY" in t or "API_KEY_ENV" in t)
    assert set(key_readers) <= {"openrouter_cli.py", "experiment_cli.py"}, key_readers
    # trace inspection imports only the bundle reader
    assert re.findall(r"from codegen_eval\.(\w+)", imports["trace_inspect.py"]) == ["bundle"]
    # replay grades through evaluate and the sandbox with no model client
    assert "evaluate" in imports["replay.py"] and "openrouter_client" not in imports["replay.py"]
    # the ledger is reserved by the OpenRouter client before a send
    assert "self.ledger.reserve" in imports["openrouter_client.py"]
    # run_checks never reads the task's hidden cases (it uses the function name and signature)
    assert not re.search(r"\.cases\b", imports["run_checks.py"])


def _old_figure_statuses():
    svg = (REPO / "docs" / "work_log_architecture.svg").read_text(encoding="utf-8")
    found = {}
    for kind, body in re.findall(r'<g class="arch-box arch-(impl|part|plan)">(.*?)</g>', svg, re.S):
        status = {"impl": "IMPLEMENTED", "part": "PARTIAL: NO LIVE RUN YET", "plan": "PENDING"}[kind]
        for name in re.findall(r"\b[a-z_]+\.py\b", body):
            found[name] = status
    return found


def test_logical_diagram_agrees_with_the_work_log_figure():
    old = _old_figure_statuses()
    new = {}
    for cell in vertices("logical"):
        ls = lines(cell.get("value"))
        if ls[-1] in STATUSES:
            for name in re.findall(r"\b[a-z_]+\.py\b", " ".join(ls)):
                new[name] = ls[-1]
    assert old, "the old figure lists no modules"
    # every module the work-log figure names is in the logical diagram, with the same status
    assert [n for n in old if n not in new] == []
    assert {n: (old[n], new[n]) for n in old if old[n] != new[n]} == {}
    old_twin = read("work_log_architecture.md")
    assert [n for n in _names(old_twin) if n.endswith(".py") and n not in twin("logical")] == []
