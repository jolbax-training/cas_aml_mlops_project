"""The prompt-comparison experiment: its versioned configuration, the start-of-run
preconditions, and the schedule runner that writes one bundle per variant.

The configuration (`experiments/prompt_comparison_v1.json`) names the variants, the frozen
benchmark and settings hashes, and the 10 x 3 schedule. Nothing here makes a model call by
itself: `run_variant` takes a client factory, so offline tests drive it with fixtures or a fake
transport, and only the trusted CLI (`experiment_cli`) builds the paid client.

The runner refuses to start unless every precondition holds. Preconditions are re-derived from
evidence on every start (the retained smoke bundle is recomputed, not trusted from a note), and
all failures are reported together."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from codegen_eval.agent_config import (
    BASELINE_PROMPT, DEFAULT_AGENT_LIMITS, PROMPT_DIR, AgentLimits, AgentPrompt, load_prompt,
)
from codegen_eval.bundle import (
    DEFAULT_BUNDLE_ROOT, GRADE_GRADED, GRADE_INCOMPLETE, STATUS_COMPLETE, BundleError, Grader,
    Verification, atomic_write, load_manifest, load_trial, new_run_id, sha256_bytes, sha256_file,
    utc_now, verify_bundle,
)
from codegen_eval.ledger import Ledger
from codegen_eval.limits import DEFAULT_LIMITS, ExecutionLimits
from codegen_eval.model_client import ModelClient
from codegen_eval.openrouter_config import (
    DEFAULT_MODEL_CONFIG, ModelConfig, PriceInputs, load_model_config,
)
from codegen_eval.run_recording import ROOT, freeze_content_hash, run_recorded
from codegen_eval.sandbox import (
    HOST_PLATFORM, ExecutionResult, execute_check, image_for_platform, platform_of_image,
)
from codegen_eval.tasks import Task, check_freeze, load_benchmark

CONFIG_SCHEMA_VERSION = 1
EXPERIMENT_ID = "prompt_comparison_v1"
EXPERIMENT_DIR = ROOT / "experiments"
DEFAULT_CONFIG = EXPERIMENT_DIR / f"{EXPERIMENT_ID}.json"
DEFAULT_EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"
DEFAULT_BENCHMARK = ROOT / "data" / "benchmark_v1.json"
PROBES_FILE = "probes.json"
FREEZE_RECORD_FILE = "settings_freeze.json"
JUNIT_FILE = "probes.junit.xml"

TRIALS_PER_TASK = 3
TRIAL_ORDER = "task_major"           # all trials of one task, then the next task
BASELINE, REVISED = "baseline", "revised"
VARIANTS = (BASELINE, REVISED)
CHECKS_PER_TRIAL = 4                 # three ordinary cases and one edge case per task

# The smoke trace must show the pre-send bound at least this far above the provider's
# reported prompt tokens on every sent attempt (task 4.4: "at or above the actual count with
# margin"). It is a project choice, recorded with the calibration, not a provider fact.
MIN_BOUND_RATIO = 1.10


class ExperimentError(Exception):
    """The configuration or an evidence file is unusable."""


# --- configuration -----------------------------------------------------------------

def _canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: Any) -> str:
    return hashlib.sha256(_canonical(data)).hexdigest()


def evaluator_code_sha256() -> str:
    """Hash of the evaluator's Python modules only. Prompts are excluded on purpose: adding
    the revised prompt file is the intended change between the variants and must not look
    like a change to the evaluator (probe evidence and comparability bind to this hash)."""
    package = Path(__file__).resolve().parent
    lines = "".join(f"{path.relative_to(package).as_posix()}\t{sha256_file(path)}\n"
                    for path in sorted(package.rglob("*.py")) if "__pycache__" not in path.parts)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def prompt_file_hashes() -> dict[str, str]:
    """Every versioned prompt file present now, by file stem."""
    return {path.stem: sha256_file(path) for path in sorted(PROMPT_DIR.glob("*.md"))}


def settings_hash(model: ModelConfig, agent_limits: AgentLimits,
                  execution_limits: ExecutionLimits, container_platform: str = HOST_PLATFORM) -> str:
    """One hash over everything that must stay fixed between the variants besides the prompt.
    The image is the one pinned for the recorded container platform, not for this host."""
    return _sha256({"model_config_hash": model.config_hash(),
                    "agent_limits_hash": agent_limits.config_hash(),
                    "execution_limits_hash": execution_limits.config_hash(),
                    "container_image": image_for_platform(container_platform)})


def build_schedule(tasks: Sequence[Task], trials_per_task: int = TRIALS_PER_TASK) -> list[dict[str, str]]:
    """Every scheduled task/trial, in run order. Trial ids are the ones `run_recorded` plans."""
    return [{"task_id": t.id, "trial_id": f"{t.id}-t{n}"}
            for t in tasks for n in range(1, trials_per_task + 1)]


def _variant_entry(name: str, prompt_version: str | None) -> dict[str, Any]:
    if prompt_version is None:
        return {"name": name, "prompt_version": None, "prompt_sha256": None}
    return {"name": name, "prompt_version": prompt_version,
            "prompt_sha256": load_prompt(prompt_version).sha256}


def build_config(benchmark_path: str | Path = DEFAULT_BENCHMARK, *,
                 model_config_version: str = DEFAULT_MODEL_CONFIG,
                 baseline_prompt: str = BASELINE_PROMPT, revised_prompt: str | None = None,
                 agent_limits: AgentLimits = DEFAULT_AGENT_LIMITS,
                 execution_limits: ExecutionLimits = DEFAULT_LIMITS,
                 container_platform: str = HOST_PLATFORM) -> dict[str, Any]:
    """The configuration as it should be recorded now. The revised prompt stays unset until a
    revision has been written from inspected baseline failures. The configuration names the
    platform the experiment will run on and the image pinned for it, so checking it for drift
    gives the same answer on every host; `check_preconditions` refuses a different host."""
    path = Path(benchmark_path)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    model = load_model_config(model_config_version)
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        relative = path.name
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "benchmark": {"file": relative, "version": envelope.get("benchmark_version"),
                      "sha256": sha256_file(path),
                      "freeze_content_hash": freeze_content_hash(path)},
        "settings": {"model_config_version": model.config_version,
                     "model_config_hash": model.config_hash(),
                     "agent_limits_hash": agent_limits.config_hash(),
                     "execution_limits_hash": execution_limits.config_hash(),
                     "container_platform": container_platform,
                     "container_image": image_for_platform(container_platform),
                     "settings_hash": settings_hash(model, agent_limits, execution_limits,
                                                    container_platform)},
        "trials_per_task": TRIALS_PER_TASK,
        "trial_order": TRIAL_ORDER,
        "variants": [_variant_entry(BASELINE, baseline_prompt),
                     _variant_entry(REVISED, revised_prompt)],
        "schedule": build_schedule(load_benchmark(path)),
    }


_CONFIG_KEYS = {"schema_version", "experiment_id", "benchmark", "settings", "trials_per_task",
                "trial_order", "variants", "schedule"}


@dataclass(frozen=True)
class ExperimentConfig:
    data: Mapping[str, Any]
    sha256: str          # of the canonical content, recorded with every run

    @property
    def experiment_id(self) -> str:
        return self.data["experiment_id"]

    @property
    def schedule(self) -> list[dict[str, str]]:
        return [dict(item) for item in self.data["schedule"]]

    @property
    def schedule_sha256(self) -> str:
        return _sha256(self.data["schedule"])

    def variant(self, name: str) -> dict[str, Any]:
        for entry in self.data["variants"]:
            if entry["name"] == name:
                return entry
        raise ExperimentError(f"unknown variant {name!r}; expected one of {list(VARIANTS)}")


def parse_config(data: Any) -> ExperimentConfig:
    """Validate the shape only; whether it still matches the repository is `config_drift`."""
    if not isinstance(data, dict) or set(data) != _CONFIG_KEYS:
        raise ExperimentError(f"experiment config must have exactly these fields: {sorted(_CONFIG_KEYS)}")
    if data["schema_version"] != CONFIG_SCHEMA_VERSION:
        raise ExperimentError(f"unsupported config schema version {data['schema_version']!r}")
    variants = data["variants"]
    if not isinstance(variants, list) or [v.get("name") for v in variants] != list(VARIANTS):
        raise ExperimentError(f"variants must be exactly {list(VARIANTS)}, in that order")
    for entry in variants:
        if set(entry) != {"name", "prompt_version", "prompt_sha256"} or \
                (entry["prompt_version"] is None) != (entry["prompt_sha256"] is None):
            raise ExperimentError(f"variant {entry.get('name')!r} must name a prompt version and "
                                  "its hash together, or neither")
    schedule = data["schedule"]
    ids = [item.get("trial_id") for item in schedule] if isinstance(schedule, list) else []
    if not ids or len(set(ids)) != len(ids) or len(ids) != len({i["task_id"] for i in schedule}) \
            * data["trials_per_task"]:
        raise ExperimentError("schedule must list each task's trials once, with unique trial ids")
    for key in ("benchmark", "settings"):
        if not isinstance(data[key], dict):
            raise ExperimentError(f"{key} must be an object")
    return ExperimentConfig(data, _sha256(data))


def load_config(path: str | Path = DEFAULT_CONFIG) -> ExperimentConfig:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ExperimentError(f"cannot read experiment config {path}: {error}") from error
    return parse_config(data)


def write_config(data: Mapping[str, Any], path: str | Path = DEFAULT_CONFIG) -> Path:
    parse_config(dict(data))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n")
    return target


def config_drift(config: ExperimentConfig, *, benchmark_path: str | Path = DEFAULT_BENCHMARK,
                 agent_limits: AgentLimits = DEFAULT_AGENT_LIMITS,
                 execution_limits: ExecutionLimits = DEFAULT_LIMITS) -> list[str]:
    """Differences between the recorded configuration and the repository as it is now. Any
    difference means the runs would not be the ones the configuration describes."""
    data = config.data
    try:
        current = build_config(benchmark_path,
                               container_platform=str(data["settings"].get("container_platform",
                                                                           HOST_PLATFORM)),
                               model_config_version=data["settings"].get("model_config_version",
                                                                          DEFAULT_MODEL_CONFIG),
                               baseline_prompt=config.variant(BASELINE)["prompt_version"] or BASELINE_PROMPT,
                               revised_prompt=config.variant(REVISED)["prompt_version"],
                               agent_limits=agent_limits, execution_limits=execution_limits)
    except (OSError, ValueError, RuntimeError, BundleError) as error:
        return [f"cannot rebuild the configuration to compare ({error})"]
    drift = []
    for section in ("benchmark", "settings", "variants", "trials_per_task", "trial_order", "schedule"):
        if data[section] != current[section]:
            drift.append(f"{section} differs from the repository's current state")
    return drift


# --- evidence: probes, calibration, settings freeze ---------------------------------

def _read_evidence(path: Path, what: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise ExperimentError(f"{what} evidence not found at {path}") from None
    except ValueError:
        raise ExperimentError(f"{what} evidence at {path} is not valid JSON") from None
    if not isinstance(data, dict):
        raise ExperimentError(f"{what} evidence at {path} is not an object")
    return data


def write_probes_evidence(evidence_dir: str | Path, counts: Mapping[str, int], *,
                          command: str, junit_xml: str | None = None,
                          container_platform: str = HOST_PLATFORM) -> Path:
    """Record one run of the sandbox probe suite, bound to the evaluator code it ran against.
    The junit report is kept beside the record and its SHA-256 stored in it, so the counts
    can be checked against the report afterwards."""
    directory = Path(evidence_dir)
    directory.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "schema_version": 1, "recorded_at": utc_now(), "command": command,
        "evaluator_code_sha256": evaluator_code_sha256(),
        "container_platform": container_platform, "container_image": image_for_platform(container_platform),
        **{key: int(counts[key]) for key in ("tests", "failures", "errors", "skipped")}}
    if junit_xml is not None:
        data = junit_xml.encode("utf-8")
        atomic_write(directory / JUNIT_FILE, data)
        record["junit_file"], record["junit_sha256"] = JUNIT_FILE, sha256_bytes(data)
    path = directory / PROBES_FILE
    atomic_write(path, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return path


def probes_problems(evidence_dir: str | Path, host_platform: str = HOST_PLATFORM) -> list[str]:
    try:
        record = _read_evidence(Path(evidence_dir) / PROBES_FILE, "probe")
    except ExperimentError as error:
        return [str(error)]
    problems = []
    for key in ("failures", "errors", "skipped"):
        if record.get(key) != 0:
            problems.append(f"probe run has {key}={record.get(key)!r}; all must be 0")
    tests = record.get("tests")
    if not isinstance(tests, int) or isinstance(tests, bool) or tests <= 0:
        problems.append("probe run recorded no tests")
    if record.get("evaluator_code_sha256") != evaluator_code_sha256():
        problems.append("probe evidence is for different evaluator code; re-run the probes")
    if record.get("container_image") != image_for_platform(host_platform):
        recorded = platform_of_image(str(record.get("container_image")))
        if recorded is None:
            problems.append("probe evidence names no pinned container image; re-run the probes "
                            f"on this host ({host_platform})")
        else:
            problems.append(f"probe evidence is for container platform {recorded}, but this host is "
                            f"{host_platform}; re-run the probes on this host")
    junit = Path(evidence_dir) / str(record.get("junit_file") or JUNIT_FILE)
    try:
        matches = sha256_file(junit) == record.get("junit_sha256")
    except OSError:
        matches = False
    if not matches:
        problems.append("the retained junit report is missing or does not match the probe record")
    return problems


@dataclass(frozen=True)
class Calibration:
    """The pre-send input bound against the provider's reported prompt tokens, per attempt."""

    ok: bool
    problems: tuple[str, ...]
    sent_attempts: int
    ratios: tuple[float, ...]            # input_token_bound / prompt_tokens, in attempt order
    min_ratio: float | None
    max_ratio: float | None
    max_bound: int | None
    fourth_call_observed: bool           # the longest-history call is the one most at risk
    ascii_chars_per_token: float
    required_min_ratio: float = MIN_BOUND_RATIO

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "problems": list(self.problems), "sent_attempts": self.sent_attempts,
                "ratios": list(self.ratios), "min_ratio": self.min_ratio, "max_ratio": self.max_ratio,
                "max_bound": self.max_bound, "fourth_call_observed": self.fourth_call_observed,
                "ascii_chars_per_token": self.ascii_chars_per_token,
                "required_min_ratio": self.required_min_ratio}


def calibrate(bundle_dir: str | Path, model: ModelConfig) -> Calibration:
    """Check a retained smoke bundle and calibrate the pre-send bound from it (task 4.4).

    Every sent attempt must report `prompt_tokens`; the bound must exceed them by at least
    `MIN_BOUND_RATIO`; the smoke must have been made with exactly the settings being frozen;
    and nothing may have been rejected before sending. The trace must show a tool call, a
    final-only call (`tool_choice: none`), and a final submission within the output cap."""
    path = Path(bundle_dir)
    problems: list[str] = []
    ratios: list[float] = []
    bounds: list[int] = []
    fourth = False
    verification = verify_bundle(path)
    if verification.run_id is None:
        return Calibration(False, tuple(f"{p.kind}: {p.detail}" for p in verification.problems),
                           0, (), None, None, None, False, model.input_bound_ascii_chars_per_token)
    if not verification.recorded:
        problems.append("the smoke bundle has no recorded trial")
    problems += [f"smoke bundle: {p.kind}: {p.detail}" for p in verification.problems
                 if p.kind != "run_not_finalized" or len(verification.problems) == 1]
    identity = load_manifest(path).get("identity", {})
    smoke_model = identity.get("model", {})
    if smoke_model.get("client") != "openrouter":
        problems.append("the smoke bundle was not made with the OpenRouter client")
    if smoke_model.get("config_hash") != model.config_hash():
        problems.append("the smoke ran with different model settings than the ones being frozen")
    for trial_id in verification.recorded:
        try:
            record = load_trial(path, trial_id)
        except BundleError as error:
            problems.append(f"{trial_id}: {error}")
            continue
        if record.get("status") != "submitted":
            problems.append(f"{trial_id}: the smoke trial did not end in a final submission")
        if not record.get("tool_attempts"):
            problems.append(f"{trial_id}: the smoke trace shows no tool call")
        if not any(r.get("tool_choice") == "none" for r in record.get("requests", [])):
            problems.append(f"{trial_id}: the smoke trace shows no final-only call (tool_choice none)")
        fourth = fourth or len(record.get("requests", [])) >= 4
        for attempt in record.get("attempts", []):
            if attempt.get("outcome") == "pre_send_rejected":
                problems.append(f"{trial_id}: the pre-send check rejected a request; the bound is "
                                "too pessimistic for realistic calls")
                continue
            if attempt.get("sent") is False:
                continue
            prompt, bound = attempt.get("prompt_tokens"), attempt.get("input_token_bound")
            if not isinstance(prompt, (int, float)) or isinstance(prompt, bool) or prompt <= 0 \
                    or not isinstance(bound, int):
                problems.append(f"{trial_id}: call {attempt.get('call')} has no reported "
                                "prompt_tokens to calibrate against")
                continue
            bounds.append(bound)
            ratios.append(round(bound / prompt, 3))
            completion = attempt.get("completion_tokens")
            if isinstance(completion, (int, float)) and completion > model.max_output_tokens:
                problems.append(f"{trial_id}: output exceeded {model.max_output_tokens} tokens")
    if not ratios:
        problems.append("no sent attempt reports prompt_tokens, so the bound cannot be calibrated")
    elif min(ratios) < MIN_BOUND_RATIO:
        problems.append(f"the bound is only {min(ratios)}x the reported prompt tokens on at least one "
                        f"attempt; it must be at least {MIN_BOUND_RATIO}x (lower "
                        "input_bound_ascii_chars_per_token or use a verified tokenizer, then re-smoke)")
    if bounds and max(bounds) > model.max_input_tokens:
        problems.append("a sent request's bound exceeds the input limit")
    return Calibration(not problems, tuple(dict.fromkeys(problems)), len(ratios), tuple(ratios),
                       min(ratios) if ratios else None, max(ratios) if ratios else None,
                       max(bounds) if bounds else None, fourth,
                       model.input_bound_ascii_chars_per_token)


def write_settings_freeze(config: ExperimentConfig, smoke_bundle: str | Path,
                          evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR, *,
                          benchmark_path: str | Path = DEFAULT_BENCHMARK,
                          model: ModelConfig | None = None, note: str = "") -> Path:
    """Record the settings freeze. Refuses unless the smoke bundle calibrates and the
    configuration still matches the repository, so a freeze record always has both behind it."""
    model = model or load_model_config(config.data["settings"]["model_config_version"])
    bundle = Path(smoke_bundle).resolve()
    calibration = calibrate(bundle, model)
    if not calibration.ok:
        raise ExperimentError("calibration gate failed: " + "; ".join(calibration.problems))
    drift = config_drift(config, benchmark_path=benchmark_path)
    if drift:
        raise ExperimentError("configuration is out of date: " + "; ".join(drift))
    record = {"schema_version": 1, "frozen_at": utc_now(), "experiment_id": config.experiment_id,
              "config_sha256": config.sha256,
              "settings_hash": config.data["settings"]["settings_hash"],
              "model_config_hash": model.config_hash(),
              "smoke": {"bundle": str(bundle), "run_id": load_manifest(bundle)["run_id"],
                        "manifest_sha256": sha256_file(bundle / "manifest.json"),
                        "mode": (load_manifest(bundle).get("identity", {}).get("smoke") or {})
                        .get("mode", "standard")},
              "calibration": calibration.to_dict(), "decision": "pass", "note": note}
    path = Path(evidence_dir) / FREEZE_RECORD_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return path


# --- preconditions -----------------------------------------------------------------

@dataclass(frozen=True)
class Failure:
    check: str
    detail: str


class PreconditionsFailed(Exception):
    def __init__(self, failures: Sequence[Failure]) -> None:
        self.failures = tuple(failures)
        super().__init__("; ".join(f"{f.check}: {f.detail}" for f in failures))


def physical_attempt_cap(trials: int, limits: AgentLimits, model: ModelConfig) -> int:
    """Most physical attempts a variant can make: every logical call plus every allowed retry."""
    return trials * (limits.max_model_calls + model.max_retries_per_trial)


def _sidecar_path(bundle_root: Path, run_id: str) -> Path:
    return bundle_root / f"{run_id}.experiment.json"


def prior_runs(bundle_root: str | Path, experiment_id: str) -> list[dict[str, Any]]:
    """Experiment run records already written under the bundle root (any status)."""
    root = Path(bundle_root)
    records = []
    for path in sorted(root.glob("*.experiment.json")) if root.is_dir() else []:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            # Unreadable: possibly an earlier spend, so it blocks every variant (see prior_run).
            records.append({"run_id": path.name, "experiment_id": experiment_id, "variant": None,
                            "status": "unreadable"})
            continue
        if record.get("experiment_id") == experiment_id:
            records.append(record)
    return records


def _smoke_image(bundle: Path) -> str | None:
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        return manifest["identity"]["container_image"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def check_preconditions(
    config: ExperimentConfig, variant_name: str, *,
    ledger: Ledger, prices: PriceInputs | None, accept_cost: bool, api_key: str | None,
    evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR,
    bundle_root: str | Path = DEFAULT_BUNDLE_ROOT,
    benchmark_path: str | Path = DEFAULT_BENCHMARK,
    smoke_bundle: str | Path | None = None,
    agent_limits: AgentLimits = DEFAULT_AGENT_LIMITS,
    execution_limits: ExecutionLimits = DEFAULT_LIMITS,
    allow_rerun: bool = False,
    host_platform: str = HOST_PLATFORM,
) -> list[Failure]:
    """Every unmet precondition for starting `variant_name`; empty means the run may start.
    `host_platform` is this machine's architecture (a parameter so tests can simulate another)."""
    failures: list[Failure] = []

    def fail(check: str, detail: str) -> None:
        failures.append(Failure(check, detail))

    if not accept_cost:
        fail("cost_acceptance", "this run makes paid calls; pass the explicit cost acceptance")
    if not api_key:
        fail("api_key", "no API key was supplied")
    try:
        variant = config.variant(variant_name)
    except ExperimentError as error:
        fail("variant", str(error))
        return failures
    if variant["prompt_version"] is None:
        fail("variant_prompt", f"the {variant_name} variant has no versioned prompt yet "
                               "(the revised prompt needs inspected baseline failures first)")

    # Settings: the configuration must still describe the repository.
    for detail in config_drift(config, benchmark_path=benchmark_path, agent_limits=agent_limits,
                               execution_limits=execution_limits):
        fail("config_current", detail)

    # Host: the configuration records the platform it was built for; candidates would run in
    # the image pinned for this host, which must be that same image.
    recorded_platform = config.data["settings"].get("container_platform")
    try:
        host_image = image_for_platform(host_platform)
    except RuntimeError as error:
        fail("container_host", str(error))
    else:
        if config.data["settings"].get("container_image") != host_image:
            fail("container_host", f"the configuration is for container platform {recorded_platform}, "
                                   f"but this host is {host_platform}; run on a {recorded_platform} host "
                                   "or rebuild and re-freeze the configuration for this one")

    # Benchmark freeze: a recorded, still-matching freeze whose hash the configuration names.
    try:
        root = Path(benchmark_path).resolve().parent.parent
        check_freeze(root)
        recorded = config.data["benchmark"].get("freeze_content_hash")
        if not recorded:
            fail("benchmark_freeze", "the configuration records no benchmark freeze hash")
    except (ValueError, OSError) as error:
        fail("benchmark_freeze", f"benchmark is not frozen or no longer matches its freeze: {error}")

    for detail in probes_problems(evidence_dir, host_platform):
        fail("probes", detail)

    # Settings freeze, retained smoke trace, calibration: recomputed from the bundle.
    model = None
    try:
        model = load_model_config(config.data["settings"]["model_config_version"])
    except (ValueError, KeyError) as error:
        fail("settings_frozen", f"model configuration is unusable: {error}")
    freeze: dict[str, Any] | None = None
    try:
        freeze = _read_evidence(Path(evidence_dir) / FREEZE_RECORD_FILE, "settings-freeze")
    except ExperimentError as error:
        fail("settings_frozen", str(error))
    if freeze is not None:
        if freeze.get("decision") != "pass":
            fail("settings_frozen", "the freeze record does not record a passing decision")
        if freeze.get("experiment_id") != config.experiment_id or \
                freeze.get("settings_hash") != config.data["settings"].get("settings_hash"):
            fail("settings_frozen", "the freeze record is for different settings than the configuration")
        if model is not None and freeze.get("model_config_hash") != model.config_hash():
            fail("settings_frozen", "model settings changed after the freeze")
        smoke = freeze.get("smoke") if isinstance(freeze.get("smoke"), dict) else {}
        bundle = Path(smoke_bundle) if smoke_bundle else Path(smoke.get("bundle") or "")
        if not (bundle / "manifest.json").is_file():
            fail("smoke_trace", f"the retained smoke bundle is missing ({bundle})")
        else:
            if sha256_file(bundle / "manifest.json") != smoke.get("manifest_sha256"):
                fail("smoke_trace", "the smoke bundle differs from the one recorded at the freeze")
            smoke_image = _smoke_image(bundle)
            if smoke_image != config.data["settings"].get("container_image"):
                fail("settings_frozen", "the smoke trace ran in a different container image than the "
                                        f"configuration records ({smoke_image or 'none recorded'})")
            if model is not None:
                calibration = calibrate(bundle, model)
                for detail in calibration.problems:
                    fail("calibration", detail)

    # Budget: the ledger plus the worst case of everything still to run must fit the ceiling.
    if prices is None:
        fail("budget_projection", "price inputs are required to project the cost")
    elif model is not None:
        done = {r.get("variant") for r in prior_runs(bundle_root, config.experiment_id)
                if r.get("status") == "complete"}
        remaining = [v for v in VARIANTS if v == variant_name or v not in done]
        trials = len(config.schedule)
        attempts = len(remaining) * physical_attempt_cap(trials, agent_limits, model)
        projected = ledger.state().total + attempts * prices.reservation_chf(model)
        if projected > ledger.ceiling_chf:
            fail("budget_projection", f"projected worst case CHF {projected:.4f} ({attempts} "
                                      f"attempts) exceeds the CHF {ledger.ceiling_chf} ceiling")

    if not allow_rerun:
        for record in prior_runs(bundle_root, config.experiment_id):
            if record.get("status") == "unreadable":
                fail("prior_run", f"an unreadable run marker ({record.get('run_id')}) may hide "
                                  "an earlier spend; inspect it, then allow_rerun")
            elif record.get("variant") == variant_name:
                fail("prior_run", f"a run for {variant_name} already exists "
                                  f"({record.get('run_id')}, {record.get('status')}); re-running "
                                  "spends again and is a recorded decision (allow_rerun)")
    return failures


# --- schedule runner ----------------------------------------------------------------

@dataclass(frozen=True)
class ScheduleVerification:
    ok: bool
    problems: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]


def verify_schedule(bundle_dir: str | Path, config: ExperimentConfig,
                    variant_name: str) -> ScheduleVerification:
    """Completeness against the configured schedule: every scheduled task/trial id is in the
    bundle with a graded record and its four check outcomes, nothing else is, and the bundle
    names this experiment, variant, and prompt. Record integrity is `verify_bundle`'s."""
    path = Path(bundle_dir)
    verification = verify_bundle(path)
    problems = [f"{p.kind}: {p.detail}" + (f" [{p.trial_id}]" if p.trial_id else "")
                for p in verification.problems]
    if verification.run_id is None:
        return ScheduleVerification(False, tuple(problems), (), ())
    manifest = load_manifest(path)
    scheduled = [item["trial_id"] for item in config.schedule]
    planned = [p["trial_id"] for p in manifest.get("planned", [])]
    missing = tuple(t for t in scheduled if t not in verification.recorded)
    unexpected = tuple(t for t in planned if t not in scheduled)
    if planned != scheduled:
        problems.append("the bundle's planned trials differ from the configured schedule")
    experiment = manifest.get("identity", {}).get("experiment", {})
    if (experiment.get("experiment_id"), experiment.get("variant")) != (config.experiment_id, variant_name):
        problems.append(f"the bundle is not a {config.experiment_id} {variant_name} run")
    elif experiment.get("schedule_sha256") != config.schedule_sha256:
        problems.append("the bundle ran a different schedule than the configuration")
    prompt = manifest.get("identity", {}).get("prompt", {})
    expected = config.variant(variant_name)
    if (prompt.get("version"), prompt.get("sha256")) != (expected["prompt_version"], expected["prompt_sha256"]):
        problems.append(f"the bundle's prompt is not the configured {variant_name} prompt")
    if manifest.get("status") != STATUS_COMPLETE:
        problems.append(f"manifest status is {manifest.get('status')!r}")
    for trial_id in verification.recorded:
        try:
            grades = load_trial(path, trial_id).get("grades", {})
        except BundleError:
            continue  # already reported by verify_bundle
        if grades.get("status") not in (GRADE_GRADED, GRADE_INCOMPLETE):
            problems.append(f"{trial_id}: not graded")
        elif len(grades.get("checks", [])) != CHECKS_PER_TRIAL:
            problems.append(f"{trial_id}: {len(grades.get('checks', []))} check outcomes, "
                            f"expected {CHECKS_PER_TRIAL}")
    for trial_id in missing:
        problems.append(f"scheduled trial {trial_id} has no record")
    return ScheduleVerification(not problems, tuple(dict.fromkeys(problems)), missing, unexpected)


@dataclass(frozen=True)
class VariantRun:
    variant: str
    run_id: str
    bundle: Path
    verification: Verification
    schedule: ScheduleVerification
    ledger_total_before_chf: str
    ledger_total_after_chf: str
    tracking: str
    checkpoint_reached: bool    # the ledger had logged its CHF 10 checkpoint when the run ended
    checkpoint_reached_before: bool

    @property
    def complete(self) -> bool:
        return self.verification.complete and self.schedule.ok


def run_variant(
    config: ExperimentConfig, variant_name: str, client_for: Callable[[Task, str], ModelClient], *,
    ledger: Ledger, prices: PriceInputs | None, accept_cost: bool, api_key: str | None,
    evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR,
    bundle_root: str | Path = DEFAULT_BUNDLE_ROOT,
    benchmark_path: str | Path = DEFAULT_BENCHMARK,
    smoke_bundle: str | Path | None = None,
    grader: Grader | None = None,
    runner: Callable[..., ExecutionResult] = execute_check,
    agent_limits: AgentLimits = DEFAULT_AGENT_LIMITS,
    execution_limits: ExecutionLimits = DEFAULT_LIMITS,
    allow_rerun: bool = False,
    record_run: Callable[[Path, str], str | None] | None = None,
    run_id: str | None = None,
) -> VariantRun:
    """Run one variant's whole schedule into one bundle, each trial a fresh conversation
    through `client_for` (which, for a paid run, reserves in the ledger before every send).

    Raises `PreconditionsFailed`, before any client is built or bundle written, unless every
    precondition holds. `record_run(bundle, variant)` is the experiment-tracking hook;
    its failure or absence never affects the bundle, which stays the durable evidence, and its
    outcome is stated in `VariantRun.tracking`."""
    failures = check_preconditions(
        config, variant_name, ledger=ledger, prices=prices, accept_cost=accept_cost,
        api_key=api_key, evidence_dir=evidence_dir, bundle_root=bundle_root,
        benchmark_path=benchmark_path, smoke_bundle=smoke_bundle, agent_limits=agent_limits,
        execution_limits=execution_limits, allow_rerun=allow_rerun)
    if failures:
        raise PreconditionsFailed(failures)
    variant = config.variant(variant_name)
    prompt: AgentPrompt = load_prompt(variant["prompt_version"])
    model = load_model_config(config.data["settings"]["model_config_version"])
    tasks = load_benchmark(benchmark_path)
    if grader is None:
        from codegen_eval.replay import make_grader
        grader = make_grader()
    run_id = run_id or new_run_id()
    root = Path(bundle_root)
    root.mkdir(parents=True, exist_ok=True)
    marker = _sidecar_path(root, run_id)
    state_before = ledger.state()
    before, checkpoint_before = state_before.total, state_before.checkpoint_logged
    record: dict[str, Any] = {"experiment_id": config.experiment_id, "variant": variant_name,
                              "run_id": run_id, "config_sha256": config.sha256,
                              "started_at": utc_now(), "status": "started",
                              "ledger_total_before_chf": str(before),
                              "checkpoint_reached_before": checkpoint_before,
                              "allow_rerun": allow_rerun}
    # Written first: a crash or interrupt leaves a marker, so a second start is a recorded decision.
    atomic_write(marker, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    identity_extra = {"experiment": {
        "experiment_id": config.experiment_id, "variant": variant_name,
        "config_sha256": config.sha256, "schedule_sha256": config.schedule_sha256,
        "trial_order": config.data["trial_order"],
        "settings_hash": config.data["settings"]["settings_hash"],
        "evaluator_code_sha256": evaluator_code_sha256(),
        "prompt_files": prompt_file_hashes()}}
    try:
        bundle, verification = run_recorded(
            tasks, client_for, benchmark_path, bundle_root=root, run_id=run_id,
            trials_per_task=config.data["trials_per_task"], grader=grader, prompt=prompt,
            limits=agent_limits, execution_limits=execution_limits, runner=runner,
            model_settings=model.identity(), extra_secrets=(api_key,) if api_key else (),
            identity_extra=identity_extra)
    except BaseException:
        state = ledger.state()
        record.update(status="interrupted", ledger_total_after_chf=str(state.total),
                      checkpoint_reached=state.checkpoint_logged)
        atomic_write(marker, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        raise
    schedule = verify_schedule(bundle, config, variant_name)
    tracking = "not recorded (no tracking hook; upload later from the retained bundle)"
    if record_run is not None:
        try:
            tracking = record_run(bundle, variant_name) or "recorded"
        except Exception as error:  # noqa: BLE001 - a tracking outage never blocks or alters a run
            tracking = f"tracking failed ({type(error).__name__}); upload later from the bundle"
    state = ledger.state()
    after = state.total
    record.update(status="complete" if verification.complete and schedule.ok else "incomplete",
                  checkpoint_reached=state.checkpoint_logged, finished_at=utc_now(), ledger_total_after_chf=str(after),
                  bundle=str(bundle), schedule_problems=list(schedule.problems), tracking=tracking)
    atomic_write(marker, json.dumps(record, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return VariantRun(variant_name, run_id, bundle, verification, schedule, str(before), str(after),
                      tracking, state.checkpoint_logged, checkpoint_before)
