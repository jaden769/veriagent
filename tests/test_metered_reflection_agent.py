import copy
import json
from types import SimpleNamespace as NS

import pytest

from analysis.metered_reflection import MeteredRequestLimits
from analysis.metered_reflection_agent import MeteredReflectionAgent, MeteredReflectionReport
from analysis.metered_reflection_provider import MeteredReflectionProvider
from analysis.metered_reflection_trace import reconcile_metered_trace
from veriagent.executor import Executor
from veriagent.models import Budget, Task
from veriagent.reflection import MockReflectionProvider, ReflectionState
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def build(tmp_path, *, faults=None, max_requests=12, transport=None, clock=None):
    tools = Sandbox(tmp_path / "state.sqlite", faults)
    tools.seed()
    traces = TraceStore(tmp_path / "trace.sqlite")
    calls = []

    def scripted(**kwargs):
        calls.append(kwargs)
        data = json.loads(kwargs["input"])
        task = Task.model_validate_json(json.dumps(data["task"]))
        state = ReflectionState.model_validate_json(json.dumps(data["state"]))
        d = MockReflectionProvider().decide(task, state, timeout=kwargs["timeout"])
        if d.kind == "finish":
            name, args = "finish_task", {}
        else:
            name = d.action.tool
            args = d.action.model_dump(mode="json", exclude={"tool"})
            if name == "read_issue":
                args.pop("status")
        return NS(
            status="completed",
            model="fixture",
            usage=NS(input_tokens=10, output_tokens=5),
            output=[
                NS(
                    type="function_call",
                    name=name,
                    arguments=json.dumps(args),
                    status="completed",
                    call_id="fixture",
                )
            ],
        )

    options = {} if clock is None else dict(clock=clock)
    provider = MeteredReflectionProvider(
        model="fixture",
        limits=MeteredRequestLimits(
            max_requests=max_requests,
            per_request_max_output_tokens=128,
            request_timeout_seconds=2.0,
            model_limits={},
        ),
        transport=transport or scripted,
        **options,
    )
    agent = MeteredReflectionAgent(
        Executor(tools), traces, Budget(max_actions=8, max_decisions=8), provider=provider
    )
    task = Task.model_validate(
        dict(
            objective="Set ISSUE-1 to done", requirements=[dict(issue_id="ISSUE-1", status="done")]
        )
    )
    return agent, task, tools, traces, calls


@pytest.mark.parametrize(
    "faults",
    [Faults(), Faults(silent_drops=1), Faults(silent_drops=20), Faults(transient_errors=1)],
)
def test_native_metered_report_and_phase_accounting(tmp_path, faults):
    agent, task, tools, traces, calls = build(tmp_path, faults=copy.deepcopy(faults))
    report = agent.run(task)
    assert type(report) is MeteredReflectionReport and report.verified_success is None
    assert report.model_calls == report.request_attempts == len(calls) == report.decisions
    assert report.model_tokens == 15 * len(calls)
    replay = reconcile_metered_trace(traces.events(report.run_id), expected_run_id=report.run_id)
    assert replay["consistency_passed"] and replay["trusted_verification_calls"] == 0
    assert replay["request_attempts"] == len(calls)
    if not faults.silent_drops:
        assert StateVerifier(tools.path).verify(task).passed


@pytest.mark.parametrize("max_requests", [0, 1, 3])
def test_request_exhaustion_remains_budget_and_honest(tmp_path, max_requests):
    agent, task, _, traces, calls = build(tmp_path, max_requests=max_requests)
    report = agent.run(task)
    assert report.failure == "budget" and not report.claimed_success
    assert len(calls) == report.request_attempts == max_requests
    assert report.decisions == max_requests + 1
    assert reconcile_metered_trace(traces.events(report.run_id), expected_run_id=report.run_id)[
        "consistency_passed"
    ]


@pytest.mark.parametrize("kind", ["transport", "malformed", "unknown", "permission"])
def test_request_failures_charged_and_reconciled(tmp_path, kind):
    def failure(**kwargs):
        if kind == "transport":
            raise TimeoutError("private-canary")
        output = (
            []
            if kind == "malformed"
            else [
                NS(
                    type="function_call",
                    name="read_issue",
                    arguments='{"issue_id":"ISSUE-2"}'
                    if kind == "permission"
                    else '{"issue_id":"ISSUE-1"}',
                    status="completed",
                    call_id="fixture",
                )
            ]
        )
        return NS(
            status="completed",
            model="fixture",
            usage=None if kind == "unknown" else NS(input_tokens=10, output_tokens=5),
            output=output,
        )

    agent, task, _, traces, _ = build(tmp_path, transport=failure)
    report = agent.run(task)
    assert report.actions == 0 and report.request_attempts == 1 and not report.claimed_success
    assert report.failure == (
        {"unknown": "budget", "permission": "permission"}.get(kind, "planning")
    )
    events = traces.events(report.run_id)
    assert "private-canary" not in json.dumps(events)
    assert reconcile_metered_trace(events, expected_run_id=report.run_id)["consistency_passed"]


def test_reused_controller_resets_usage_and_new_identity(tmp_path):
    agent, task, _, traces, _ = build(tmp_path)
    first = agent.run(task)
    second = agent.run(task)
    assert (
        first.run_id != second.run_id
        and first.request_attempts == 5
        and second.request_attempts == 4
    )
    assert reconcile_metered_trace(traces.events(second.run_id), expected_run_id=second.run_id)[
        "consistency_passed"
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "before",
        "usage",
        "report",
        "model_calls",
        "claim",
        "oracle",
        "timeout",
        "remove",
        "diagnostic",
        "failure",
    ],
)
def test_trace_corruption_rejected(tmp_path, mutation):
    agent, task, _, traces, _ = build(tmp_path)
    report = agent.run(task)
    events = copy.deepcopy(traces.events(report.run_id))
    accounting = next(e for e in events if e["kind"] == "metered_decision_accounting")
    if mutation == "before":
        accounting["payload"]["before"]["request_attempts"] = 1
    elif mutation == "usage":
        accounting["payload"]["after"]["usage"]["input_tokens"] += 1
    elif mutation == "report":
        events[-1]["payload"]["request_state"]["settled_requests"] += 1
    elif mutation == "model_calls":
        events[-1]["payload"]["model_calls"] = True
    elif mutation == "claim":
        events[-1]["payload"]["claimed_success"] = False
    elif mutation == "oracle":
        next(e for e in events if e["kind"] == "reflection_context")["payload"]["verification"] = {
            "passed": True
        }
    elif mutation == "timeout":
        accounting["payload"]["dispatch"]["timeout_seconds"] = 999
    elif mutation == "remove":
        events.remove(accounting)
    elif mutation == "diagnostic":
        accounting["payload"]["diagnostic"] = {
            "category": "response_validation",
            "detail": "private-canary",
        }
    else:
        accounting["payload"]["outcome"] = "planning"
    for i, e in enumerate(events, 1):
        e["seq"] = i
    with pytest.raises(ValueError):
        reconcile_metered_trace(events, expected_run_id=report.run_id)


def test_replay_invokes_no_provider_tool_or_oracle(tmp_path, monkeypatch):
    agent, task, _, traces, _ = build(tmp_path)
    report = agent.run(task)
    events = traces.events(report.run_id)

    def forbidden(*args, **kwargs):
        pytest.fail("Replay executed a provider/tool/oracle")

    monkeypatch.setattr(agent.provider, "decide", forbidden)
    monkeypatch.setattr(Executor, "execute", forbidden)
    monkeypatch.setattr(StateVerifier, "verify", forbidden)
    assert reconcile_metered_trace(events, expected_run_id=report.run_id)["consistency_passed"]


def test_cancellation_retains_partial_trace_without_report(tmp_path):
    def cancel(**kwargs):
        raise KeyboardInterrupt()

    agent, task, _, traces, _ = build(tmp_path, transport=cancel)
    with pytest.raises(KeyboardInterrupt):
        agent.run(task)
    import sqlite3

    with sqlite3.connect(traces.path) as db:
        run_id = db.execute("SELECT run_id FROM events LIMIT 1").fetchone()[0]
    events = traces.events(run_id)
    assert events[-1]["payload"]["outcome"] == "cancelled"
    assert events[-1]["payload"]["after"]["request_attempts"] == 1
    with pytest.raises(ValueError):
        reconcile_metered_trace(events, expected_run_id=run_id)


def test_false_claim_stays_distinct_from_final_sql_truth(tmp_path):
    def optimistic(**kwargs):
        return NS(
            status="completed",
            model="fixture",
            usage=NS(input_tokens=10, output_tokens=5),
            output=[
                NS(
                    type="function_call",
                    name="finish_task",
                    arguments="{}",
                    status="completed",
                    call_id="fixture",
                )
            ],
        )

    agent, task, tools, traces, _ = build(tmp_path, transport=optimistic)
    report = agent.run(task)
    assert report.claimed_success and not StateVerifier(tools.path).verify(task).passed
    assert report.verified_success is None
    assert reconcile_metered_trace(traces.events(report.run_id), expected_run_id=report.run_id)[
        "consistency_passed"
    ]


def test_known_overshoot_does_not_execute_actions(tmp_path):
    agent, task, _, traces, _ = build(tmp_path)
    from analysis.metered_reflection import MeteredRequestLimits

    agent.provider = MeteredReflectionProvider(
        model="fixture",
        limits=MeteredRequestLimits(
            max_requests=2,
            per_request_max_output_tokens=128,
            request_timeout_seconds=2.0,
            model_limits={"max_total_tokens": 1},
        ),
        transport=lambda **k: NS(
            status="completed",
            model="fixture",
            usage=NS(input_tokens=10, output_tokens=5),
            output=[
                NS(
                    type="function_call",
                    name="read_issue",
                    arguments='{"issue_id":"ISSUE-1"}',
                    status="completed",
                    call_id="fixture",
                )
            ],
        ),
    )
    report = agent.run(task)
    assert report.failure == "budget" and report.actions == 0 and report.model_tokens == 15
    assert reconcile_metered_trace(traces.events(report.run_id), expected_run_id=report.run_id)[
        "consistency_passed"
    ]


def test_native_report_rejects_usage_and_pending_tampering(tmp_path):
    agent, task, _, _, _ = build(tmp_path)
    report = agent.run(task)
    for field, value in [
        ("model_tokens", 999),
        ("request_attempts", 0),
        ("comparator", "mock_self_reflection"),
    ]:
        raw = report.model_dump(mode="json")
        raw[field] = value
        with pytest.raises(ValueError):
            MeteredReflectionReport.model_validate_json(json.dumps(raw), strict=True)
    raw = report.model_dump(mode="json")
    raw["request_state"]["pending"] = True
    with pytest.raises(ValueError):
        MeteredReflectionReport.model_validate_json(json.dumps(raw), strict=True)


def test_late_response_stops_controller_before_action(tmp_path):
    ticks = iter([0.0, 0.0, 100.0])
    agent, task, _, traces, _ = build(tmp_path, clock=lambda: next(ticks))
    report = agent.run(task)
    assert report.failure == "budget" and report.actions == 0 and report.request_attempts == 1
    assert reconcile_metered_trace(traces.events(report.run_id), expected_run_id=report.run_id)[
        "consistency_passed"
    ]


def test_nonidempotent_repeat_is_denied_with_trusted_policy_replay(tmp_path):
    from veriagent.executor import ToolPolicy

    agent, task, _, traces, _ = build(tmp_path, faults=Faults(silent_drops=1))
    agent.executor.policies["set_status"] = ToolPolicy(idempotent=False)
    report = agent.run(task)
    assert report.failure == "permission" and not report.claimed_success
    assert reconcile_metered_trace(
        traces.events(report.run_id),
        expected_run_id=report.run_id,
        policies=agent.executor.policies,
    )["consistency_passed"]


@pytest.mark.parametrize("mutation", ["provider_shape", "missing_after"])
def test_malformed_nested_frames_are_sanitized(tmp_path, mutation):
    agent, task, _, traces, _ = build(tmp_path)
    report = agent.run(task)
    events = copy.deepcopy(traces.events(report.run_id))
    if mutation == "provider_shape":
        events[1]["payload"]["provider"] = None
    else:
        next(e for e in events if e["kind"] == "metered_decision_accounting")["payload"][
            "after"
        ] = {"private-canary": True}
    with pytest.raises(ValueError) as caught:
        reconcile_metered_trace(events, expected_run_id=report.run_id)
    assert "private-canary" not in str(caught.value)


def test_malformed_token_types_rejected_before_cost_arithmetic(tmp_path):
    agent, task, _, traces, _ = build(tmp_path)
    report = agent.run(task)
    events = copy.deepcopy(traces.events(report.run_id))
    events[1]["payload"]["provider"]["prices"] = [1000000, 1000000]
    event = next(e for e in events if e["kind"] == "metered_decision_accounting")
    event["payload"]["after"]["usage"]["input_tokens"] = "private-canary"
    with pytest.raises(ValueError) as caught:
        reconcile_metered_trace(events, expected_run_id=report.run_id)
    assert "private-canary" not in str(caught.value)


def test_priced_usage_reconciles_from_public_rates(tmp_path):
    agent, task, _, traces, _ = build(tmp_path)
    old = agent.provider
    agent.provider = MeteredReflectionProvider(
        model=old.model,
        limits=old.ledger.limits,
        transport=old.transport,
        input_usd_per_million=1.0,
        output_usd_per_million=2.0,
    )
    report = agent.run(task)
    assert report.model_usage.estimated_cost_usd == pytest.approx(report.model_calls * 0.00002)
    assert reconcile_metered_trace(traces.events(report.run_id), expected_run_id=report.run_id)[
        "consistency_passed"
    ]
