import json
import threading
from decimal import Decimal

import pytest

from codegen_eval.ledger import (
    BASIS_ESTIMATED, BASIS_REPORTED, BudgetCeiling, Ledger, LedgerError, default_ledger_path,
)

D = Decimal


def small(tmp_path, checkpoint="1", ceiling="1.5"):
    return Ledger(tmp_path / "sub" / "ledger.jsonl", checkpoint_chf=D(checkpoint),
                  ceiling_chf=D(ceiling))


def events(ledger):
    return [json.loads(line) for line in ledger.path.read_text().splitlines()]


def test_default_budget_is_chf_10_checkpoint_and_chf_15_ceiling(tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")

    assert (ledger.checkpoint_chf, ledger.ceiling_chf) == (D(10), D(15))
    assert default_ledger_path({"CODEGEN_EVAL_LEDGER": "/x/y.jsonl"}).as_posix() == "/x/y.jsonl"
    assert default_ledger_path({}).as_posix().endswith(".codegen_eval/spend_ledger.jsonl")


def test_reserve_then_settle_moves_amount_from_reserved_to_committed(tmp_path):
    ledger = small(tmp_path)
    res = ledger.reserve(D("0.30"), {"prices": "p"}, {"trial_id": "t1"})
    assert (ledger.state().reserved, ledger.state().committed) == (D("0.30"), 0)

    ledger.settle(res.id, D("0.05"), BASIS_REPORTED, reported_cost_usd="0.0625",
                  usage={"prompt_tokens": 1})

    state = ledger.state()
    assert (state.reserved, state.committed, state.total) == (0, D("0.05"), D("0.05"))
    settlement = events(ledger)[-1]
    assert settlement["basis"] == BASIS_REPORTED and settlement["reported_cost_usd"] == "0.0625"
    assert settlement["released_chf"] == "0.25"
    with pytest.raises(LedgerError):
        ledger.settle(res.id, D("0.05"), BASIS_REPORTED)  # already settled


def test_estimates_are_recorded_apart_from_reported_costs(tmp_path):
    ledger = small(tmp_path)
    res = ledger.reserve(D("0.2"), {})
    ledger.settle(res.id, D("0.1"), BASIS_ESTIMATED)

    last = events(ledger)[-1]
    assert last["basis"] == BASIS_ESTIMATED and last["reported_cost_usd"] is None
    with pytest.raises(ValueError):
        ledger.settle(res.id, D("0.1"), "guess")


def test_kept_reservation_stays_counted(tmp_path):
    ledger = small(tmp_path)
    res = ledger.reserve(D("0.4"), {})
    ledger.keep(res.id, "timeout")

    assert ledger.state().total == D("0.4") and events(ledger)[-1]["event"] == "kept"


def test_checkpoint_is_logged_once_on_committed_plus_reservations_and_work_continues(tmp_path):
    ledger = small(tmp_path)  # checkpoint 1, ceiling 1.5
    ledger.reserve(D("0.6"), {})
    assert not [e for e in events(ledger) if e["event"] == "checkpoint"]

    ledger.reserve(D("0.5"), {})  # total 1.1 reaches the checkpoint; continues
    ledger.reserve(D("0.2"), {})  # later attempts log nothing more

    checkpoints = [e for e in events(ledger) if e["event"] == "checkpoint"]
    assert len(checkpoints) == 1 and checkpoints[0]["total_chf"] == "1.1"
    assert checkpoints[0]["basis"] == "committed_plus_reservations"
    kinds = [e["event"] for e in events(ledger)]
    assert kinds.index("checkpoint") == kinds.index("reservation", 1) + 1


def test_ceiling_refuses_over_budget_reservations_without_reserving(tmp_path):
    ledger = small(tmp_path)
    ledger.reserve(D("1.4"), {})

    with pytest.raises(BudgetCeiling):
        ledger.reserve(D("0.2"), {}, {"trial_id": "t9"})

    assert ledger.state().total == D("1.4")
    refusal = events(ledger)[-1]
    assert refusal["event"] == "refusal" and refusal["context"] == {"trial_id": "t9"}
    ledger.reserve(D("0.1"), {})  # exactly at the ceiling is allowed
    with pytest.raises(BudgetCeiling):
        ledger.reserve(D("0.0001"), {})


def test_settled_release_makes_room_but_kept_reservations_do_not(tmp_path):
    ledger = small(tmp_path)
    kept = ledger.reserve(D("0.7"), {})
    ledger.keep(kept.id, "timeout")
    paid = ledger.reserve(D("0.7"), {})
    with pytest.raises(BudgetCeiling):
        ledger.reserve(D("0.2"), {})

    ledger.settle(paid.id, D("0.01"), BASIS_REPORTED)

    ledger.reserve(D("0.2"), {})  # released room is reusable; the kept 0.7 still counts
    assert ledger.state().total == D("0.7") + D("0.01") + D("0.2")


def test_adjustment_counts_and_can_cross_the_checkpoint(tmp_path):
    ledger = small(tmp_path)
    ledger.adjust(D("1.2"), "earlier manual calls")

    assert ledger.state().committed == D("1.2") and ledger.state().checkpoint_logged
    with pytest.raises(ValueError):
        ledger.adjust(D("0"), "x")
    with pytest.raises(ValueError):
        ledger.adjust(D("1"), " ")


def test_torn_final_line_is_dropped_but_a_corrupt_middle_line_blocks_use(tmp_path):
    ledger = small(tmp_path)
    ledger.reserve(D("0.1"), {})
    with open(ledger.path, "ab") as handle:
        handle.write(b'{"event": "reservation", "id": "torn", "amo')  # crash mid-write

    assert ledger.state().total == D("0.1")
    ledger.reserve(D("0.1"), {})  # the next write removes the fragment first
    assert [json.loads(l)["event"] for l in ledger.path.read_text().splitlines()] == \
        ["reservation", "reservation"]

    with open(ledger.path, "ab") as handle:
        handle.write(b"not json\n")
    with pytest.raises(LedgerError):
        ledger.state()
    with pytest.raises(LedgerError):
        ledger.reserve(D("0.1"), {})


def test_concurrent_reservations_cannot_jointly_pass_the_ceiling(tmp_path):
    ledger = small(tmp_path, checkpoint="1", ceiling="2")
    results = []

    def worker():
        try:
            ledger.reserve(D("0.4"), {})
            results.append(True)
        except BudgetCeiling:
            results.append(False)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 5 and ledger.state().total == D("2.0")
    assert len([e for e in events(ledger) if e["event"] == "checkpoint"]) == 1


def test_ledger_file_is_created_private(tmp_path):
    ledger = small(tmp_path)
    ledger.reserve(D("0.1"), {})

    assert oct(ledger.path.stat().st_mode & 0o777) == "0o600"
