import sqlite3

import pytest

from veriagent.bounded_verification import BudgetedStateVerifier
from veriagent.models import Requirement, Task
from veriagent.sandbox import Sandbox
from veriagent.verification import StateVerifier
from veriagent.verification_budget import (
    VerificationBudgetExceeded,
    VerificationBudgetLedger,
    VerificationLimits,
)


@pytest.fixture
def fixture(tmp_path):
    path = tmp_path / "state.sqlite"
    sandbox = Sandbox(path)
    sandbox.seed()
    task = Task(
        objective="Set ISSUE-1 and ISSUE-2 to done",
        requirements=tuple(Requirement(issue_id=f"ISSUE-{i}", status="done") for i in (1, 2)),
    )
    return path, task


@pytest.mark.parametrize(
    "limits", [VerificationLimits(max_calls=0), VerificationLimits(max_target_rows=1)]
)
def test_denial_precedes_any_sqlite_connection(fixture, monkeypatch, limits):
    path, task = fixture
    ledger = VerificationBudgetLedger(limits)
    verifier = BudgetedStateVerifier(path, ledger)
    before = ledger.state

    def forbidden(*args, **kwargs):
        pytest.fail("Denied verification must not open SQLite")

    monkeypatch.setattr("veriagent.verification.sqlite3.connect", forbidden)
    with pytest.raises(VerificationBudgetExceeded):
        verifier.verify(task)
    assert ledger.state == before


def test_complete_mismatch_consumes_exact_allowance_and_stays_read_only(fixture, monkeypatch):
    path, task = fixture
    before = path.read_bytes()
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=2, max_target_rows=4))
    verifier = BudgetedStateVerifier(path, ledger)
    original = sqlite3.connect
    connections, statements = [], []

    def observe(*args, **kwargs):
        connections.append((args, kwargs))
        db = original(*args, **kwargs)
        db.set_trace_callback(statements.append)
        return db

    monkeypatch.setattr("veriagent.verification.sqlite3.connect", observe)
    for _ in range(2):
        result = verifier.verify(task)
        assert not result.passed and result.failure == "state_mismatch"
    assert len(connections) == 2
    assert all("?mode=ro" in args[0] and kwargs["uri"] for args, kwargs in connections)
    assert sum(statement.startswith("SELECT status") for statement in statements) == 4
    with pytest.raises(VerificationBudgetExceeded):
        verifier.verify(task)
    assert len(connections) == 2
    assert ledger.state["verified_target_rows"] == 4
    assert ledger.state["remaining_target_rows"] == 0
    assert path.read_bytes() == before


def test_partial_read_error_consumes_reservation_and_preserves_unknown(fixture, monkeypatch):
    path, task = fixture
    with sqlite3.connect(path) as db:
        db.execute("UPDATE issues SET status='invalid' WHERE id='ISSUE-2'")
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=1, max_target_rows=2))
    verifier = BudgetedStateVerifier(path, ledger)
    original = sqlite3.connect
    statements = []

    def observe(*args, **kwargs):
        db = original(*args, **kwargs)
        db.set_trace_callback(statements.append)
        return db

    monkeypatch.setattr("veriagent.verification.sqlite3.connect", observe)
    with pytest.raises(ValueError):
        verifier.verify(task)
    assert sum(statement.startswith("SELECT status") for statement in statements) == 2
    assert ledger.state["verification_errors"] == 1 and not ledger.state["pending"]
    assert ledger.state["verified_target_rows"] is None
    assert ledger.state["known_verified_target_rows"] == 0
    assert ledger.state["remaining_target_rows"] == 0


def test_connection_error_and_missing_file_do_not_create_database(tmp_path):
    path = tmp_path / "missing.sqlite"
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=1))
    verifier = BudgetedStateVerifier(path, ledger)
    task = Task(
        objective="Set ISSUE-1 to done",
        requirements=(Requirement(issue_id="ISSUE-1", status="done"),),
    )
    with pytest.raises(sqlite3.OperationalError):
        verifier.verify(task)
    assert not path.exists()
    assert ledger.state["verification_errors"] == 1
    assert ledger.state["verified_target_rows"] is None


def test_final_evaluator_is_independent_of_execution_allowance(fixture):
    path, task = fixture
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=0))
    with pytest.raises(VerificationBudgetExceeded):
        BudgetedStateVerifier(path, ledger).verify(task)
    before = ledger.state
    assert not StateVerifier(path).verify(task).passed
    assert ledger.state == before


def test_missing_target_is_completed_evidence_not_an_adapter_error(fixture):
    path, task = fixture
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM issues WHERE id='ISSUE-2'")
    ledger = VerificationBudgetLedger(VerificationLimits(max_target_rows=2))
    result = BudgetedStateVerifier(path, ledger).verify(task)
    assert not result.passed and result.failure == "not_found"
    assert ledger.state["verified_target_rows"] == 2
    assert ledger.state["verification_errors"] == 0


def test_incomplete_verifier_result_is_settled_as_unknown_error(fixture, monkeypatch):
    path, task = fixture
    ledger = VerificationBudgetLedger(VerificationLimits())
    verifier = BudgetedStateVerifier(path, ledger)
    full = StateVerifier(path).verify(task)
    monkeypatch.setattr(
        verifier._verifier,
        "verify",
        lambda task: full.model_copy(update={"evidence": full.evidence[:1]}),
    )
    with pytest.raises(ValueError, match="incomplete"):
        verifier.verify(task)
    assert ledger.state["verification_errors"] == 1
    assert ledger.state["verified_target_rows"] is None and not ledger.state["pending"]


def test_satisfied_targets_consume_verification_allowance(fixture):
    path, _ = fixture
    task = Task(
        objective="Set ISSUE-1 to open",
        requirements=(Requirement(issue_id="ISSUE-1", status="open"),),
    )
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=1, max_target_rows=1))
    assert BudgetedStateVerifier(path, ledger).verify(task).passed
    assert ledger.state["verified_target_rows"] == 1
    assert ledger.state["remaining_calls"] == 0


@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_verifier_exceptions_are_settled_then_propagated(fixture, monkeypatch, error):
    path, task = fixture
    ledger = VerificationBudgetLedger(VerificationLimits(max_calls=1))
    verifier = BudgetedStateVerifier(path, ledger)

    def fail(task):
        raise error("injected")

    monkeypatch.setattr(verifier._verifier, "verify", fail)
    with pytest.raises(error):
        verifier.verify(task)
    assert ledger.state["verification_errors"] == 1 and not ledger.state["pending"]
