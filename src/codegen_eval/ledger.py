"""Append-only project-wide spending ledger, kept outside Git.

One JSON-lines file shared by every command (development, smoke, main runs, retries).
Money is `Decimal` CHF, stored as strings. Events:

- `reservation`: written and fsynced *before* a paid attempt is sent, so a crash can never
  leave an unrecorded paid attempt.
- `settlement`: the charge is known (reported cost, or an estimate from reported usage);
  the reservation is released and the charge committed. Reported cost is stored apart from
  any estimate.
- `kept`: informational; the reservation stays counted (timeout, missing usage, error).
- `checkpoint`: logged once, the first time reserved + committed reaches the checkpoint.
- `refusal`: a reservation that would pass the ceiling was refused.
- `adjustment`: spending that happened outside the client (for example earlier manual calls).

Total spend is committed + outstanding reservations; the checkpoint and the ceiling use
that same basis (accepted 2026-10-30). Writers take an exclusive `flock`, so concurrent
processes cannot both pass the ceiling check. A torn final line (crash mid-write) never
authorised a send and is dropped on the next write; any other unreadable line stops all
use of the ledger rather than guessing."""

from __future__ import annotations

import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping

CHECKPOINT_CHF = Decimal("10")
CEILING_CHF = Decimal("15")
LEDGER_ENV = "CODEGEN_EVAL_LEDGER"
DEFAULT_LEDGER_PATH = Path.home() / ".codegen_eval" / "spend_ledger.jsonl"

BASIS_REPORTED = "reported_cost"
BASIS_ESTIMATED = "estimated_from_usage"


class LedgerError(Exception):
    """The ledger is unreadable or inconsistent; nothing may be sent until it is fixed."""


class BudgetCeiling(Exception):
    """A reservation would bring reserved plus committed spending above the ceiling."""


def default_ledger_path(env: Mapping[str, str] | None = None) -> Path:
    value = (os.environ if env is None else env).get(LEDGER_ENV)
    return Path(value) if value else DEFAULT_LEDGER_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class LedgerState:
    committed: Decimal
    outstanding: Mapping[str, Decimal]   # reservation id -> amount still counted
    checkpoint_logged: bool
    events: int

    @property
    def reserved(self) -> Decimal:
        return sum(self.outstanding.values(), Decimal(0))

    @property
    def total(self) -> Decimal:
        return self.committed + self.reserved


@dataclass(frozen=True)
class Reservation:
    id: str
    amount_chf: Decimal


class Ledger:
    def __init__(self, path: str | Path, *, checkpoint_chf: Decimal = CHECKPOINT_CHF,
                 ceiling_chf: Decimal = CEILING_CHF) -> None:
        if checkpoint_chf > ceiling_chf:
            raise ValueError("checkpoint must not exceed the ceiling")
        self.path = Path(path)
        self.checkpoint_chf = checkpoint_chf
        self.ceiling_chf = ceiling_chf

    # -- file access -------------------------------------------------------------------

    @contextmanager
    def _locked(self) -> Iterator[int]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield fd
        finally:
            os.close(fd)  # also releases the lock

    def _read(self, fd: int) -> tuple[list[dict[str, Any]], int]:
        """Parsed events and the byte length of the intact prefix."""
        os.lseek(fd, 0, os.SEEK_SET)
        chunks = []
        while chunk := os.read(fd, 1 << 20):
            chunks.append(chunk)
        data = b"".join(chunks)
        intact = data.rfind(b"\n") + 1
        events = []
        for number, line in enumerate(data[:intact].splitlines(), 1):
            try:
                event = json.loads(line)
            except ValueError:
                raise LedgerError(f"{self.path}: line {number} is not valid JSON") from None
            if not isinstance(event, dict) or "event" not in event:
                raise LedgerError(f"{self.path}: line {number} is not a ledger event")
            events.append(event)
        return events, intact

    def _append(self, fd: int, event: Mapping[str, Any]) -> None:
        line = json.dumps({"at": _now(), **event}, sort_keys=True, ensure_ascii=False) + "\n"
        data = memoryview(line.encode("utf-8"))
        while data:  # a short write must not leave a torn line behind an acknowledged event
            data = data[os.write(fd, data):]
        os.fsync(fd)

    def _state(self, events: list[dict[str, Any]]) -> LedgerState:
        committed = Decimal(0)
        outstanding: dict[str, Decimal] = {}
        checkpoint = False
        try:
            for event in events:
                kind = event["event"]
                if kind == "adjustment":
                    committed += Decimal(event["amount_chf"])
                elif kind == "reservation":
                    outstanding[event["id"]] = Decimal(event["amount_chf"])
                elif kind == "settlement":
                    if outstanding.pop(event["reservation_id"], None) is None:
                        raise LedgerError(f"settlement for unknown or settled reservation "
                                          f"{event['reservation_id']}")
                    committed += Decimal(event["amount_chf"])
                elif kind == "checkpoint":
                    checkpoint = True
        except (KeyError, ArithmeticError) as error:
            raise LedgerError(f"{self.path}: malformed event ({error!r})") from None
        return LedgerState(committed, outstanding, checkpoint, len(events))

    def _snapshot(self, fd: int) -> tuple[LedgerState, int]:
        events, intact = self._read(fd)
        return self._state(events), intact

    def _heal(self, fd: int, intact: int) -> None:
        if intact < os.fstat(fd).st_size:
            os.ftruncate(fd, intact)  # torn tail: its reservation was never acknowledged

    def _log_checkpoint(self, fd: int, state: LedgerState) -> None:
        if not state.checkpoint_logged and state.total >= self.checkpoint_chf:
            self._append(fd, {"event": "checkpoint", "threshold_chf": str(self.checkpoint_chf),
                              "basis": "committed_plus_reservations",
                              "committed_chf": str(state.committed),
                              "reserved_chf": str(state.reserved),
                              "total_chf": str(state.total)})

    # -- operations --------------------------------------------------------------------

    def state(self) -> LedgerState:
        with self._locked() as fd:
            return self._snapshot(fd)[0]

    def reserve(self, amount_chf: Decimal, inputs: Mapping[str, Any],
                context: Mapping[str, Any] | None = None) -> Reservation:
        """Record a reservation durably, or raise `BudgetCeiling` (also recorded)."""
        if amount_chf <= 0:
            raise ValueError("a reservation must be positive")
        with self._locked() as fd:
            state, intact = self._snapshot(fd)
            self._heal(fd, intact)
            self._log_checkpoint(fd, state)  # heals a crash between reservation and checkpoint
            if state.total + amount_chf > self.ceiling_chf:
                self._append(fd, {"event": "refusal", "requested_chf": str(amount_chf),
                                  "committed_chf": str(state.committed),
                                  "reserved_chf": str(state.reserved),
                                  "ceiling_chf": str(self.ceiling_chf),
                                  "context": dict(context or {})})
                raise BudgetCeiling(f"reservation of CHF {amount_chf} would bring spending to "
                                    f"CHF {state.total + amount_chf}, above the CHF "
                                    f"{self.ceiling_chf} ceiling")
            reservation = Reservation(uuid.uuid4().hex[:16], amount_chf)
            self._append(fd, {"event": "reservation", "id": reservation.id,
                              "amount_chf": str(amount_chf), "inputs": dict(inputs),
                              "context": dict(context or {}),
                              "committed_before_chf": str(state.committed),
                              "reserved_before_chf": str(state.reserved)})
            after = LedgerState(state.committed, {**state.outstanding, reservation.id: amount_chf},
                                state.checkpoint_logged, state.events + 1)
            self._log_checkpoint(fd, after)
            return reservation

    def settle(self, reservation_id: str, amount_chf: Decimal, basis: str, *,
               reported_cost_usd: str | None = None, usage: Mapping[str, Any] | None = None) -> None:
        """Release a reservation and commit the now-known charge."""
        if basis not in (BASIS_REPORTED, BASIS_ESTIMATED):
            raise ValueError(f"unknown settlement basis {basis!r}")
        if amount_chf < 0:
            raise ValueError("a charge cannot be negative")
        with self._locked() as fd:
            state, intact = self._snapshot(fd)
            self._heal(fd, intact)
            reserved = state.outstanding.get(reservation_id)
            if reserved is None:
                raise LedgerError(f"no outstanding reservation {reservation_id}")
            self._append(fd, {"event": "settlement", "reservation_id": reservation_id,
                              "amount_chf": str(amount_chf), "basis": basis,
                              "reported_cost_usd": reported_cost_usd,
                              "reservation_chf": str(reserved),
                              "released_chf": str(reserved - amount_chf),
                              "usage": dict(usage) if usage else None})
            outstanding = {k: v for k, v in state.outstanding.items() if k != reservation_id}
            self._log_checkpoint(fd, LedgerState(state.committed + amount_chf, outstanding,
                                                 state.checkpoint_logged, state.events + 1))

    def keep(self, reservation_id: str, reason: str) -> None:
        """Note that a reservation stays counted because the charge is uncertain."""
        with self._locked() as fd:
            state, intact = self._snapshot(fd)
            self._heal(fd, intact)
            if reservation_id not in state.outstanding:
                raise LedgerError(f"no outstanding reservation {reservation_id}")
            self._append(fd, {"event": "kept", "reservation_id": reservation_id,
                              "reason": reason})

    def adjust(self, amount_chf: Decimal, note: str) -> None:
        """Record committed spending made outside the client."""
        if amount_chf <= 0 or not note.strip():
            raise ValueError("an adjustment needs a positive amount and a note")
        with self._locked() as fd:
            state, intact = self._snapshot(fd)
            self._heal(fd, intact)
            self._append(fd, {"event": "adjustment", "amount_chf": str(amount_chf),
                              "note": note})
            self._log_checkpoint(fd, LedgerState(state.committed + amount_chf, state.outstanding,
                                                 state.checkpoint_logged, state.events + 1))
