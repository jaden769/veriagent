"""Actual SDK function-call parsing; all HTTP is handled by an in-memory transport."""

import json
from contextlib import contextmanager

import pytest

from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget, Failure, ModelLimits
from veriagent.openai_provider import OpenAIConfig, OpenAIProvider
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def function_call(name, arguments, call_id="call_test"):
    return {
        "type": "function_call",
        "id": "fc_test",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments),
        "status": "completed",
    }


@contextmanager
def sdk_transport(outputs):
    openai = pytest.importorskip("openai", reason="Install the optional OpenAI extra")
    import httpx

    outputs = iter(outputs)
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["parallel_tool_calls"] is False and body["tool_choice"] == "required"
        assert body["store"] is False
        assert {tool["name"] for tool in body["tools"]} == {
            "read_issue",
            "set_status",
            "finish_task",
        }
        assert all(tool["strict"] for tool in body["tools"])
        output = next(outputs)
        if output == "rate_limit":
            return httpx.Response(429, json={"error": {"message": "SECRET-API-ERROR"}})
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "model": "test-model-snapshot",
                "status": "completed",
                "output": output,
                "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with openai.OpenAI(
            api_key="test-placeholder", max_retries=0, http_client=http_client
        ) as client:
            yield client, requests


def run_agent(tmp_path, client, *, faults=None, budget=None, limits=None):
    sandbox = Sandbox(tmp_path / "state.sqlite", faults)
    sandbox.seed()
    provider = OpenAIProvider(
        OpenAIConfig(
            model="test-model",
            input_usd_per_million=1,
            output_usd_per_million=2,
            limits=limits or ModelLimits(),
        ),
        client=client,
    )
    traces = TraceStore(tmp_path / "traces.sqlite")
    report = DynamicAgent(
        provider,
        Executor(sandbox),
        StateVerifier(sandbox.path),
        traces,
        budget or Budget(timeout_seconds=60),
    ).run(MockProvider().parse("Set ISSUE-1 to done"))
    return report, sandbox, traces


def test_sdk_dynamic_recovery_observes_results_and_aggregates_usage(tmp_path):
    outputs = [
        [function_call("read_issue", {"issue_id": "ISSUE-1"}, "read_1")],
        [function_call("set_status", {"issue_id": "ISSUE-1", "status": "done"}, "write_1")],
        [function_call("read_issue", {"issue_id": "ISSUE-1"}, "read_2")],
        [function_call("set_status", {"issue_id": "ISSUE-1", "status": "done"}, "write_2")],
    ]
    with sdk_transport(outputs) as (client, requests):
        report, sandbox, traces = run_agent(tmp_path, client, faults=Faults(silent_drops=1))
    assert report.verified_success and report.recovery_attempts == 1
    assert report.actions == report.decisions == report.model_calls == len(requests) == 4
    assert report.model_tokens == 600
    assert report.estimated_cost_usd == pytest.approx(0.0008)
    assert sandbox.read_issue("ISSUE-1").version == 1
    assert json.loads(requests[1]["input"])["state"]["feedback"][0]["observed_status"] == "open"
    assert json.loads(requests[2]["input"])["state"]["verification"]["failure"] == "state_mismatch"
    assert json.loads(requests[0]["input"])["state"]["budget"]["max_decisions"] == 20
    assert json.loads(requests[2]["input"])["state"]["decisions"] == 2
    decisions = [e["payload"] for e in traces.events(report.run_id) if e["kind"] == "decision"]
    assert [d["call_id"] for d in decisions] == ["read_1", "write_1", "read_2", "write_2"]


@pytest.mark.parametrize(
    "output,failure",
    [
        ([function_call("delete_issue", {"issue_id": "ISSUE-1"})], Failure.PLANNING),
        (
            [function_call("read_issue", {"issue_id": "ISSUE-1", "idempotent": True})],
            Failure.PLANNING,
        ),
        (
            [function_call("set_status", {"issue_id": "ISSUE-1", "status": "open"})],
            Failure.PERMISSION,
        ),
        ([function_call("read_issue", {"issue_id": "ISSUE-2"})], Failure.PERMISSION),
        ([function_call("read_issue", {"issue_id": "ISSUE-1"})] * 2, Failure.PLANNING),
        ([function_call("finish_task", {"approved": True})], Failure.PLANNING),
        ([], Failure.PLANNING),
        (
            [{**function_call("read_issue", {"issue_id": "ISSUE-1"}), "call_id": ""}],
            Failure.PLANNING,
        ),
        (
            [{**function_call("read_issue", {"issue_id": "ISSUE-1"}), "status": "in_progress"}],
            Failure.PLANNING,
        ),
        (
            [
                {
                    "type": "message",
                    "id": "msg_claim",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "Everything succeeded!", "annotations": []}
                    ],
                }
            ],
            Failure.PLANNING,
        ),
    ],
)
def test_invalid_sdk_function_calls_never_execute(tmp_path, output, failure):
    with sdk_transport([output]) as (client, requests):
        report, sandbox, _ = run_agent(tmp_path, client)
    assert report.failure == failure and not report.claimed_success
    assert report.actions == 0 and report.model_calls == len(requests) == 1
    assert report.model_tokens == 150
    assert sandbox.read_issue("ISSUE-1").status == "open"


def test_sdk_rate_limit_stops_without_hidden_retry_or_secret_trace(tmp_path):
    with sdk_transport(["rate_limit"]) as (client, requests):
        report, _, traces = run_agent(tmp_path, client)
    assert report.failure == Failure.PLANNING and report.model_calls == len(requests) == 1
    assert report.model_tokens is None and report.estimated_cost_usd is None
    assert "SECRET-API-ERROR" not in traces.render(report.run_id)


def test_sdk_decision_limit_prevents_an_extra_billable_request(tmp_path):
    with sdk_transport([[function_call("read_issue", {"issue_id": "ISSUE-1"})]]) as (
        client,
        requests,
    ):
        report, _, _ = run_agent(
            tmp_path, client, budget=Budget(timeout_seconds=60, max_decisions=1)
        )
    assert report.failure == Failure.BUDGET and len(requests) == 1


@pytest.mark.parametrize(
    "limits,reason",
    [
        (ModelLimits(max_total_tokens=150), "total_tokens_exhausted"),
        (ModelLimits(max_output_tokens=150), "output_allowance_insufficient"),
        (ModelLimits(max_cost_usd=0.0002), "cost_threshold_reached"),
    ],
)
def test_cumulative_limits_prevent_the_next_sdk_request(tmp_path, limits, reason):
    with sdk_transport([[function_call("read_issue", {"issue_id": "ISSUE-1"})]]) as (
        client,
        requests,
    ):
        report, sandbox, _ = run_agent(tmp_path, client, limits=limits)
    assert report.failure == Failure.BUDGET and report.actions == report.model_calls == 1
    assert report.decisions == 2 and len(requests) == 1
    assert report.model_tokens == 150 and report.model_budget.stop_reason == reason
    assert report.model_budget.usage.calls == 1
    assert sandbox.read_issue("ISSUE-1").status == "open"


def test_remaining_output_allowance_is_applied_to_each_sdk_request(tmp_path):
    outputs = [
        [function_call("read_issue", {"issue_id": "ISSUE-1"})],
        [function_call("set_status", {"issue_id": "ISSUE-1", "status": "done"})],
    ]
    with sdk_transport(outputs) as (client, requests):
        report, _, _ = run_agent(tmp_path, client, limits=ModelLimits(max_output_tokens=200))
    assert report.verified_success and report.model_calls == 2
    assert [r["max_output_tokens"] for r in requests] == [200, 150]
    assert report.model_budget.usage.output_tokens == 100


def test_exact_total_threshold_can_complete_without_an_extra_request(tmp_path):
    outputs = [
        [function_call("read_issue", {"issue_id": "ISSUE-1"})],
        [function_call("set_status", {"issue_id": "ISSUE-1", "status": "done"})],
    ]
    with sdk_transport(outputs) as (client, requests):
        report, _, _ = run_agent(tmp_path, client, limits=ModelLimits(max_total_tokens=300))
    assert report.verified_success and len(requests) == 2
    assert report.model_budget.usage.total_tokens == 300 and report.model_budget.stop_reason is None


def test_cost_threshold_can_overshoot_but_over_limit_decision_cannot_execute(tmp_path):
    outputs = [
        [function_call("read_issue", {"issue_id": "ISSUE-1"})],
        [function_call("set_status", {"issue_id": "ISSUE-1", "status": "done"})],
    ]
    with sdk_transport(outputs) as (client, requests):
        report, sandbox, _ = run_agent(tmp_path, client, limits=ModelLimits(max_cost_usd=0.0003))
    assert report.failure == Failure.BUDGET and report.actions == 1 and len(requests) == 2
    assert report.estimated_cost_usd == pytest.approx(0.0004)
    assert report.model_budget.stop_reason == "cost_threshold_exceeded"
    assert sandbox.read_issue("ISSUE-1").status == "open"


def test_transport_error_with_active_limit_marks_usage_unknown_and_stops(tmp_path):
    with sdk_transport(["rate_limit"]) as (client, requests):
        report, _, traces = run_agent(tmp_path, client, limits=ModelLimits(max_total_tokens=1000))
    assert report.failure == Failure.BUDGET and report.model_calls == len(requests) == 1
    assert report.model_tokens is None and report.model_budget.stop_reason == "token_usage_unknown"
    assert "SECRET-API-ERROR" not in traces.render(report.run_id)
