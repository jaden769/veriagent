import copy
import socket

import pytest
from pydantic import ValidationError

from analysis.metered_reflection import (
    DispatchTicket,
    MeteredRequestLedger,
    MeteredRequestLimits,
    ReflectionInput,
    reflection_payload,
)
from veriagent.budgeting import ModelBudgetExceeded
from veriagent.models import Budget, Requirement, Status, Task
from veriagent.reflection import ReflectionReport, ReflectionState


def limits(**changes):
    data = dict(
        max_requests=4,
        per_request_max_output_tokens=256,
        request_timeout_seconds=5.0,
        model_limits={},
    )
    data.update(changes)
    return MeteredRequestLimits(**data)


def usage(**changes):
    data = dict(
        provider="openai",
        model="fixture-model",
        calls=1,
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=0.01,
    )
    data.update(changes)
    return data


def context():
    task = Task(
        objective="Set ISSUE-1 to done",
        requirements=(Requirement(issue_id="ISSUE-1", status=Status.DONE),),
    )
    state = ReflectionState(
        phase="execute",
        budget=Budget(max_actions=8, max_decisions=8),
        actions=0,
        decisions=0,
        corrective_admissions=0,
    )
    return task, state


@pytest.mark.parametrize(
    "field", ["verification", "SQLite_path", "hidden_faults", "eligibility", "credentials"]
)
def test_payload_rejects_extra_private_fields(field):
    task, state = context()
    raw = dict(task=task.model_dump(mode="json"), state=state.model_dump(mode="json"))
    raw["state"][field] = "private-canary"
    with pytest.raises(ValidationError):
        ReflectionInput(**raw)
    assert "private-canary" not in str(reflection_payload(task, state))


@pytest.mark.parametrize("value", [True, 1.0, "1", -1])
@pytest.mark.parametrize("field", ["actions", "decisions", "corrective_admissions"])
def test_strict_nested_counters(field, value):
    task, state = context()
    raw = state.model_dump(mode="json")
    raw[field] = value
    with pytest.raises(ValidationError):
        ReflectionInput(task=task, state=raw)


def test_boundary_detached_frozen_and_shared_caps():
    task, state = context()
    payload = reflection_payload(task, state)
    payload["state"]["actions"] = 7
    assert state.actions == 0
    raw = state.model_dump(mode="json")
    raw["actions"] = 9
    with pytest.raises(ValidationError):
        ReflectionInput(task=task, state=raw)
    validated = ReflectionInput(task=task, state=state)
    with pytest.raises(ValidationError):
        validated.task = task


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_requests", True),
        ("max_requests", 1.0),
        ("max_requests", "2"),
        ("max_requests", -1),
        ("per_request_max_output_tokens", 127),
        ("per_request_max_output_tokens", True),
        ("request_timeout_seconds", float("nan")),
        ("request_timeout_seconds", float("inf")),
        ("request_timeout_seconds", 0),
        ("request_timeout_seconds", True),
    ],
)
def test_strict_request_limits(field, value):
    with pytest.raises(ValidationError):
        limits(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_total_tokens", True),
        ("max_output_tokens", "256"),
        ("max_cost_usd", True),
        ("max_cost_usd", float("nan")),
    ],
)
def test_strict_nested_model_limits(field, value):
    with pytest.raises(ValidationError):
        limits(model_limits={field: value})


def test_attempt_pending_settlement_and_cumulative_balance():
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    assert ledger.state["request_attempts"] == 0
    ticket = ledger.admit(remaining_seconds=2)
    assert ticket.timeout_seconds == 2 and ticket.output_allowance == 256
    assert ledger.state["request_attempts"] == ledger.budget_state.usage.calls == 1
    assert ledger.budget_state.usage.total_tokens is None and ledger.usage.calls == 1
    ledger.complete(ticket, usage())
    assert ledger.budget_state.usage.total_tokens == 30
    second = ledger.admit(remaining_seconds=20)
    assert second.timeout_seconds == 5
    ledger.complete(second, usage(input_tokens=3, output_tokens=4))
    assert ledger.usage.calls == 1 and ledger.usage.total_tokens == 7
    assert ledger.budget_state.usage.calls == ledger.state["request_attempts"] == 2
    assert ledger.budget_state.usage.total_tokens == 37
    detached = ledger.state
    detached["request_attempts"] = 999
    assert ledger.state["request_attempts"] == 2


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "1"])
def test_invalid_deadline_not_dispatched(value):
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    with pytest.raises(ValueError):
        ledger.admit(remaining_seconds=value)
    assert ledger.state["request_attempts"] == 0


@pytest.mark.parametrize(
    "limit,remaining,reason",
    [(0, 1, "request_limit_exhausted"), (4, 0, "request_deadline_exhausted")],
)
def test_denial_before_dispatch(limit, remaining, reason):
    ledger = MeteredRequestLedger(limits(max_requests=limit), "fixture-model")
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.admit(remaining_seconds=remaining)
    assert ledger.budget_state.usage.calls == ledger.usage.calls == 0
    assert not ledger.state["pending"]


def test_ticket_identity_pending_and_reset_guards():
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    ticket = ledger.admit(remaining_seconds=1)
    with pytest.raises(ValueError):
        ledger.admit(remaining_seconds=1)
    with pytest.raises(ValueError):
        ledger.begin_run()
    with pytest.raises(ValueError):
        ledger.complete(DispatchTicket(ticket.output_allowance, ticket.timeout_seconds), usage())
    ledger.complete(ticket, usage())
    with pytest.raises(ValueError):
        ledger.complete(ticket, usage())
    assert ledger.state["request_attempts"] == 1
    ledger.begin_run()
    assert ledger.budget_state.usage.calls == ledger.state["request_attempts"] == 0


def test_quota_denial_clears_snapshot_without_double_charging():
    ledger = MeteredRequestLedger(limits(max_requests=1), "fixture-model")
    ledger.complete(ledger.admit(remaining_seconds=1), usage())
    with pytest.raises(ModelBudgetExceeded):
        ledger.admit(remaining_seconds=1)
    assert ledger.usage.calls == 0 and ledger.budget_state.usage.calls == 1


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_unknown_usage_retains_partial_known_work_and_halts(field):
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    ledger.complete(ledger.admit(remaining_seconds=1), usage())
    ticket = ledger.admit(remaining_seconds=1)
    with pytest.raises(ModelBudgetExceeded, match="token_usage_unknown"):
        ledger.complete(ticket, usage(**{field: None}))
    assert ledger.budget_state.usage.calls == 2 and ledger.budget_state.usage.total_tokens is None
    assert ledger.state["known_input_tokens"] == (10 if field == "input_tokens" else 20)
    assert ledger.state["known_output_tokens"] == (20 if field == "output_tokens" else 40)
    with pytest.raises(ModelBudgetExceeded):
        ledger.admit(remaining_seconds=1)


def test_failed_unknown_request_charged_and_primary_failure_preserved():
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    ledger.fail(ledger.admit(remaining_seconds=1))
    assert ledger.state["request_attempts"] == ledger.state["failed_requests"] == 1
    assert ledger.state["provider_failed"] and ledger.state["stop_reason"] == "token_usage_unknown"
    assert ledger.budget_state.usage.total_tokens is None
    with pytest.raises(ModelBudgetExceeded):
        ledger.admit(remaining_seconds=1)


@pytest.mark.parametrize(
    "model_limits,current,reason",
    [
        ({}, usage(output_tokens=257), "request_output_exceeded"),
        ({"max_total_tokens": 25}, usage(), "total_tokens_exceeded"),
        ({"max_output_tokens": 128}, usage(output_tokens=129), "request_output_exceeded"),
        ({"max_cost_usd": 0.005}, usage(), "cost_threshold_exceeded"),
        ({"max_cost_usd": 1.0}, usage(estimated_cost_usd=None), "cost_usage_unknown"),
    ],
)
def test_response_stops_after_charging(model_limits, current, reason):
    ledger = MeteredRequestLedger(limits(model_limits=model_limits), "fixture-model")
    ticket = ledger.admit(remaining_seconds=1)
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.complete(ticket, current)
    assert ledger.budget_state.usage.calls == 1 and not ledger.state["pending"]


def test_known_provider_failure_and_secondary_overshoot():
    ledger = MeteredRequestLedger(limits(model_limits={"max_total_tokens": 1}), "fixture-model")
    ledger.fail(ledger.admit(remaining_seconds=1), usage())
    assert (
        ledger.state["provider_failed"] and ledger.state["stop_reason"] == "total_tokens_exceeded"
    )
    assert ledger.budget_state.usage.total_tokens == 30


def test_unknown_cost_without_limit_remains_null_and_known_cost_separate():
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    ledger.complete(ledger.admit(remaining_seconds=1), usage(estimated_cost_usd=None))
    ledger.complete(ledger.admit(remaining_seconds=1), usage())
    assert ledger.budget_state.usage.estimated_cost_usd is None
    assert ledger.state["known_estimated_cost_usd"] == 0.01


def test_output_remainder_denial_and_zero_cost_limit():
    ledger = MeteredRequestLedger(limits(model_limits={"max_output_tokens": 300}), "fixture-model")
    ledger.complete(ledger.admit(remaining_seconds=1), usage(output_tokens=200))
    with pytest.raises(ModelBudgetExceeded, match="output_allowance_insufficient"):
        ledger.admit(remaining_seconds=1)
    assert ledger.state["request_attempts"] == 1
    zero = MeteredRequestLedger(limits(model_limits={"max_cost_usd": 0.0}), "fixture-model")
    with pytest.raises(ModelBudgetExceeded, match="cost_threshold_reached"):
        zero.admit(remaining_seconds=1)
    assert zero.state["request_attempts"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"calls": 0},
        {"calls": True},
        {"input_tokens": True},
        {"provider": "mock"},
        {"estimated_cost_usd": float("inf")},
    ],
)
def test_invalid_usage_does_not_erase_pending_attempt(change):
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    ticket = ledger.admit(remaining_seconds=1)
    current = copy.deepcopy(usage())
    current.update(change)
    with pytest.raises((ValueError, ValidationError)):
        ledger.complete(ticket, current)
    assert ledger.state["pending"] and ledger.state["request_attempts"] == 1
    ledger.fail(ticket)
    assert ledger.budget_state.usage.calls == 1


def test_no_network_or_mock_contract_change(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Network construction forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    task, state = context()
    reflection_payload(task, state)
    ledger = MeteredRequestLedger(limits(), "fixture-model")
    ledger.complete(ledger.admit(remaining_seconds=1), usage())
    assert ReflectionReport.model_fields["model_calls"].default == 0


@pytest.mark.parametrize(
    "mutation", ["task_extra", "budget_boolean", "feedback_boolean", "feedback_window"]
)
def test_nested_payload_rejection(mutation):
    task, state = context()
    raw = dict(task=task.model_dump(mode="json"), state=state.model_dump(mode="json"))
    item = dict(
        action=dict(tool="read_issue", issue_id="ISSUE-1", status=None),
        reported_success=True,
        failure=None,
        observed_status="open",
    )
    if mutation == "task_extra":
        raw["task"]["trusted_verification"] = "private-canary"
    elif mutation == "budget_boolean":
        raw["state"]["budget"]["max_actions"] = True
    elif mutation == "feedback_boolean":
        item["reported_success"] = 1
        raw["state"]["feedback"] = [item]
    else:
        raw["state"]["feedback"] = [item] * 17
    with pytest.raises(ValidationError):
        ReflectionInput(**raw)
