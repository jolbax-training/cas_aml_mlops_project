"""Durable local run bundles: write evidence incrementally, read it back, verify it.

A bundle is a directory of plain JSON files (`manifest.json`, `trials/<trial_id>.json`,
`replays/<replay_id>.json`). Nothing here imports a model client, the sandbox, or the
evaluator, so reading and verifying a bundle needs no Podman, network, or credentials.

The manifest records the SHA-256 of every trial record it has accepted. That detects
edited, truncated, or swapped records. It is a checksum, not a signature: someone who
rewrites a record and the manifest together is not detected unless the printed bundle
digest (the hash of manifest.json) was recorded elsewhere."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

BUNDLE_SCHEMA_VERSION = 1
DEFAULT_BUNDLE_ROOT = "run_bundles"  # ignored by Git (see .gitignore)

STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETE = "complete"
STATUS_INCOMPLETE = "incomplete"

# Fields that may be written. Anything else (headers, keys, client objects) is dropped.
REQUEST_FIELDS = ("messages", "tools", "tool_choice")
RESPONSE_FIELDS = ("content", "tool_calls", "truncated", "usage", "failure", "detail")
MESSAGE_FIELDS = ("role", "content", "tool_calls", "tool_call_id")

# Environment variables whose values must never appear in a bundle: names that end in a
# credential word, or contain SECRET/PASSWORD/CREDENTIAL. This is a heuristic, so the
# number of replacements is recorded in the manifest; extra values can be passed explicitly.
_SECRET_NAME = re.compile(r"(^|_)(API_?KEY|KEY|TOKEN|PASSWD)$|SECRET|PASSWORD|CREDENTIAL",
                          re.IGNORECASE)
_MIN_SECRET_LENGTH = 8
REDACTED = "[REDACTED]"

# Labels naming the container or worker rather than candidate code; they make a trial
# incomplete instead of failed. Kept equal to `sandbox.INFRASTRUCTURE_STATUSES` by a test
# (this module must not import the sandbox). Candidate labels are not enumerated here:
# the grading side owns them, and the bundle only requires each to be a nonempty string.
INFRASTRUCTURE_FAILURES = frozenset({"infrastructure_error", "protocol_error"})

# Problem kinds reported by verify_bundle.
UNREADABLE_MANIFEST = "unreadable_manifest"
UNSUPPORTED_SCHEMA = "unsupported_schema"
NOT_FINALIZED = "run_not_finalized"
MISSING_RECORD = "missing_record"
UNEXPECTED_RECORD = "unexpected_record"
UNREADABLE_RECORD = "unreadable_record"
TAMPERED_RECORD = "tampered_record"
IDENTITY_MISMATCH = "identity_mismatch"
INFRASTRUCTURE_STOP = "infrastructure_stop"
INVALID_GRADE = "invalid_grade"
UNRECORDED_RECORD = "unrecorded_record"
RUN_STOPPED = "run_stopped"


class BundleError(Exception):
    """A bundle cannot be read or written as requested."""


# The interface the grading side implements: `(Task, TrialResult) -> TrialGrade`, exactly
# `evaluate.grade_trial` (bind its runner with `functools.partial`). The bundle stores the
# grade through `grades_record` and validates stored grades with `check_grades`.
Grader = Callable[[Any, Any], Any]

GRADE_PENDING = "pending"
GRADE_GRADED = "graded"
GRADE_INCOMPLETE = "incomplete"  # an infrastructure outcome made grading unreliable
PENDING_GRADES: dict[str, Any] = {"status": GRADE_PENDING, "checks": []}


def grades_record(grade: Any) -> dict[str, Any]:
    """Stored form of a `TrialGrade`: trial-level fields plus one entry per planned check.
    Check entries keep `evaluate.CaseResult` names (`id`, `kind`, `executed`, `passed`,
    `failures`, `actual`)."""
    return {
        "status": GRADE_INCOMPLETE if grade.incomplete else GRADE_GRADED,
        "trial_status": grade.status,
        "labels": list(grade.labels),
        "success": grade.success,
        "incomplete": grade.incomplete,
        "infrastructure_status": grade.infrastructure_status,
        "checks": [{"id": c.id, "kind": c.kind, "executed": c.executed, "passed": c.passed,
                    "failures": list(c.failures), "actual": c.actual} for c in grade.cases],
    }


@dataclass(frozen=True)
class Problem:
    kind: str
    detail: str
    trial_id: str | None = None


@dataclass(frozen=True)
class Verification:
    run_id: str | None
    problems: tuple[Problem, ...]
    planned: tuple[str, ...] = ()
    recorded: tuple[str, ...] = ()
    grades_pending: tuple[str, ...] = ()
    bundle_digest: str | None = None

    @property
    def complete(self) -> bool:
        return not self.problems

    def missing(self) -> tuple[str, ...]:
        return tuple(p.trial_id for p in self.problems
                     if p.kind == MISSING_RECORD and p.trial_id)


# --- hashing, time, identity -------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def evaluator_revision(repo: str | Path | None = None) -> str:
    """Git revision of the evaluator code, with `+dirty` if `src/` or `data/` has any
    uncommitted change, untracked files included (a new module is code that ran)."""
    cwd = Path(repo) if repo else Path(__file__).resolve().parent
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True,
                             text=True, timeout=10, check=True).stdout.strip()
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=top, capture_output=True,
                              text=True, timeout=10, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "data"],
                               cwd=top, capture_output=True, text=True, timeout=10,
                               check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return head + ("+dirty" if dirty else "")


def source_tree_sha256() -> str:
    """Hash of the evaluator's own files (Python modules and prompts), so a bundle names
    the exact code that produced it even when the Git revision cannot."""
    package = Path(__file__).resolve().parent
    lines = "".join(f"{path.relative_to(package).as_posix()}\t{sha256_file(path)}\n"
                    for path in sorted(package.rglob("*"))
                    if path.suffix in {".py", ".md"} and "__pycache__" not in path.parts)
    return sha256_bytes(lines.encode("utf-8"))


def runtime_identity() -> dict[str, str]:
    return {"python": sys.version.split()[0], "platform": platform.platform()}


# --- sanitising --------------------------------------------------------------------

def _pick(data: Mapping[str, Any], allowed: Iterable[str]) -> dict[str, Any]:
    return {key: data[key] for key in allowed if key in data}


def _numeric_only(value: Any) -> Any:
    """Usage records keep numbers (and nested groups of them); free text is dropped."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        kept = {str(k): _numeric_only(v) for k, v in value.items()}
        return {k: v for k, v in kept.items() if v is not None}
    return None


def sanitize_request(request: Mapping[str, Any]) -> dict[str, Any]:
    record = _pick(request, REQUEST_FIELDS)
    if "messages" in record:
        record["messages"] = [_pick(m, MESSAGE_FIELDS) for m in record["messages"]]
    return record


def sanitize_response(response: Mapping[str, Any]) -> dict[str, Any]:
    record = _pick(response, RESPONSE_FIELDS)
    if "usage" in record:
        record["usage"] = _numeric_only(record["usage"])
    return record


def secret_values(extra: Iterable[str] = ()) -> list[str]:
    values = [v for name, v in os.environ.items()
              if _SECRET_NAME.search(name) and len(v) >= _MIN_SECRET_LENGTH and not v.isdigit()]
    values += [v for v in extra if len(v) >= _MIN_SECRET_LENGTH]
    return sorted(set(values), key=len, reverse=True)


def redact_value(value: Any, secrets: Sequence[str]) -> tuple[Any, int]:
    """Replace secret values inside string values (and keys) of a JSON-like structure.

    Working on the structure, not on serialised text, keeps numbers, escapes, and the
    record's validity intact. Returns the redacted copy and the number of replacements."""
    if isinstance(value, str):
        count = 0
        for secret in secrets:
            count += value.count(secret)
            value = value.replace(secret, REDACTED)
        return value, count
    if isinstance(value, Mapping):
        total, out = 0, {}
        for key, item in value.items():
            new_key, k = redact_value(key, secrets)
            new_item, n = redact_value(item, secrets)
            out[new_key] = new_item
            total += k + n
        return out, total
    if isinstance(value, (list, tuple)):
        items = [redact_value(item, secrets) for item in value]
        return [i for i, _ in items], sum(n for _, n in items)
    return value, 0


# --- files -------------------------------------------------------------------------

def _canonical(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _fsync_directory(directory: Path) -> None:
    """Make a rename durable; not available on every platform, so best effort."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes) -> None:
    """Write beside the target, then rename, so readers never see a torn file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _fsync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")


def _check_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.match(value) or ".." in value:
        raise BundleError(f"invalid {label}: {value!r}")
    return value


# --- writer ------------------------------------------------------------------------

class BundleWriter:
    """Create a bundle, add trial records as they finish, then finalise it.

    The manifest is written first with status `in_progress`; a run that stops before
    `finish` therefore stays visibly unfinished with every completed record on disk."""

    def __init__(self, root: str | Path, run_id: str, planned: Sequence[Mapping[str, str]],
                 identity: Mapping[str, Any], *, extra_secrets: Iterable[str] = ()) -> None:
        self.run_id = _check_id(run_id, "run id")
        self.path = Path(root) / self.run_id
        if self.path.exists():
            raise BundleError(f"bundle already exists: {self.path}")
        ids = [_check_id(p["trial_id"], "trial id") for p in planned]
        if not ids or len(set(ids)) != len(ids):
            raise BundleError("planned trials must be a non-empty list of unique trial ids")
        self._secrets = secret_values(extra_secrets)
        self._redactions = 0
        self._manifest: dict[str, Any] = {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "status": STATUS_IN_PROGRESS,
            "reasons": [],
            "redactions": 0,  # secret values replaced anywhere in this bundle's records
            "planned": [{"task_id": p["task_id"], "trial_id": p["trial_id"]} for p in planned],
            "identity": dict(identity),
            "records": {},
        }
        self._save_manifest()

    def _dump(self, data: Any) -> bytes:
        clean, count = redact_value(data, self._secrets)
        self._redactions += count
        return _canonical(clean)

    def _save_manifest(self) -> None:
        self._manifest["updated_at"] = utc_now()
        self._manifest["redactions"] = self._redactions
        atomic_write(self.path / "manifest.json", self._dump(self._manifest))

    def _calls_path(self, trial_id: str) -> Path:
        return self.path / "trials" / f"{_check_id(trial_id, 'trial id')}.calls.jsonl"

    def append_call(self, trial_id: str, entry: Mapping[str, Any]) -> None:
        """Append one request or response of a running trial, durably, as it happens, so a
        crash mid-trial keeps every paid response received so far. The trial's record
        replaces this log once the trial finishes."""
        if trial_id not in {p["trial_id"] for p in self._manifest["planned"]}:
            raise BundleError(f"trial {trial_id} was not planned")
        line = self._dump(entry).decode("utf-8")
        line = json.dumps(json.loads(line), sort_keys=True, ensure_ascii=False) + "\n"
        path = self._calls_path(trial_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as handle:
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())

    def write_trial(self, record: Mapping[str, Any]) -> None:
        trial_id = _check_id(record["trial_id"], "trial id")
        if trial_id not in {p["trial_id"] for p in self._manifest["planned"]}:
            raise BundleError(f"trial {trial_id} was not planned")
        body = {**record, "schema_version": BUNDLE_SCHEMA_VERSION, "run_id": self.run_id}
        data = self._dump(body)
        atomic_write(self.path / "trials" / f"{trial_id}.json", data)
        self._manifest["records"][trial_id] = sha256_bytes(data)
        self._save_manifest()
        self._calls_path(trial_id).unlink(missing_ok=True)  # superseded by the record

    def finish(self, reasons: Sequence[str] = ()) -> Verification:
        """Verify the bundle record by record and store the resulting status."""
        result = verify_bundle(self.path, finalizing=True)
        self._manifest["status"] = STATUS_COMPLETE if result.complete and not reasons \
            else STATUS_INCOMPLETE
        self._manifest["reasons"] = list(reasons) + [f"{p.kind}: {p.detail}"
                                                      for p in result.problems]
        self._save_manifest()
        if reasons:  # e.g. an interrupt: record-level checks alone could look clean
            result = replace(result, problems=result.problems + tuple(
                Problem(RUN_STOPPED, reason) for reason in reasons))
        return result


def write_replay(bundle_dir: str | Path, evidence: Mapping[str, Any]) -> Path:
    """Store replay evidence beside, never over, the original records."""
    replay_id = _check_id(evidence["replay_id"], "replay id")
    path = Path(bundle_dir) / "replays" / f"{replay_id}.json"
    if path.exists():
        raise BundleError(f"replay already exists: {path}")
    clean, _ = redact_value(evidence, secret_values())
    atomic_write(path, _canonical(clean))
    return path


# --- reading and listing -----------------------------------------------------------

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BundleError(f"cannot read {path.name}: {error}") from error


def load_manifest(bundle_dir: str | Path) -> dict[str, Any]:
    manifest = read_json(Path(bundle_dir) / "manifest.json")
    if not isinstance(manifest, dict):
        raise BundleError("manifest is not an object")
    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise BundleError(f"unsupported bundle schema version: {manifest.get('schema_version')!r}"
                          f" (this code reads version {BUNDLE_SCHEMA_VERSION})")
    planned = manifest.get("planned")
    if not (isinstance(planned, list) and planned and all(
            isinstance(p, dict) and isinstance(p.get("task_id"), str)
            and isinstance(p.get("trial_id"), str) for p in planned)):
        raise BundleError("manifest 'planned' must list task_id/trial_id pairs")
    if not isinstance(manifest.get("records"), dict) or not isinstance(manifest.get("identity"), dict) \
            or not isinstance(manifest.get("run_id"), str):
        raise BundleError("manifest must have run_id, identity, and records")
    return manifest


def load_partial_calls(bundle_dir: str | Path, trial_id: str) -> list[dict[str, Any]]:
    """Requests/responses retained for a trial that never produced a record."""
    path = Path(bundle_dir) / "trials" / f"{_check_id(trial_id, 'trial id')}.calls.jsonl"
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except ValueError:  # a torn final line from a crash keeps the lines before it
            break
    return entries


def load_trial(bundle_dir: str | Path, trial_id: str) -> dict[str, Any]:
    record = read_json(Path(bundle_dir) / "trials" / f"{_check_id(trial_id, 'trial id')}.json")
    if not isinstance(record, dict):
        raise BundleError(f"trial {trial_id} is not an object")
    return record


def resolve_bundle(root: str | Path, run: str) -> Path:
    """Accept a run id under `root` or a path to a bundle directory."""
    candidate = Path(run)
    if (candidate / "manifest.json").is_file():
        return candidate
    candidate = Path(root) / _check_id(run, "run id")
    if not (candidate / "manifest.json").is_file():
        raise BundleError(f"no bundle {run!r} under {root}")
    return candidate


def list_runs(root: str | Path) -> list[Path]:
    base = Path(root)
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if (p / "manifest.json").is_file())


# --- completeness ------------------------------------------------------------------

def check_grades(grades: Any) -> str | None:
    """Return why a stored grade record is not a valid outcome, or None if it is valid.

    Structural only: candidate labels are owned by the grading side, so any nonempty
    string is accepted; the infrastructure labels are the exception because they decide
    whether a trial is incomplete rather than failed."""
    if not isinstance(grades, dict) or grades.get("status") not in {
            GRADE_PENDING, GRADE_GRADED, GRADE_INCOMPLETE}:
        return "grades must be pending, graded, or incomplete"
    if grades["status"] == GRADE_PENDING:
        return None
    labels = grades.get("labels")
    if not (isinstance(labels, list) and all(isinstance(x, str) and x for x in labels)):
        return "trial labels must be a list of nonempty strings"
    if not isinstance(grades.get("trial_status"), str) or not isinstance(grades.get("success"), bool) \
            or not isinstance(grades.get("incomplete"), bool):
        return "trial-level fields are missing or malformed"
    infrastructure = grades.get("infrastructure_status")
    if grades["incomplete"] != (grades["status"] == GRADE_INCOMPLETE):
        return "status and incomplete flag disagree"
    if grades["incomplete"] and not (isinstance(infrastructure, str) and infrastructure):
        return "incomplete grade has no infrastructure status"
    if grades["incomplete"] and grades["success"]:
        return "an incomplete trial cannot be a success"
    checks = grades.get("checks")
    if not isinstance(checks, list) or not checks:
        return "graded record has no checks"
    seen: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or not {"id", "executed", "passed", "failures"} <= set(check):
            return "check is missing required fields"
        name = check["id"]
        if not isinstance(name, str) or name in seen:
            return f"duplicate or malformed check id {name!r}"
        seen.add(name)
        failures = check["failures"]
        if not isinstance(check["passed"], bool) or not isinstance(check["executed"], bool) \
                or not isinstance(failures, list) \
                or not all(isinstance(f, str) and f for f in failures):
            return f"check {name} has malformed outcome fields"
        if check["passed"] and (failures or not check["executed"]):
            return f"check {name} is marked passed but has failures or did not run"
        if not check["passed"] and not failures:
            return f"check {name} failed without a label"
        if any(f in INFRASTRUCTURE_FAILURES for f in failures):
            if check["executed"]:
                return f"check {name} reports an infrastructure failure as executed"
            if not grades["incomplete"]:
                return f"check {name} hit an infrastructure failure but the trial is not incomplete"
    if grades["success"] and not all(c["passed"] for c in checks):
        return "trial marked success with a failing check"
    return None


def verify_bundle(bundle_dir: str | Path, *, finalizing: bool = False) -> Verification:
    """Record-level completeness: every planned trial has an intact, valid record.

    Compares trial ids against the manifest's planned ids (never aggregate counts), checks
    each record against the hash the manifest stored for it, and validates executed-check
    outcomes. Infrastructure stops make a run incomplete, with denominators left at the
    planned values; classification and headline exclusion belong to the grading side.
    The status field the manifest claims is not trusted."""
    path = Path(bundle_dir)
    try:
        manifest = load_manifest(path)
    except BundleError as error:
        kind = UNSUPPORTED_SCHEMA if "schema version" in str(error) else UNREADABLE_MANIFEST
        return Verification(None, (Problem(kind, str(error)),))

    problems: list[Problem] = []
    planned = tuple(p["trial_id"] for p in manifest.get("planned", []))
    task_of = {p["trial_id"]: p["task_id"] for p in manifest.get("planned", [])}
    hashes = manifest.get("records", {})
    if not finalizing and manifest.get("status") != STATUS_COMPLETE:
        problems.append(Problem(NOT_FINALIZED, f"manifest status is {manifest.get('status')!r}"))

    recorded: list[str] = []
    pending: list[str] = []
    trial_dir = path / "trials"
    for trial_id in planned:
        file = trial_dir / f"{trial_id}.json"
        if not file.is_file():
            partial = len(load_partial_calls(path, trial_id))
            extra = f"; {partial} request/response entries retained in {trial_id}.calls.jsonl" \
                if partial else ""
            problems.append(Problem(MISSING_RECORD,
                                    "no record for this planned trial" + extra, trial_id))
            continue
        data = file.read_bytes()
        if trial_id not in hashes:
            problems.append(Problem(UNRECORDED_RECORD,
                                    "record exists but the manifest never accepted it "
                                    "(crash between the two writes, or an added file)", trial_id))
            continue
        if hashes[trial_id] != sha256_bytes(data):
            problems.append(Problem(TAMPERED_RECORD,
                                    "record does not match the hash stored in the manifest",
                                    trial_id))
            continue
        try:
            record = json.loads(data)
        except ValueError:
            problems.append(Problem(UNREADABLE_RECORD, "record is not valid JSON", trial_id))
            continue
        if not isinstance(record, dict):
            problems.append(Problem(UNREADABLE_RECORD, "record is not an object", trial_id))
            continue
        if record.get("schema_version") != BUNDLE_SCHEMA_VERSION:
            problems.append(Problem(UNSUPPORTED_SCHEMA, f"record schema version "
                                    f"{record.get('schema_version')!r}", trial_id))
            continue
        if (record.get("trial_id"), record.get("run_id"), record.get("task_id")) != \
                (trial_id, manifest.get("run_id"), task_of[trial_id]):
            problems.append(Problem(IDENTITY_MISMATCH,
                                    "record identity differs from the manifest plan", trial_id))
            continue
        recorded.append(trial_id)
        stopped = record.get("status") == "infrastructure_incomplete"
        if stopped:
            problems.append(Problem(INFRASTRUCTURE_STOP, f"trial stopped: "
                                    f"{record.get('infrastructure_status')}", trial_id))
        grades = record.get("grades", PENDING_GRADES)
        reason = check_grades(grades)
        if reason:
            problems.append(Problem(INVALID_GRADE, reason, trial_id))
        elif grades["status"] == GRADE_PENDING:
            pending.append(trial_id)
        elif grades["status"] == GRADE_INCOMPLETE and not stopped:
            problems.append(Problem(INFRASTRUCTURE_STOP, "a check hit an infrastructure failure "
                                    f"({grades['infrastructure_status']})", trial_id))

    if trial_dir.is_dir():
        for file in sorted(trial_dir.glob("*.json")):
            if file.stem not in task_of:
                problems.append(Problem(UNEXPECTED_RECORD, "record is not in the plan", file.stem))
    return Verification(manifest.get("run_id"), tuple(problems), planned, tuple(recorded),
                        tuple(pending), sha256_file(path / "manifest.json"))
