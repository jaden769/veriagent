import sqlite3

import pytest

from veriagent.agent import Agent
from veriagent.bounded_verification import BudgetedStateVerifier
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget, Mode, Requirement, Task
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier
from veriagent.verification_budget import VerificationBudgetLedger, VerificationLimits


def setup_run(path, engine, *, limits=None, drops=0, goal="done"):
    sandbox = Sandbox(path / "state.sqlite", Faults(silent_drops=drops))
    sandbox.seed()
    traces = TraceStore(path / "traces.sqlite")
    task = Task(
        objective=f"Set ISSUE-1 to {goal}",
        requirements=(Requirement(issue_id="ISSUE-1", status=goal),),
    )
    verifier = StateVerifier(sandbox.path)
    if limits is not None:
        verifier = BudgetedStateVerifier(sandbox.path, VerificationBudgetLedger(limits))
    cls = Agent if engine == "static" else DynamicAgent
    agent = cls(
        MockProvider(), Executor(sandbox), verifier, traces, Budget(max_actions=8, max_decisions=8)
    )
    return agent, task, sandbox, traces


@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("mode", [Mode.VERIFY, Mode.RECOVER])
def test_zero_admission_is_budget_failure_with_no_oracle_connection(
    tmp_path, monkeypatch, engine, mode
):
    agent, task, sandbox, traces = setup_run(
        tmp_path, engine, limits=VerificationLimits(max_calls=0), drops=1
    )
    original = sqlite3.connect

    def guard(*args, **kwargs):
        if isinstance(args[0], str) and "?mode=ro" in args[0]:
            pytest.fail("Denied execution verification must not open the oracle")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", guard)
        report = agent.run(task, mode)
    assert report.failure == "budget" and not report.claimed_success
    assert report.verified_success is None and report.verification is None
    assert report.actions == (1 if engine == "static" else 0)
    events = traces.events(report.run_id)
    budgets = [e["payload"] for e in events if e["kind"] == "verification_budget"]
    assert [b["phase"] for b in budgets] == ["denied"]
    assert budgets[0]["state"]["reserved_calls"] == 0
    assert any(e["kind"] == "verification_denied" for e in events)
    assert not any(e["kind"] == "verification_error" for e in events)
    assert not StateVerifier(sandbox.path).verify(task).passed


@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_budget_denial_after_repair_does_not_reuse_stale_verification(tmp_path, engine):
    agent, task, sandbox, traces = setup_run(
        tmp_path,
        engine,
        limits=VerificationLimits(max_calls=1 if engine == "static" else 2),
        drops=1,
    )
    report = agent.run(task)
    assert report.failure == "budget" and not report.claimed_success
    assert report.verification is None and report.verified_success is None
    assert StateVerifier(sandbox.path).verify(task).passed
    events = traces.events(report.run_id)
    budgets = [e["payload"] for e in events if e["kind"] == "verification_budget"]
    assert budgets[-1]["phase"] == "denied"
    assert budgets[-1]["state"]["verification_errors"] == 0
    assert report.recovery_attempts == 1


@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("mode", list(Mode))
def test_unlimited_opt_in_preserves_existing_outcomes(tmp_path, engine, mode):
    ordinary = setup_run(tmp_path / "ordinary", engine, drops=1)
    bounded = setup_run(tmp_path / "bounded", engine, limits=VerificationLimits(), drops=1)
    reports = [run[0].run(run[1], mode) for run in (ordinary, bounded)]
    for key in (
        "claimed_success",
        "verified_success",
        "failure",
        "actions",
        "decisions",
        "recovery_attempts",
        "verification",
    ):
        assert getattr(reports[0], key) == getattr(reports[1], key)
    original_events = ordinary[3].events(reports[0].run_id)
    assert not any(e["kind"] == "verification_budget" for e in original_events)
    assert "verification_limits" not in next(
        e["payload"] for e in original_events if e["kind"] == "configuration"
    )
    events = bounded[3].events(reports[1].run_id)
    phases = [e["payload"]["phase"] for e in events if e["kind"] == "verification_budget"]
    assert phases.count("admitted") == phases.count("completed")
    if mode == Mode.BASELINE:
        assert not phases and bounded[0].verifier.ledger.state["reserved_calls"] == 0


@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_admitted_errors_have_internal_failure_and_unknown_work(tmp_path, monkeypatch, engine):
    agent, task, _, traces = setup_run(tmp_path, engine, limits=VerificationLimits(max_calls=1))

    def fail(task):
        raise RuntimeError("injected")

    monkeypatch.setattr(agent.verifier._verifier, "verify", fail)
    report = agent.run(task)
    assert report.failure == "internal" and not report.claimed_success
    budgets = [
        e["payload"] for e in traces.events(report.run_id) if e["kind"] == "verification_budget"
    ]
    assert [b["phase"] for b in budgets] == ["admitted", "error"]
    assert budgets[-1]["state"]["verified_target_rows"] is None
    assert not budgets[-1]["state"]["pending"]


@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_fresh_run_binding_and_initial_satisfaction(tmp_path, engine):
    agent, task, _, traces = setup_run(
        tmp_path, engine, limits=VerificationLimits(max_calls=1), goal="open"
    )
    report = agent.run(task)
    assert report.claimed_success and report.verified_success
    assert agent.verifier.ledger.state["reserved_calls"] == 1
    before = traces.events(report.run_id)
    with pytest.raises(ValueError, match="fresh"):
        agent.run(task)
    assert traces.events(report.run_id) == before
