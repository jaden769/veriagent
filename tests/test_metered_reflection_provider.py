import json
import socket
from types import SimpleNamespace as NS

import pytest

from analysis.metered_reflection import MeteredRequestLimits
from analysis.metered_reflection_provider import MeteredReflectionProvider
from veriagent.budgeting import ModelBudgetExceeded
from veriagent.models import Budget, Requirement, Status, Task
from veriagent.openai_provider import ProviderError
from veriagent.reflection import ReflectionState


def context(phase="execute"):
    return (
        Task(
            objective="Set ISSUE-1 to done",
            requirements=(Requirement(issue_id="ISSUE-1", status=Status.DONE),),
        ),
        ReflectionState(
            phase=phase,
            budget=Budget(max_actions=8, max_decisions=8),
            actions=0,
            decisions=0,
            corrective_admissions=int(phase == "reflect"),
        ),
    )


def call(name="read_issue", arguments='{"issue_id":"ISSUE-1"}'):
    return NS(
        type="function_call",
        name=name,
        arguments=arguments,
        status="completed",
        call_id="fixture-call",
    )


def response(output=None, usage=True, status="completed"):
    return NS(
        model="served-model",
        status=status,
        output=[call()] if output is None else output,
        usage=NS(input_tokens=10, output_tokens=20) if usage is True else usage,
    )


class Transport:
    def __init__(self, reply=None, error=None):
        self.reply = response() if reply is None else reply
        self.error = error
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.reply


def provider(transport=None, **changes):
    limits = MeteredRequestLimits(
        max_requests=changes.pop("max_requests", 4),
        per_request_max_output_tokens=256,
        request_timeout_seconds=2.0,
        model_limits=changes.pop("model_limits", {}),
    )
    return MeteredReflectionProvider(
        model="fixture-model", limits=limits, transport=transport or Transport(), **changes
    )


def test_stateless_execute_reflect_payload_and_shared_usage(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Network forbidden"))
    transport = Transport()
    p = provider(transport)
    for phase in ["execute", "reflect"]:
        task, state = context(phase)
        assert p.decide(task, state, timeout=5).action.tool == "read_issue"
    assert len(transport.calls) == p.budget_state.usage.calls == 2 and p.usage.calls == 1
    for payload in transport.calls:
        data = json.loads(payload["input"])
        assert set(data) == {"task", "state"} and "verification" not in data["state"]
        assert payload["store"] is False and payload["parallel_tool_calls"] is False
        assert payload["timeout"] <= 2 and payload["max_output_tokens"] == 256
        assert "trusted verification" not in payload["tools"][-1]["description"].replace(
            "not trusted verification", ""
        )
    p.begin_run()
    assert p.budget_state.usage.calls == 0 and p.diagnostic is None


@pytest.mark.parametrize(
    "output",
    [[call("finish_task", "{}")], [call("set_status", '{"issue_id":"ISSUE-1","status":"done"}')]],
)
def test_finish_and_authorized_write(output):
    p = provider(Transport(response(output)))
    result = p.decide(*context(), timeout=2)
    assert result.kind in {"finish", "action"} and p.budget_state.usage.calls == 1


@pytest.mark.parametrize(
    "output",
    [
        [],
        [call(), call()],
        [call("unknown")],
        [call(arguments="bad")],
        [call(arguments='{"issue_id":"ISSUE-1","issue_id":"ISSUE-2"}')],
        [call(arguments='{"issue_id":"ISSUE-1","private":"canary"}')],
        [NS(type="message", content="refused")],
        [call(arguments="x" * 65537)],
    ],
)
def test_invalid_output_charged_once(output):
    p = provider(Transport(response(output)))
    with pytest.raises(ProviderError):
        p.decide(*context(), timeout=2)
    assert p.budget_state.usage.calls == 1
    assert p.ledger.state["failed_requests"] == p.ledger.state["settled_requests"] == 1
    assert p.budget_state.usage.total_tokens == 30


@pytest.mark.parametrize(
    "reply", [response(usage=None), response(usage=NS(input_tokens=None, output_tokens=20))]
)
def test_valid_output_unknown_usage_is_budget_stop(reply):
    p = provider(Transport(reply))
    with pytest.raises(ModelBudgetExceeded, match="token_usage_unknown"):
        p.decide(*context(), timeout=2)
    assert p.budget_state.usage.calls == 1 and p.budget_state.usage.total_tokens is None
    assert p.ledger.state["failed_requests"] == 0


@pytest.mark.parametrize("status", ["incomplete", "failed"])
def test_incomplete_primary_despite_unknown_usage(status):
    p = provider(Transport(response(usage=None, status=status)))
    with pytest.raises(ProviderError):
        p.decide(*context(), timeout=2)
    assert p.ledger.state["stop_reason"] == "token_usage_unknown"
    assert p.ledger.state["failed_requests"] == p.budget_state.usage.calls == 1
    assert p.diagnostic.category == "incomplete_response"


def test_invalid_usage_metadata_primary_and_unknown():
    p = provider(Transport(response(usage=NS(input_tokens=True, output_tokens=20))))
    with pytest.raises(ProviderError):
        p.decide(*context(), timeout=2)
    assert (
        p.diagnostic.category == "usage_unavailable" and p.budget_state.usage.total_tokens is None
    )
    assert p.ledger.state["failed_requests"] == 1


@pytest.mark.parametrize(
    "error", [TimeoutError("private-canary"), ConnectionError("private-canary")]
)
def test_transport_error_no_retry_or_secret(error):
    transport = Transport(error=error)
    p = provider(transport)
    with pytest.raises(ProviderError) as caught:
        p.decide(*context(), timeout=2)
    assert "private-canary" not in str(caught.value) + str(p.diagnostic.model_dump())
    assert len(transport.calls) == p.budget_state.usage.calls == 1
    assert p.budget_state.usage.total_tokens is None
    with pytest.raises(ModelBudgetExceeded):
        p.decide(*context(), timeout=2)
    assert len(transport.calls) == 1


def test_cancellation_settles_before_propagating():
    p = provider(Transport(error=KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        p.decide(*context(), timeout=2)
    assert not p.ledger.state["pending"] and p.ledger.state["failed_requests"] == 1


@pytest.mark.parametrize(
    "name,args",
    [
        ("read_issue", '{"issue_id":"ISSUE-2"}'),
        ("set_status", '{"issue_id":"ISSUE-1","status":"open"}'),
    ],
)
def test_unauthorized_decision_never_returned(name, args):
    p = provider(Transport(response([call(name, args)])))
    with pytest.raises(PermissionError):
        p.decide(*context(), timeout=2)
    assert p.budget_state.usage.calls == 1 and p.diagnostic.category == "permission"


def test_overshoot_after_charge_without_action():
    p = provider(model_limits={"max_total_tokens": 1})
    with pytest.raises(ModelBudgetExceeded, match="total_tokens_exceeded"):
        p.decide(*context(), timeout=2)
    assert p.budget_state.usage.total_tokens == 30


def test_invalid_output_primary_despite_overshoot():
    p = provider(Transport(response([])), model_limits={"max_total_tokens": 1})
    with pytest.raises(ProviderError):
        p.decide(*context(), timeout=2)
    assert p.ledger.state["stop_reason"] == "total_tokens_exceeded"
    assert p.ledger.state["failed_requests"] == 1


def test_late_finish_rejected_and_admission_closed():
    times = iter([0.0, 0.0, 3.0])
    p = provider(Transport(response([call("finish_task", "{}")])), clock=lambda: next(times))
    with pytest.raises(ModelBudgetExceeded, match="response_deadline_exhausted"):
        p.decide(*context(), timeout=2)
    assert p.budget_state.usage.calls == 1


@pytest.mark.parametrize("kind", ["quota", "deadline", "action", "decision", "private"])
def test_preflight_denial_does_not_dispatch(kind):
    transport = Transport()
    p = provider(transport, max_requests=0 if kind == "quota" else 4)
    task, state = context()
    if kind in {"action", "decision"}:
        state = state.model_copy(update={"actions" if kind == "action" else "decisions": 8})
    if kind == "private":
        state = dict(state.model_dump(mode="json"), verification="canary")
    with pytest.raises((ModelBudgetExceeded, ProviderError)):
        p.decide(task, state, timeout=0 if kind == "deadline" else 2)
    assert not transport.calls and p.budget_state.usage.calls == 0


def test_explicit_cost_estimation_and_missing_price_rejection():
    with pytest.raises(ValueError):
        provider(model_limits={"max_cost_usd": 1.0})
    p = provider(input_usd_per_million=1.0, output_usd_per_million=2.0)
    p.decide(*context(), timeout=2)
    assert p.budget_state.usage.estimated_cost_usd == pytest.approx(0.00005)


@pytest.mark.parametrize("missing", ["usage", "input_tokens"])
def test_missing_usage_fields_halt_without_fabricated_zero(missing):
    reply = response()
    if missing == "usage":
        del reply.usage
    else:
        del reply.usage.input_tokens
    p = provider(Transport(reply))
    with pytest.raises(ModelBudgetExceeded, match="token_usage_unknown"):
        p.decide(*context(), timeout=2)
    assert p.budget_state.usage.calls == 1 and p.budget_state.usage.total_tokens is None


def test_http_error_diagnostic_drops_all_response_excerpts():
    class APIError(Exception):
        status_code = 400
        code = "unsupported_parameter"
        param = "model"
        body = {"error": {"message": "private-canary"}}

    p = provider(Transport(error=APIError("private-canary")))
    with pytest.raises(ProviderError) as caught:
        p.decide(*context(), timeout=2)
    assert p.diagnostic.http_status == 400 and p.diagnostic.detail is None
    assert "private-canary" not in str(caught.value) + str(p.diagnostic.model_dump())


def test_cancellation_while_reading_usage_settles_pending_request():
    class InterruptedResponse:
        @property
        def usage(self):
            raise KeyboardInterrupt()

    p = provider(Transport(InterruptedResponse()))
    with pytest.raises(KeyboardInterrupt):
        p.decide(*context(), timeout=2)
    assert not p.ledger.state["pending"]
    assert p.ledger.state["failed_requests"] == p.budget_state.usage.calls == 1
    assert p.budget_state.usage.total_tokens is None
