import json

import pytest
from pydantic import ValidationError

from veriagent.agent import Agent
from veriagent.budgeting import ModelBudgetExceeded, ModelBudgetLedger
from veriagent.cli import main
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.interpretation import propose_task
from veriagent.models import Budget, Failure, ModelLimits, ModelUsage
from veriagent.openai_provider import OpenAIConfig, OpenAIProvider
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def usage(*, inputs=100, outputs=50, cost=0.01):
    return ModelUsage(
        provider="openai",
        model="test-model",
        calls=1,
        input_tokens=inputs,
        output_tokens=outputs,
        estimated_cost_usd=cost,
    )


@pytest.mark.parametrize(
    "limits,reason",
    [
        (ModelLimits(max_total_tokens=0), "total_tokens_exhausted"),
        (ModelLimits(max_output_tokens=0), "output_allowance_insufficient"),
        (ModelLimits(max_cost_usd=0), "cost_threshold_reached"),
    ],
)
def test_zero_allowance_rejects_before_any_request(limits, reason):
    ledger = ModelBudgetLedger(limits, "test-model")
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.allowance(2048)
    assert ledger.state.usage.calls == 0
    assert ledger.state.stop_reason == reason


def test_output_allowance_caps_request_and_preserves_small_unusable_remainder():
    ledger = ModelBudgetLedger(ModelLimits(max_output_tokens=300), "test-model")
    assert ledger.allowance(2048) == 300
    ledger.record(usage(outputs=150))
    ledger.check_response()
    assert ledger.allowance(2048) == 150
    ledger.record(usage(outputs=50))
    with pytest.raises(ModelBudgetExceeded, match="output_allowance_insufficient"):
        ledger.allowance(2048)
    assert ledger.state.usage.output_tokens == 200


@pytest.mark.parametrize(
    "limits,entry,reason",
    [
        (ModelLimits(max_total_tokens=150), usage(), "total_tokens_exhausted"),
        (ModelLimits(max_cost_usd=0.01), usage(), "cost_threshold_reached"),
    ],
)
def test_exact_threshold_response_is_usable_but_another_request_is_not(limits, entry, reason):
    ledger = ModelBudgetLedger(limits, "test-model")
    ledger.record(entry)
    ledger.check_response()
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.allowance(2048)


@pytest.mark.parametrize(
    "limits,reason",
    [
        (ModelLimits(max_total_tokens=149), "total_tokens_exceeded"),
        (ModelLimits(max_output_tokens=49), "output_tokens_exceeded"),
        (ModelLimits(max_cost_usd=0.009), "cost_threshold_exceeded"),
    ],
)
def test_response_exceeding_observed_threshold_is_not_usable(limits, reason):
    ledger = ModelBudgetLedger(limits, "test-model")
    ledger.record(usage())
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.check_response()
    assert ledger.state.usage.calls == 1 and ledger.state.usage.total_tokens == 150


@pytest.mark.parametrize(
    "limits,reason",
    [
        (ModelLimits(max_total_tokens=1000), "token_usage_unknown"),
        (ModelLimits(max_output_tokens=1000), "output_usage_unknown"),
        (ModelLimits(max_cost_usd=1), "cost_usage_unknown"),
    ],
)
def test_unknown_usage_fails_closed_when_a_relevant_limit_is_active(limits, reason):
    ledger = ModelBudgetLedger(limits, "test-model")
    ledger.record(usage(inputs=None, outputs=None, cost=None))
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.check_response()
    with pytest.raises(ModelBudgetExceeded, match=reason):
        ledger.allowance(2048)


def test_unknown_usage_without_limits_remains_unknown_and_does_not_block():
    ledger = ModelBudgetLedger(ModelLimits(), "test-model")
    ledger.record(usage(inputs=None, outputs=None, cost=None))
    ledger.check_response()
    assert ledger.allowance(2048) == 2048
    assert ledger.state.usage.total_tokens is None


def test_reset_discards_prior_spend_and_stop_reason():
    ledger = ModelBudgetLedger(ModelLimits(max_total_tokens=150), "test-model")
    ledger.record(usage())
    with pytest.raises(ModelBudgetExceeded):
        ledger.allowance(2048)
    ledger.reset()
    assert ledger.allowance(2048) == 2048
    assert ledger.state.usage.calls == 0 and ledger.state.stop_reason is None


@pytest.mark.parametrize(
    "values",
    [
        {"max_total_tokens": -1},
        {"max_output_tokens": -1},
        {"max_cost_usd": -1},
        {"max_cost_usd": float("nan")},
        {"max_cost_usd": float("inf")},
    ],
)
def test_invalid_limits(values):
    with pytest.raises(ValidationError):
        ModelLimits(**values)


def test_cost_threshold_requires_caller_prices():
    with pytest.raises(ValidationError, match="requires"):
        OpenAIConfig(model="test-model", limits=ModelLimits(max_cost_usd=1))


class FakeResponses:
    def __init__(self, *, unknown=False):
        self.requests = []
        self.responses = self
        self.unknown = unknown

    def create(self, **request):
        from types import SimpleNamespace

        self.requests.append(request)
        return SimpleNamespace(
            status="completed",
            model="test-model",
            output_text=json.dumps(
                {
                    "steps": [
                        {
                            "id": "update",
                            "action": {
                                "tool": "set_status",
                                "issue_id": "ISSUE-1",
                                "status": "done",
                            },
                            "depends_on": [],
                            "expected": {"issue_id": "ISSUE-1", "status": "done"},
                        }
                    ]
                }
            ),
            usage=None if self.unknown else SimpleNamespace(input_tokens=100, output_tokens=50),
        )


def make_agent(tmp_path, provider, *, dynamic=False):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    traces = TraceStore(tmp_path / "traces.sqlite")
    agent_class = DynamicAgent if dynamic else Agent
    agent = agent_class(
        provider, Executor(sandbox), StateVerifier(sandbox.path), traces, Budget(timeout_seconds=60)
    )
    return sandbox, traces, agent


@pytest.mark.parametrize("dynamic", [False, True])
def test_engines_report_preflight_budget_failure_without_api_request(tmp_path, dynamic):
    client = FakeResponses()
    provider = OpenAIProvider(
        OpenAIConfig(model="test-model", limits=ModelLimits(max_total_tokens=0)), client=client
    )
    sandbox, traces, agent = make_agent(tmp_path, provider, dynamic=dynamic)
    report = agent.run(MockProvider().parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.BUDGET and not report.claimed_success
    assert report.model_calls == report.model_tokens == report.actions == 0
    assert client.requests == [] and sandbox.read_issue("ISSUE-1").status == "open"
    assert report.model_budget.stop_reason == "total_tokens_exhausted"
    assert "model_budget" in [e["kind"] for e in traces.events(report.run_id)]


def test_static_over_limit_response_is_metered_but_cannot_authorize_a_write(tmp_path):
    client = FakeResponses()
    provider = OpenAIProvider(
        OpenAIConfig(model="test-model", limits=ModelLimits(max_total_tokens=149)), client=client
    )
    sandbox, _, agent = make_agent(tmp_path, provider)
    report = agent.run(MockProvider().parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.BUDGET and report.actions == 0
    assert report.model_calls == 1 and report.model_tokens == 150
    assert report.model_budget.usage.total_tokens == 150
    assert sandbox.read_issue("ISSUE-1").status == "open"


def test_exact_static_limit_can_finish_and_next_run_starts_fresh(tmp_path):
    client = FakeResponses()
    provider = OpenAIProvider(
        OpenAIConfig(model="test-model", limits=ModelLimits(max_total_tokens=150)), client=client
    )
    _, _, agent = make_agent(tmp_path, provider)
    task = MockProvider().parse("Set ISSUE-1 to done")
    for _ in range(2):
        report = agent.run(task)
        assert report.verified_success and report.model_budget.usage.calls == 1
        assert report.model_budget.stop_reason is None
    assert len(client.requests) == 2


def test_missing_usage_rejects_an_otherwise_valid_plan_when_limited(tmp_path):
    client = FakeResponses(unknown=True)
    provider = OpenAIProvider(
        OpenAIConfig(model="test-model", limits=ModelLimits(max_total_tokens=1000)), client=client
    )
    sandbox, _, agent = make_agent(tmp_path, provider)
    report = agent.run(MockProvider().parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.BUDGET and report.actions == 0
    assert report.model_budget.stop_reason == "token_usage_unknown"
    assert report.model_tokens is None and len(client.requests) == 1
    assert sandbox.read_issue("ISSUE-1").status == "open"


def test_interpretation_budget_block_saves_an_honest_zero_call_result(tmp_path):
    client = FakeResponses()
    provider = OpenAIProvider(
        OpenAIConfig(model="test-model", limits=ModelLimits(max_output_tokens=0)), client=client
    )
    result = propose_task("Close ISSUE-1", provider, tmp_path)
    assert result["error"] == "model_budget_exhausted" and result["proposal_file"] is None
    assert result["model_usage"]["calls"] == 0 and client.requests == []
    assert result["model_budget"]["stop_reason"] == "output_allowance_insufficient"


def test_mock_cli_rejects_model_limits_instead_of_pretending_to_enforce_them(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "propose",
            "Close ISSUE-1",
            "--max-model-tokens",
            "1000",
            "--output",
            str(tmp_path / "new"),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "require --provider openai" in capsys.readouterr().err
    assert not (tmp_path / "new").exists()


def test_cost_threshold_cli_validates_prices_before_creating_provider(monkeypatch, capsys):
    def forbidden(*args):
        pytest.fail("Invalid cost settings must stop before client construction")

    monkeypatch.setattr("veriagent.cli.OpenAIProvider.from_env", forbidden)
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "run",
            "Set ISSUE-1 to done",
            "--provider",
            "openai",
            "--model",
            "test-model",
            "--max-model-cost",
            "1",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "requires both caller-supplied token prices" in capsys.readouterr().err


def test_denied_request_does_not_erase_the_actual_response_model():
    from veriagent.dynamic import add_usage

    observed = ModelUsage(
        provider="openai", model="actual-snapshot", calls=1, input_tokens=100, output_tokens=50
    )
    denied = ModelUsage(provider="openai", model="requested-alias", calls=0)
    assert add_usage(observed, denied) == observed
