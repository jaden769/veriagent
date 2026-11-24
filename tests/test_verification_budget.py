import pytest

from veriagent.verification_budget import (
    VerificationBudgetExceeded,
    VerificationBudgetLedger,
    VerificationLimits,
    VerificationReservation,
)


@pytest.mark.parametrize("value", [-1, True, False, 1.0, "1"])
@pytest.mark.parametrize("field", ["max_calls", "max_target_rows"])
def test_limits_reject_coerced_or_negative_values(field, value):
    with pytest.raises(ValueError):
        VerificationLimits(**{field: value})


@pytest.mark.parametrize(
    "limits",
    [
        VerificationLimits(max_calls=0),
        VerificationLimits(max_target_rows=0),
        VerificationLimits(max_target_rows=1),
    ],
)
def test_denied_reservation_does_not_consume_budget(limits):
    ledger = VerificationBudgetLedger(limits)
    before = ledger.state
    with pytest.raises(VerificationBudgetExceeded):
        ledger.reserve(2)
    assert ledger.state == before


def test_exact_boundary_and_no_partial_admission():
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=2, max_target_rows=3))
    first = ledger.reserve(2)
    assert ledger.state["pending"] and ledger.state["verified_target_rows"] is None
    ledger.complete(first, observed_target_rows=2)
    before = ledger.state
    with pytest.raises(VerificationBudgetExceeded, match="target_rows"):
        ledger.reserve(2)
    assert ledger.state == before
    second = ledger.reserve(1)
    ledger.complete(second, observed_target_rows=1)
    assert ledger.state["verified_target_rows"] == 3
    assert ledger.state["remaining_calls"] == ledger.state["remaining_target_rows"] == 0
    with pytest.raises(VerificationBudgetExceeded, match="calls"):
        ledger.reserve(1)


def test_error_retains_reservation_and_unknown_partial_work():
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=2, max_target_rows=4))
    first = ledger.reserve(2)
    ledger.fail(first)
    assert ledger.state["remaining_target_rows"] == 2
    assert ledger.state["known_verified_target_rows"] == 0
    assert ledger.state["verified_target_rows"] is None
    second = ledger.reserve(2)
    ledger.complete(second, observed_target_rows=2)
    assert ledger.state["known_verified_target_rows"] == 2
    assert ledger.state["verified_target_rows"] is None
    assert ledger.state["verification_errors"] == 1
    assert not ledger.state["verification_work_complete"]


def test_stale_foreign_and_double_completion_cannot_change_state():
    ledger = VerificationBudgetLedger(VerificationLimits())
    ticket = ledger.reserve(1)
    for forged in (VerificationReservation(1), None):
        before = ledger.state
        with pytest.raises(ValueError):
            ledger.fail(forged)
        assert ledger.state == before
    with pytest.raises(ValueError):
        ledger.reserve(1)
    ledger.complete(ticket, observed_target_rows=1)
    before = ledger.state
    with pytest.raises(ValueError):
        ledger.complete(ticket, observed_target_rows=1)
    assert ledger.state == before
    ticket = ledger.reserve(1)
    assert ticket is not None


@pytest.mark.parametrize("rows", [0, -1, True, 1.0, "1", None])
def test_requested_rows_are_strictly_positive_integers(rows):
    ledger = VerificationBudgetLedger(VerificationLimits())
    before = ledger.state
    with pytest.raises(ValueError):
        ledger.reserve(rows)
    assert ledger.state == before


@pytest.mark.parametrize("rows", [0, 1, 3, True, 2.0])
def test_completion_mismatch_keeps_pending_for_error_accounting(rows):
    ledger = VerificationBudgetLedger(VerificationLimits())
    ticket = ledger.reserve(2)
    before = ledger.state
    with pytest.raises(ValueError):
        ledger.complete(ticket, observed_target_rows=rows)
    assert ledger.state == before
    ledger.fail(ticket)
    assert ledger.state["verification_errors"] == 1


def test_unlimited_accounting_and_snapshot_isolation():
    ledger = VerificationBudgetLedger(VerificationLimits())
    for _ in range(3):
        ticket = ledger.reserve(2)
        ledger.complete(ticket, observed_target_rows=2)
    snapshot = ledger.state
    assert snapshot["remaining_calls"] is snapshot["remaining_target_rows"] is None
    snapshot["limits"]["max_calls"] = 0
    assert ledger.state["limits"]["max_calls"] is None
    assert ledger.state["reserved_target_rows"] == 6
