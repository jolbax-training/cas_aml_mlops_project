"""The run-flow diagrams (lifecycle activity and one-trial sequence), their text twins, and the
source tree must agree.

Offline: needs no Podman and no draw.io; it reads only the checked-in files. The helpers mirror
tests/test_architecture_diagrams.py (copied so that accepted test module stays unmodified)."""

import ast
import collections
import html
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "codegen_eval"
SVG_NS = "{http://www.w3.org/2000/svg}"
KINDS = ("activity", "sequence")
STATUSES = ("IMPLEMENTED", "PARTIAL: NO LIVE RUN YET", "PENDING")
DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>")

spec = importlib.util.spec_from_file_location("build_work_log_run_flow", REPO / "scripts" / "build_work_log.py")
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


def read(name):
    return (REPO / "docs" / name).read_text(encoding="utf-8")


def svg_text(kind):
    return read(f"run_flow_{kind}.drawio.svg")


def svg_root(kind):
    return ET.fromstring(DOCTYPE.sub("", svg_text(kind), count=1))


def model(kind):
    payload = svg_root(kind).get("content")
    assert payload, f"{kind}: the root <svg> has no embedded draw.io `content`"
    inline = ET.fromstring(payload).find("diagram").find("mxGraphModel")
    assert inline is not None, f"{kind}: the embedded diagram is compressed; turn off File > Properties > Compressed"
    return inline


def cells(kind):
    return [c for c in model(kind).iter("mxCell") if c.get("parent") not in (None, "0")]


def vertices(kind):
    return [c for c in cells(kind) if c.get("vertex")]


def edges(kind):
    return [c for c in cells(kind) if c.get("edge")]


def lines(value):
    return [part.strip() for part in html.unescape(value or "").split("\n") if part.strip()]


def rendered_texts(kind):
    return [t.text.strip() for t in svg_root(kind).iter(f"{SVG_NS}text") if (t.text or "").strip()]


def twin(kind):
    return read(f"run_flow_{kind}.md")


def label_text(kind):
    return " ".join(rendered_texts(kind))


def center(cell):
    g = cell.find("mxGeometry")
    return float(g.get("x")) + float(g.get("width")) / 2, float(g.get("y")) + float(g.get("height")) / 2


def titles(kind):
    return [lines(c.get("value"))[0] for c in vertices(kind) if lines(c.get("value"))]


def source(name):
    return (SRC / name).read_text(encoding="utf-8")


# ----------------------------------------------------------------------------- AST helpers

def _tree(name):
    return ast.parse(source(name))


def _defs(name):
    """Every function, class, and module-level or class-level assigned name in a module."""
    names = set()
    for node in ast.walk(_tree(name)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _function(name, qualified):
    """The (possibly method) function node, `Class.method` or `function`."""
    parts = qualified.split(".")
    scope = _tree(name).body
    node = None
    for part in parts:
        node = next((n for n in scope if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == part), None)
        assert node is not None, f"{name}: {qualified} not found"
        scope = node.body
    return node


def _lines(name, qualified, needle, nth=0):
    """Line numbers of calls or names whose source segment contains `needle` inside a function."""
    func = _function(name, qualified)
    found = sorted(n.lineno for n in ast.walk(func) if isinstance(n, ast.Call)
                   and needle in (ast.get_source_segment(source(name), n.func) or ""))
    assert found, f"{name}:{qualified}: no call to {needle}"
    return found[nth] if nth is not None else found


MODULES = {p.stem for p in SRC.glob("*.py")}


def _dotted(text):
    """module.attr and module.Class.method references written in backticks or as code refs."""
    refs = set()
    for token in re.findall(r"`([^`]+)`", text):
        for ref in re.findall(r"\b([a-z_]+(?:\.[A-Za-z_]+)+)\b", token):
            if ref.split(".")[0] in MODULES and not ref.endswith((".py", ".sh", ".md", ".json")):
                refs.add(ref)
    return refs


def _file_names(text):
    return set(re.findall(r"[A-Za-z0-9_./-]+\.(?:py|sh)\b", text))


def _resolves(name):
    return any(candidate.exists() for candidate in (REPO / name, SRC / name, REPO / "scripts" / name))


# ----------------------------------------------------------------------------- files and labels

@pytest.mark.parametrize("kind", KINDS)
def test_embedded_xml_decodes_and_matches_the_rendered_labels(kind):
    embedded = collections.Counter(line for c in cells(kind) if c.get("value") for line in lines(c.get("value")))
    assert embedded == collections.Counter(rendered_texts(kind))


@pytest.mark.parametrize("kind", KINDS)
def test_file_is_a_draw_io_svg_that_passes_the_unchanged_sanitizer(kind):
    text = svg_text(kind)
    assert not re.search(r"<(script|image|foreignObject|style|a)\b|href=|url\(|data:", text)
    # the default fill exports a nested var() that the sanitizer's grammar rejects: authoring rule
    assert "light-dark(#ffffff, var" not in text
    out = builder.sanitize_drawio_svg(text, f"run-flow-{kind}", "Title", "Description")
    assert "content=" not in out and "<text" in out


@pytest.mark.parametrize("kind", KINDS)
def test_authoring_rules_hold_for_every_cell(kind):
    for cell in cells(kind):
        style = cell.get("style") or ""
        assert "html=1" not in style and "whiteSpace" not in style and "image" not in style
        if cell.get("vertex") and not style.startswith("text;"):
            assert "fillColor=" in style, f"{kind}: vertex without an explicit fillColor: {cell.get('id')}"
        if cell.get("edge"):
            assert "labelBackgroundColor=none" in style, f"{kind}: edge {cell.get('id')} lacks labelBackgroundColor=none"


@pytest.mark.parametrize("kind", KINDS)
def test_every_file_and_function_name_written_in_the_diagram_or_twin_exists(kind):
    text = label_text(kind) + "\n" + twin(kind)
    names = _file_names(text)
    assert names
    assert [n for n in sorted(names) if not _resolves(n)] == []
    refs = _dotted(twin(kind))
    assert refs
    missing = []
    for ref in sorted(refs):
        module, *rest = ref.split(".")
        if len(rest) >= 2:  # Class.member: the method or field must be defined inside that class
            owner = next((x for x in _tree(module + ".py").body if isinstance(x, ast.ClassDef) and x.name == rest[0]), None)
            members = set()
            for item in (owner.body if owner else []):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    members.add(item.name)
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    members.add(item.target.id)
                elif isinstance(item, ast.Assign):
                    members.update(t.id for t in item.targets if isinstance(t, ast.Name))
            if owner is None or rest[1] not in members:
                missing.append(ref)
        elif not set(rest) <= _defs(module + ".py"):
            missing.append(ref)
    assert missing == []


@pytest.mark.parametrize("kind", KINDS)
def test_every_label_line_appears_in_the_text_twin(kind):
    text = twin(kind)
    for cell in cells(kind):
        style = cell.get("style") or ""
        if style.startswith("text;") or "swimlane" in style or "shape=umlLifeline" in style:
            continue  # titles and headers are checked by their own tests
        for line in lines(cell.get("value")):
            assert line in text, f"{kind}: {line!r} is not in the text twin"


@pytest.mark.parametrize("kind", KINDS)
def test_lane_and_lifeline_headers_are_named_in_the_twin_and_carry_a_status(kind):
    text = twin(kind)
    headers = [c for c in vertices(kind) if "swimlane" in (c.get("style") or "") or "shape=umlLifeline" in (c.get("style") or "")]
    assert len(headers) == (5 if kind == "activity" else 11)
    for cell in headers:
        ls = lines(cell.get("value"))
        assert ls[0] in text, f"{kind}: header {ls[0]!r} is not in the twin"
        assert any(s in ls for s in STATUSES) or any("EXTERNAL" in l for l in ls), f"{kind}: header without a status: {ls}"


@pytest.mark.parametrize("kind", KINDS)
def test_openrouter_is_marked_external_and_phase_2_like_the_physical_diagram(kind):
    headers = [lines(c.get("value")) for c in vertices(kind)
               if ("swimlane" in (c.get("style") or "") or "shape=umlLifeline" in (c.get("style") or ""))
               and any("OpenRouter" in l for l in lines(c.get("value")))]
    assert len(headers) == 1
    joined = " ".join(headers[0])
    assert "EXTERNAL" in joined and "PHASE 2" in joined
    openrouter = [c for c in vertices(kind) if "OpenRouter API" in (c.get("value") or "") and "swimlane" not in c.get("style")
                  and "umlLifeline" not in c.get("style") and not c.get("style").startswith("text;")]
    for cell in openrouter:
        assert "dashed=1" in cell.get("style")
        assert "PHASE 2" in cell.get("value")


@pytest.mark.parametrize("kind", KINDS)
def test_no_invented_results_urls_identifiers_or_spend(kind):
    text = label_text(kind) + "\n" + twin(kind)
    assert not re.search(r"\b(run|wf|task|ctx)_[0-9a-f]{6,}\b|sha256:[0-9a-f]{8,}", text)
    urls = set(re.findall(r"https?://[^\s)`*]+", text))
    assert urls <= {"https://openrouter.ai/api/v1/chat/completions"}, urls
    assert set(re.findall(r"CHF\s*(\d+)", text)) <= {"10", "15"}
    assert not re.search(r"\b\d+(\.\d+)?\s*%|pass rate|\bwins?\b|improv", text, re.I)
    assert "no live run has happened" in twin(kind).lower()


@pytest.mark.parametrize("kind", KINDS)
def test_no_arrow_leaves_the_container_except_to_the_host_launcher(kind):
    if kind == "activity":
        lanes = {lines(c.get("value"))[0]: c for c in vertices(kind) if "swimlane" in c.get("style")}
        box = lanes["sandbox container (TRUST BOUNDARY)"].find("mxGeometry")
        x0, x1 = float(box.get("x")), float(box.get("x")) + float(box.get("width"))
        by_id = {c.get("id"): c for c in vertices(kind)}
        inside = {i for i, c in by_id.items() if "swimlane" not in c.get("style") and x0 < center(c)[0] < x1
                  and c.get("style").startswith(("rounded", "shape"))}
        assert len(inside) == 2
        host = lanes["host CLI (trusted process)"].find("mxGeometry")
        hx0, hx1 = float(host.get("x")), float(host.get("x")) + float(host.get("width"))
        for edge in edges(kind):
            ends = {edge.get("source"), edge.get("target")}
            if ends & inside:
                other = (ends - inside).pop()
                assert hx0 < center(by_id[other])[0] < hx1, f"container node joined to {other}"
    else:
        worker = next(c for c in vertices(kind) if c.get("id") == "p_wk")
        launcher = next(c for c in vertices(kind) if c.get("id") == "p_sb")
        wx, sx = center(worker)[0], center(launcher)[0]
        touching = []
        for edge in edges(kind):
            g = edge.find("mxGeometry")
            points = {p.get("as"): float(p.get("x")) for p in g.findall("mxPoint") if p.get("as") in ("sourcePoint", "targetPoint")}
            if points and wx in points.values():
                touching.append(edge)
                assert sx in points.values(), f"message {edge.get('id')} touches worker.py without the launcher"
        assert len(touching) == 4  # two checks and two cases: payload in, report out
        boundary = next(c for c in vertices(kind) if c.get("id") == "tb")
        assert "TRUST BOUNDARY" in boundary.get("value")


# ----------------------------------------------------------------------------- activity structure

def test_activity_has_one_start_node_and_seven_final_nodes_with_their_exits():
    starts = [c for c in vertices("activity") if "shape=startState" in c.get("style")]
    ends = [c for c in vertices("activity") if "shape=endState" in c.get("style")]
    assert len(starts) == 1 and "experiment begins" in starts[0].get("value")
    assert sorted(lines(c.get("value"))[0] for c in ends) == sorted([
        "FINAL: refused", "FINAL: budget ceiling", "FINAL: incomplete after infrastructure",
        "FINAL: aborted", "FINAL: check reports unmet preconditions",
        "FINAL: compare is not a headline comparison", "FINAL: experiment complete"])
    ids = {c.get("id") for c in ends}
    for edge in edges("activity"):
        assert edge.get("source") not in ids, "a final node has an outgoing arrow"
    assert all(any(e.get("target") == i for e in edges("activity")) for i in ids)
    assert [e for e in edges("activity") if e.get("target") == starts[0].get("id")] == []


def test_every_activity_arrow_connects_two_drawn_nodes():
    ids = {c.get("id") for c in vertices("activity")}
    for edge in edges("activity"):
        assert edge.get("source") in ids and edge.get("target") in ids


def test_a_completed_run_is_an_exit_edge_not_a_final_node():
    exits = [c for c in vertices("activity") if lines(c.get("value"))[0].startswith("EXIT: run completed")]
    assert len(exits) == 1 and "shape=endState" not in exits[0].get("style")
    assert any("FINAL: refused" in t for t in titles("activity"))
    assert not any("FINAL: completed" in t for t in titles("activity"))


def test_the_checkpoint_is_a_continuing_action_not_an_ending():
    cp = next(c for c in vertices("activity") if "CHF 10 checkpoint" in (c.get("value") or ""))
    assert "the run continues" in cp.get("value") and "shape=endState" not in cp.get("style")
    assert not any("CHF 10" in t for t in titles("activity") if t.startswith("FINAL"))


def test_both_run_actions_point_to_the_single_expanded_sub_activity():
    rakes = [c for c in vertices("activity") if "[sub-activity: see frame below]" in (c.get("value") or "")]
    assert sorted(lines(c.get("value"))[0] for c in rakes) == ["run --variant baseline", "run --variant revised"]
    frames = [c for c in vertices("activity") if (c.get("value") or "").startswith("activity: run --variant V")]
    assert len(frames) == 1


def test_endings_state_exit_and_statuses_the_code_produces():
    labels = label_text("activity")
    text = twin("activity")
    cli, experiment, recording, bundle = source("experiment_cli.py"), source("experiment.py"), source("run_recording.py"), source("bundle.py")
    from codegen_eval.openrouter_cli import REFUSED
    assert REFUSED == 2 and "exit 2" in labels and "return REFUSED" in cli
    assert 'STATUS_COMPLETE = "complete"' in bundle and 'STATUS_INCOMPLETE = "incomplete"' in bundle
    for needle in ('status="interrupted"', '"started"', 'status="complete" if', '"incomplete"'):
        assert needle in experiment, needle
    assert 'f"interrupted: {type(error).__name__}"' in recording
    assert "budget_ceiling: stopped before" in recording
    for phrase in ("exit **0**", "exit **1**", "`REFUSED` (**2**)", "rewritten `interrupted`", "marker stays `started`",
                   "manifest `complete`", "manifest `incomplete`", "`not_recorded`", "`recorded`",
                   "FINAL: check reports unmet preconditions", "NOT a headline comparison"):
        assert phrase in text, phrase
    assert "NOT a headline comparison" in source("comparison.py")
    assert 'return 1 if failures else 0' in cli and "return 0 if result.complete else 1" in cli
    assert 'return 0 if result["headline_comparison"] else 1' in cli
    for label in ("manifest incomplete (budget_ceiling)", "marker incomplete", "marker interrupted (or started)",
                  "exit 2 (exit 1 if the config is unreadable)", "exit 0, manifest complete, marker complete"):
        assert label in labels, label


def test_limits_and_budget_in_the_labels_equal_the_source():
    from codegen_eval.agent_config import DEFAULT_AGENT_LIMITS
    from codegen_eval.ledger import CEILING_CHF, CHECKPOINT_CHF
    labels = label_text("activity")
    assert DEFAULT_AGENT_LIMITS.max_model_calls == 4 and "at most 4 model calls" in labels and "model calls < 4" in labels
    assert DEFAULT_AGENT_LIMITS.max_tool_attempts == 3 and "tool attempts < 3" in labels
    assert DEFAULT_AGENT_LIMITS.max_checks_per_request == 4 and "at most 4 checks" in labels
    assert CEILING_CHF == Decimal(15) and "CHF 15 ceiling" in labels
    assert CHECKPOINT_CHF == Decimal(10) and "CHF 10 checkpoint" in labels
    config = json.loads((REPO / "experiments" / "prompt_comparison_v1.json").read_text(encoding="utf-8"))
    assert len(config["schedule"]) == 30 and config["trials_per_task"] == 3 and config["trial_order"] == "task_major"
    assert "30 trials, task_major order" in labels and "plan 10 tasks x 3 trials" in labels
    seq = label_text("sequence")
    assert "model_calls < 4" in seq and "CHF 15" in seq and "at most 4 per request" in seq and "up to 4" in seq


def test_trial_outcome_names_exist_in_the_source():
    trial = source("trial.py")
    for name in ("tool_request_when_disabled", "no_final_message", "no_submission", "infrastructure_incomplete", "submitted"):
        assert name in trial
        assert name in label_text("activity") or name in label_text("sequence")
    assert "request_rejected" in source("model_client.py") and "request_rejected" in label_text("activity")
    assert "budget_ceiling" in source("openrouter_client.py")
    for status in ("transport_exhausted", "api_error", "malformed_response"):
        assert status in label_text("activity") and status in source("openrouter_client.py") + source("model_client.py")
    assert '"not_recorded"' in source("mlflow_tracking.py") and '"recorded"' in source("mlflow_tracking.py")


# ----------------------------------------------------------------------------- order claims

def test_ledger_reservation_precedes_the_send_and_settlement_follows():
    reserve = _lines("openrouter_client.py", "OpenRouterClient._attempt", "self.ledger.reserve")
    post = _lines("openrouter_client.py", "OpenRouterClient._attempt", "self.transport.post")
    interpret = _lines("openrouter_client.py", "OpenRouterClient._attempt", "self._interpret")
    assert reserve < post < interpret
    assert _lines("openrouter_client.py", "OpenRouterClient._interpret", "self._settle")
    complete = _function("openrouter_client.py", "OpenRouterClient.complete")
    assert any("input_token_bound" in (ast.get_source_segment(source("openrouter_client.py"), n) or "") for n in ast.walk(complete))
    bound = _lines("openrouter_client.py", "OpenRouterClient.complete", "input_token_bound")
    attempt = _lines("openrouter_client.py", "OpenRouterClient.complete", "self._attempt")
    assert bound < attempt  # a rejected request is never reserved or sent


def test_the_request_is_logged_before_the_send_and_the_response_after():
    complete = _function("run_recording.py", "RecordingClient.complete")
    text = source("run_recording.py")
    emitted = [n.lineno for n in ast.walk(complete) if isinstance(n, ast.Call)
               and (ast.get_source_segment(text, n.func) or "") == "self._emit"]
    inner = _lines("run_recording.py", "RecordingClient.complete", "self.inner.complete")
    assert emitted[0] < inner < emitted[-1]
    assert '"event": "request"' in text and '"event": "response"' in text
    assert "writer.append_call" in text


def test_the_run_marker_is_written_before_the_run_and_the_recording_follows_verification():
    marker = _lines("experiment.py", "run_variant", "atomic_write", 0)
    run = _lines("experiment.py", "run_variant", "run_recorded")
    verify = _lines("experiment.py", "run_variant", "verify_schedule")
    record = _lines("experiment.py", "run_variant", "record_run")
    final = _lines("experiment.py", "run_variant", "atomic_write", None)[-1]
    checks = _lines("experiment.py", "run_variant", "check_preconditions")
    assert checks < marker < run < verify < record < final
    assert "except Exception" in source("experiment.py")  # a tracking outage never stops the run
    callers = {p.name: p.read_text(encoding="utf-8").count("check_preconditions(") for p in SRC.glob("*.py")}
    # the definition and its one use in run_variant (experiment.py), and the offline `check` command
    assert {k: v for k, v in callers.items() if v} == {"experiment.py": 2, "experiment_cli.py": 1}


def test_one_run_command_runs_one_variant_and_mlflow_is_recorded_once_per_run():
    cli = source("experiment_cli.py")
    assert 'p.add_argument("--variant", required=True, choices=VARIANTS)' in cli
    assert source("experiment.py").count("record_run(bundle, variant_name)") == 1
    recording = source("run_recording.py")
    assert "mlflow" not in recording.lower()  # per-trial code never records


def test_trial_records_follow_grading_and_the_ceiling_stops_the_loop():
    run = _lines("run_recording.py", "run_recorded", "run_trial")
    grade = _lines("run_recording.py", "run_recorded", "grader")
    write = _lines("run_recording.py", "run_recorded", "writer.write_trial")
    finish = _lines("run_recording.py", "run_recorded", "writer.finish", None)
    assert run < grade < write < finish[-1]
    text = source("run_recording.py")
    assert text.index("if result.infrastructure_status == BUDGET_CEILING") > text.index("writer.write_trial")
    assert "break" in text[text.index("if result.infrastructure_status == BUDGET_CEILING"):]


def test_the_five_response_outcomes_are_checked_in_the_order_drawn():
    text = source("trial.py")
    run = text[text.index("def run_trial"):text.index("def _outcome")]
    order = [run.index(s) for s in ("REQUEST_REJECTED", "INFRASTRUCTURE_INCOMPLETE", "tool_request_when_disabled",
                                    "_handle_tool_calls(", "no_final_message", "validate_source(")]
    assert order == sorted(order)
    assert "state.model_calls < limits.max_model_calls" in run and "state.tool_attempts < limits.max_tool_attempts" in run
    assert '"auto" if tools_enabled else "none"' in run
    handler = text[text.index("def _handle_tool_calls"):]
    assert "TOOL_NAME" in handler and "next(" in handler  # only the first call named run_checks executes
    assert "continue  # the trial ends; no feedback is sent" in handler
    client = source("openrouter_client.py")
    assert 'request.tool_choice == "none"' in client and "self.tool_definitions" in client


def test_grading_starts_no_container_for_unexecuted_outcomes_and_scores_on_the_host():
    evaluate = source("evaluate.py")
    grade = evaluate[evaluate.index("def grade_trial"):evaluate.index("def count_results")]
    assert grade.index("INFRASTRUCTURE_INCOMPLETE") < grade.index("NO_SUBMISSION") < grade.index("validate_source") < grade.index("runner(trial.submission")
    assert "score_case(case, runner(" in grade
    sandbox = source("sandbox.py")
    execute = sandbox[sandbox.index("def execute_check"):sandbox.index("def run_case")]
    assert execute.index('"payload_too_large"') < execute.index("subprocess.Popen")
    assert "podman create" in sandbox.replace('"podman", "create"', "podman create") and '"start", "--attach"' in sandbox
    for module in ("sandbox.py", "worker.py"):  # expected answers never reach the launcher or the container
        assert not [n for n in ast.walk(_tree(module)) if isinstance(n, ast.Attribute) and n.attr == "expected"]
    worker = source("worker.py")
    scripts = worker[worker.index("EXECUTOR = "):]  # the code that runs in the container, not the module docstring
    assert "expected" not in scripts.lower()
    assert "run_case" in evaluate and "make_grader" in source("replay.py")


def test_checkpoint_is_logged_by_the_ledger_and_the_ceiling_test_matches_the_diagram():
    ledger = source("ledger.py")
    for func in ("reserve", "settle", "adjust"):
        assert "_log_checkpoint" in ledger[ledger.index(f"def {func}"):]
    assert "state.total + amount_chf > self.ceiling_chf" in ledger
    assert "raise BudgetCeiling" in ledger and '"event": "refusal"' in ledger


def test_comparison_and_summary_read_bundles_not_mlflow_and_summaries_are_called_by_compare():
    assert "mlflow" not in source("comparison.py").lower() and "mlflow" not in source("summary.py").lower()
    assert "summarize_bundle" in source("comparison.py") and "verify_schedule" in source("comparison.py")
    tracking = source("mlflow_tracking.py")
    assert "_find_run" in tracking  # idempotent upload: searches for an earlier upload of the digest
    assert not re.search(r"\.(get_run|get_metric_history|download_artifacts|load_table)\(", tracking)
    assert "_BLOCKING" in tracking and "NOT_FINALIZED" not in tracking[tracking.index("_BLOCKING ="):tracking.index("_BATCH")]


# ----------------------------------------------------------------------------- sequence structure

def test_sequence_participants_fragments_and_message_order():
    heads = [lines(c.get("value"))[0] for c in vertices("sequence") if "shape=umlLifeline" in c.get("style")]
    assert heads == ["run_recording.py", "trial.py", "openrouter_client.py", "ledger.py", "OpenRouter", "bundle.py",
                     "mlflow_tracking.py", "run_checks.py", "evaluate.py + contract.py", "sandbox.py + limits.py", "worker.py"]
    ops = collections.Counter(c.get("value") for c in vertices("sequence") if "shape=umlFrame" in c.get("style"))
    assert ops == {"loop": 4, "alt": 4}
    def y_of(edge):
        point = next(p for p in edge.find("mxGeometry").findall("mxPoint") if p.get("as") == "sourcePoint")
        return float(point.get("y"))
    labels = [lines(c.get("value"))[0] for c in sorted(edges("sequence"), key=y_of) if c.get("value")]
    def at(prefix):
        return next(i for i, l in enumerate(labels) if l.startswith(prefix))
    assert (at("run_trial(") < at("complete(request)") < at("append_call(request)") < at("inner.complete")
            < at("input_token_bound") < at("reserve(amount)") < at("POST chat completions") < at("settle(...)")
            < at("append_call(response)") < at("run_checks(") < at("execute_check(") < at("grade_trial(")
            < at("run_case(") < at("score_case") < at("write_trial(") < at("finish()") < at("record_run("))
    text = twin("sequence")
    for phrase in ("five outcomes", "tool_request_when_disabled", "no_final_message", "idempotent", "never read back",
                   "once per run", "`TRUST BOUNDARY; candidate container`" if False else "TRUST BOUNDARY"):
        assert phrase in text, phrase


def test_the_activity_and_sequence_views_share_the_logical_box_names():
    logical = (REPO / "docs" / "architecture_logical.md").read_text(encoding="utf-8")
    for name in ("run_recording.py", "trial.py", "openrouter_client.py", "ledger.py", "run_checks.py", "evaluate.py", "contract.py",
                 "sandbox.py", "limits.py", "worker.py", "bundle.py", "mlflow_tracking.py", "comparison.py", "summary.py",
                 "experiment.py", "experiment_cli.py"):
        assert name in logical
        assert name in twin("activity") + twin("sequence")
    for box in ("OpenRouter (external model API)", "MLflow tracking store"):
        assert box in logical and box in twin("activity")
    assert "reviewed result summaries" in logical and "reviewed result summaries" in twin("activity")


# ----------------------------------------------------------------------------- work log

def test_the_work_log_shows_both_diagrams_after_the_existing_ones():
    root = builder.REPO_ROOT
    config = builder.load_config(root, root / "docs" / "work_log.toml")
    ids = [d.id for d in config.diagrams]
    assert ids[:2] == ["architecture-logical", "architecture-physical"]
    assert ids[2:] == ["run-flow-activity", "run-flow-sequence"]
    text = builder.build_html(root, config, builder.parse_build_time("2026-11-01T12:00:00Z"), root / "report")
    builder.validate_output(text)
    positions = [text.index(f'<section id="{i}"') for i in ids]
    assert positions == sorted(positions)
    assert text.index('<nav id="sections"') < positions[0]
    for ident in ("run-flow-activity", "run-flow-sequence"):
        section = re.search(rf'<section id="{ident}".*?</section>', text, re.S).group(0)
        assert 'role="img"' in section and "<title" in section and "<desc" in section and "<text" in section
        assert "content=" not in section and "mxfile" not in section
        assert "no live run has happened" in section.lower()
    assert "run_flow_activity.drawio.svg" in text and "run_flow_sequence.md" in text  # provenance rows


# ----------------------------------------------------------------------------- failed model calls and the five outcomes

def _activity_by_title():
    return {lines(c.get("value"))[0]: c for c in vertices("activity") if lines(c.get("value"))}


def test_failed_model_calls_are_logged_before_the_outcome_is_decided():
    """RecordingClient.complete appends the response event for every return, failures included."""
    by_title = _activity_by_title()
    log = by_title["log the response"].get("id")
    decision = next(c for c in vertices("activity") if (c.get("value") or "").startswith("response outcome?")).get("id")
    out = collections.defaultdict(list)
    for e in edges("activity"):
        out[e.get("source")].append(e.get("target"))
    for title in ("ModelFailure: request_rejected", "ModelFailure: budget_ceiling", "ModelFailure: transport_exhausted,"):
        assert log in out[by_title[title].get("id")], f"{title}: does not flow into `log the response`"
        assert "trial ends: TrialResult" not in [lines(next(c for c in vertices("activity") if c.get("id") == t).get("value"))[0]
                                                 for t in out[by_title[title].get("id")]]
    assert decision in out[log]
    text = source("run_recording.py")
    complete = text[text.index("def complete"):text.index("def _usage_totals")]
    assert "isinstance(response, ModelFailure)" in complete and complete.count('"event": "response"') == 1
    assert complete.index("isinstance(response, ModelFailure)") < complete.index('"event": "response"')
    assert "the response event is appended to the call log for every outcome" in twin("activity").lower()


def test_the_response_decision_has_one_guarded_edge_per_outcome():
    ids = {c.get("id"): lines(c.get("value"))[0] for c in vertices("activity") if lines(c.get("value"))}
    decision = next(c.get("id") for c in vertices("activity") if (c.get("value") or "").startswith("response outcome?"))
    guards = {e.get("value"): ids[e.get("target")] for e in edges("activity") if e.get("source") == decision}
    assert guards == {
        "rejected": "no_submission",
        "other failure": "infrastructure_incomplete",
        "tools disabled": "tool call while tools disabled",
        "no content": "no content",
        "final content": "final content: contract.validate_source",
        "tool call, tools enabled": "run_checks.run_checks() (tool call, tools on)"}
    trial = source("trial.py")
    run = trial[trial.index("def run_trial"):trial.index("def _outcome")]
    order = [run.index(x) for x in ("REQUEST_REJECTED", "INFRASTRUCTURE_INCOMPLETE", "tool_request_when_disabled",
                                    "_handle_tool_calls(", "no_final_message", "validate_source(")]
    assert order == sorted(order)  # the five outcomes the guards stand for, in the code's order


def test_sequence_replies_are_dashed_with_an_open_head_and_calls_are_solid():
    replies = ("ModelFailure(request_rejected)", "BudgetCeiling", "ModelFailure(budget_ceiling)", "ModelResponse, or ModelFailure",
               "response", "ExecutionResult", "one bounded report", "feedback", "TrialResult", "TrialGrade", "reply, or transport failure")
    for edge in edges("sequence"):
        label = lines(edge.get("value"))[0] if edge.get("value") else ""
        style = edge.get("style")
        if edge.get("id").startswith("m") and label:
            if label.startswith(replies):
                assert "dashed=1" in style and "endArrow=open" in style, label
            else:
                assert "endArrow=block" in style, label
                if not label.startswith(("POST", "client_for")):
                    assert "dashed=1" not in style, label
