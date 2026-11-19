"""No credentials, sockets or paid requests: all model responses are injected."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from veriagent.agent import Agent
from veriagent.executor import Executor
from veriagent.interpretation import load_proposal, propose_task
from veriagent.models import Budget, Failure, Status
from veriagent.openai_provider import OpenAIConfig, OpenAIProvider, ProviderError, plan_schema
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.smoke import smoke_test
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


class FakeClient:
    def __init__(self, payload, *, status="completed", usage=True, error=None):
        self.payload = payload
        self.status = status
        self.has_usage = usage
        self.error = error
        self.requests = []
        self.responses = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            status=self.status,
            model="test-model-snapshot",
            output_text=json.dumps(self.payload),
            usage=SimpleNamespace(input_tokens=100, output_tokens=50) if self.has_usage else None,
        )


@pytest.fixture
def payload():
    return {
        "steps": [
            {
                "id": "update",
                "action": {"tool": "set_status", "issue_id": "ISSUE-1", "status": "done"},
                "depends_on": [],
                "expected": {"issue_id": "ISSUE-1", "status": "done"},
            }
        ]
    }


def make_agent(tmp_path, client, config=None, budget=None, faults=None):
    sandbox = Sandbox(tmp_path / "state.sqlite", faults)
    sandbox.seed()
    provider = OpenAIProvider(config or OpenAIConfig(model="test-model"), client=client)
    traces = TraceStore(tmp_path / "traces.sqlite")
    agent = Agent(provider, Executor(sandbox), StateVerifier(sandbox.path), traces, budget)
    return agent, sandbox, traces, provider


def test_model_plan_executes_and_recovery_does_not_make_another_paid_request(tmp_path, payload):
    client = FakeClient(payload)
    config = OpenAIConfig(model="test-model", input_usd_per_million=2, output_usd_per_million=4)
    agent, sandbox, traces, provider = make_agent(
        tmp_path, client, config, faults=Faults(silent_drops=1)
    )
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.verified_success
    assert report.actions == 2 and report.recovery_attempts == 1
    assert sandbox.read_issue("ISSUE-1").status == Status.DONE
    assert report.model_calls == 1 and report.model_tokens == 150
    assert report.estimated_cost_usd == pytest.approx(0.0004)
    assert report.model_usage.model == "test-model-snapshot"
    assert len(client.requests) == 1
    request = client.requests[0]
    assert 0 < request["timeout"] <= agent.budget.timeout_seconds
    assert request["store"] is False and request["max_output_tokens"] == 2048
    assert json.loads(request["input"])["requirements"][0]["issue_id"] == "ISSUE-1"
    assert "model_usage" in [e["kind"] for e in traces.events(report.run_id)]


@pytest.mark.parametrize("attack", ["target", "status", "tool", "permission", "cycle", "empty"])
def test_adversarial_plans_never_execute(tmp_path, payload, attack):
    step = payload["steps"][0]
    if attack == "target":
        step["action"]["issue_id"] = step["expected"]["issue_id"] = "ISSUE-2"
    elif attack == "status":
        step["action"]["status"] = "open"
    elif attack == "tool":
        step["action"]["tool"] = "delete_issue"
    elif attack == "permission":
        step["action"]["idempotent"] = True
    elif attack == "cycle":
        step["depends_on"] = [step["id"]]
    else:
        payload["steps"] = []
    agent, sandbox, traces, provider = make_agent(tmp_path, FakeClient(payload))
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert not report.claimed_success and report.actions == 0
    assert report.failure == Failure.PLANNING
    assert report.model_calls == 1 and report.model_tokens == 150
    assert sandbox.read_issue("ISSUE-1").status == Status.OPEN
    assert sandbox.read_issue("ISSUE-2").status == Status.OPEN
    assert traces.events(report.run_id)[-1]["kind"] == "report"


@pytest.mark.parametrize("status,payload", [("incomplete", {}), ("completed", None)])
def test_incomplete_or_invalid_response_is_traced(tmp_path, status, payload):
    agent, _, _, provider = make_agent(tmp_path, FakeClient(payload, status=status))
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.PLANNING and report.actions == 0
    assert report.model_tokens == 150


def test_missing_usage_remains_unknown(tmp_path, payload):
    agent, _, _, provider = make_agent(tmp_path, FakeClient(payload, usage=False))
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.verified_success
    assert report.model_tokens is None and report.estimated_cost_usd is None


def test_transport_failure_does_not_leak_secrets_or_retry(tmp_path, payload):
    client = FakeClient(payload, error=TimeoutError("SECRET-API-KEY"))
    agent, _, traces, provider = make_agent(tmp_path, client)
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.PLANNING and report.actions == 0
    assert report.model_calls == 1 and report.model_tokens is None
    assert report.estimated_cost_usd is None
    assert len(client.requests) == 1
    assert "SECRET-API-KEY" not in traces.render(report.run_id)


def test_usage_does_not_accumulate_between_runs(tmp_path, payload):
    agent, _, _, provider = make_agent(tmp_path, FakeClient(payload))
    task = provider.parse("Set ISSUE-1 to done")
    assert agent.run(task).model_tokens == agent.run(task).model_tokens == 150


def test_no_default_price_is_invented(tmp_path, payload):
    agent, _, _, provider = make_agent(tmp_path, FakeClient(payload))
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.model_tokens == 150
    assert report.estimated_cost_usd is None


def test_expired_planning_budget_prevents_request(payload):
    client = FakeClient(payload)
    provider = OpenAIProvider(OpenAIConfig(model="test"), client=client)
    with pytest.raises(ProviderError):
        provider.plan(provider.parse("Set ISSUE-1 to done"), timeout=0)
    assert client.requests == [] and provider.usage.calls == 0


def test_late_plan_cannot_execute(tmp_path, payload, monkeypatch):
    agent, sandbox, _, provider = make_agent(
        tmp_path, FakeClient(payload), budget=Budget(timeout_seconds=1)
    )
    original = provider.plan

    def late_plan(task, *, timeout=None):
        plan = original(task, timeout=timeout)
        monkeypatch.setattr("veriagent.agent.time.monotonic", lambda: initial + 2)
        return plan

    import time

    initial = time.monotonic()
    monkeypatch.setattr(provider, "plan", late_plan)
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.BUDGET and report.actions == 0
    assert sandbox.read_issue("ISSUE-1").status == Status.OPEN


def test_missing_credentials_fail_before_client_import(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        OpenAIProvider.from_env(OpenAIConfig(model="test"))


@pytest.mark.parametrize(
    "values",
    [
        {"model": ""},
        {"model": "test", "input_usd_per_million": 2},
        {"model": "test", "request_timeout_seconds": float("nan")},
        {"model": "test", "input_usd_per_million": -1, "output_usd_per_million": 1},
    ],
)
def test_invalid_configuration(values):
    with pytest.raises(ValidationError):
        OpenAIConfig(**values)


def test_schema_is_strict_at_every_object():
    schema = plan_schema()

    def check(node):
        if isinstance(node, dict):
            assert "default" not in node and "prefixItems" not in node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for child in node.values():
                check(child)
        elif isinstance(node, list):
            for child in node:
                check(child)

    check(schema)


def test_mock_remains_free_and_independent_of_sdk():
    provider = MockProvider()
    assert provider.usage.calls == 0 and provider.usage.total_tokens == 0


@pytest.mark.parametrize("kind", ["valid", "invalid_json", "refusal", "rate_limit"])
def test_real_sdk_with_in_memory_http_transport(tmp_path, payload, kind):
    openai = pytest.importorskip("openai", reason="Install the optional openai extra")
    import httpx

    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        body = json.loads(request.content)
        assert body["text"]["format"]["strict"] is True
        if kind == "rate_limit":
            return httpx.Response(429, json={"error": {"message": "test rate limit"}})
        content = [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]
        if kind == "invalid_json":
            content[0]["text"] = "not JSON"
        elif kind == "refusal":
            content = [{"type": "refusal", "refusal": "Cannot provide a plan"}]
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "model": "test-model",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": content,
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with openai.OpenAI(
            api_key="test-placeholder", max_retries=0, http_client=http_client
        ) as client:
            agent, sandbox, _, provider = make_agent(
                tmp_path, client, budget=Budget(timeout_seconds=60)
            )
            report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert len(requests) == 1
    if kind == "valid":
        assert report.verified_success and report.model_tokens == 150
    else:
        assert report.failure == Failure.PLANNING and report.actions == 0
        assert sandbox.read_issue("ISSUE-1").status == Status.OPEN
        assert report.model_tokens == (None if kind == "rate_limit" else 150)


def test_environment_configuration_disables_retries_and_pins_endpoint(monkeypatch):
    openai = pytest.importorskip("openai", reason="Install the optional openai extra")
    captured = {}

    def constructor(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid")
    monkeypatch.setattr(openai, "OpenAI", constructor)
    OpenAIProvider.from_env(OpenAIConfig(model="test"))
    assert captured["max_retries"] == 0
    assert captured["base_url"] == "https://api.openai.com/v1"


def test_openai_smoke_records_one_request_and_actual_usage(tmp_path, payload):
    client = FakeClient(payload)
    provider = OpenAIProvider(OpenAIConfig(model="test-model"), client=client)
    result = smoke_test(tmp_path, provider)
    assert result["smoke_passed"]
    assert len(client.requests) == 1
    assert result["report"]["model_calls"] == 1
    assert result["report"]["model_tokens"] == 150
    assert result["report"]["model_usage"]["model"] == "test-model-snapshot"
    assert result["report"]["estimated_cost_usd"] is None


def test_openai_interpretation_is_metered_and_only_proposes(tmp_path):
    client = FakeClient(
        {"requirements": [{"issue_id": "ISSUE-1", "status": "done"}], "clarification": None}
    )
    provider = OpenAIProvider(OpenAIConfig(model="test-model"), client=client)
    result = propose_task("Please resolve ISSUE-1", provider, tmp_path)
    proposal = load_proposal(Path(result["proposal_file"]))
    assert proposal.task().requirements[0].status == "done"
    assert proposal.interpretation_usage.calls == 1
    assert proposal.interpretation_usage.total_tokens == 150
    assert proposal.interpretation_usage.estimated_cost_usd is None
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request["text"]["format"]["name"] == "issue_requirements"
    assert request["input"] == "Please resolve ISSUE-1"
    assert not list(tmp_path.glob("**/*.sqlite"))


@pytest.mark.parametrize(
    "response",
    [
        {"requirements": [{"issue_id": "ISSUE-999", "status": "done"}], "clarification": None},
        {"requirements": [{"issue_id": "ISSUE-1", "status": "deleted"}], "clarification": None},
        {
            "requirements": [{"issue_id": "ISSUE-1", "status": "done", "approved": True}],
            "clarification": None,
        },
        {
            "requirements": [{"issue_id": "ISSUE-1", "status": "done"}],
            "clarification": "Which issue?",
        },
        {"requirements": [], "clarification": None},
    ],
)
def test_invalid_interpretations_save_failure_usage(tmp_path, response):
    provider = OpenAIProvider(OpenAIConfig(model="test"), client=FakeClient(response))
    result = propose_task("Close ISSUE-1", provider, tmp_path)
    assert result["error"] == "interpretation_failed" and result["proposal_file"] is None
    assert result["model_usage"]["calls"] == 1
    assert result["model_usage"]["input_tokens"] == 100


def test_model_can_request_clarification_without_guessing(tmp_path):
    provider = OpenAIProvider(
        OpenAIConfig(model="test"),
        client=FakeClient(
            {"requirements": [], "clarification": "Which explicit issue ID should be closed?"}
        ),
    )
    result = propose_task("Close the issue", provider, tmp_path)
    assert result["error"] is None and result["needs_clarification"]
    assert result["model_usage"]["calls"] == 1


def test_real_sdk_interpretation_transport(tmp_path):
    openai = pytest.importorskip("openai", reason="Install the optional openai extra")
    import httpx

    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["text"]["format"]["name"] == "issue_requirements"
        text = json.dumps(
            {"requirements": [{"issue_id": "ISSUE-1", "status": "done"}], "clarification": None}
        )
        return httpx.Response(
            200,
            json={
                "id": "resp_intent",
                "object": "response",
                "created_at": 0,
                "model": "test-model",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_intent",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with openai.OpenAI(
            api_key="test-placeholder", max_retries=0, http_client=http_client
        ) as client:
            result = propose_task(
                "Finish ISSUE-1",
                OpenAIProvider(OpenAIConfig(model="test-model"), client=client),
                tmp_path,
                timeout=60,
            )
    assert result["error"] is None and not result["needs_clarification"]
    assert result["model_usage"]["input_tokens"] == 80
    assert len(requests) == 1
