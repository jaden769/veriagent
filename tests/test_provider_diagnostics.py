import json

import pytest

from veriagent.agent import Agent
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget, Failure, ModelLimits
from veriagent.openai_provider import (
    OpenAIConfig,
    OpenAIProvider,
    ProviderError,
    request_diagnostic,
)
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


@pytest.mark.parametrize(
    "status,code,category",
    [
        (401, "invalid_api_key", "authentication"),
        (403, None, "permission"),
        (429, "insufficient_quota", "rate_limit"),
        (400, "invalid_json_schema", "api_status"),
        (404, "model_not_found", "api_status"),
    ],
)
@pytest.mark.parametrize("engine", [Agent, DynamicAgent], ids=["static", "dynamic"])
def test_request_failure_survives_budget_guard_without_leaking_secrets(
    tmp_path, status, code, category, engine
):
    openai = pytest.importorskip("openai")
    import httpx

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={
                "error": {
                    "message": "SECRET-KEY-MUST-NOT-APPEAR",
                    "code": code,
                    "type": "invalid_request_error",
                    "param": None,
                }
            },
        )

    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    traces = TraceStore(tmp_path / "traces.sqlite")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with openai.OpenAI(
            api_key="test-placeholder", http_client=http_client, max_retries=0
        ) as client:
            provider = OpenAIProvider(
                OpenAIConfig(model="test-model", limits=ModelLimits(max_output_tokens=2048)),
                client=client,
            )
            report = engine(
                provider,
                Executor(sandbox),
                StateVerifier(sandbox.path),
                traces,
                Budget(timeout_seconds=60),
            ).run(MockProvider().parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.PLANNING and report.actions == 0
    assert report.model_calls == len(requests) == 1 and report.model_tokens is None
    assert report.model_budget.stop_reason == "output_usage_unknown"
    assert report.provider_diagnostic.category == category
    assert report.provider_diagnostic.http_status == status
    assert report.provider_diagnostic.api_code == code
    if status == 400:
        assert report.provider_diagnostic.detail is not None
    else:
        assert report.provider_diagnostic.detail is None
    assert "SECRET-KEY-MUST-NOT-APPEAR" not in traces.render(report.run_id)
    assert any(e["kind"] == "provider_diagnostic" for e in traces.events(report.run_id))


def test_unknown_error_codes_and_messages_are_never_copied():
    class UntrustedError(Exception):
        status_code = 400
        code = "SECRET-UNTRUSTED-CODE"

    diagnostic = request_diagnostic(UntrustedError("SECRET-MESSAGE"))
    assert diagnostic.http_status == 400 and diagnostic.api_code is None
    assert "SECRET" not in diagnostic.model_dump_json()


@pytest.mark.parametrize(
    "error,category",
    [
        (TimeoutError("SECRET"), "timeout"),
        (ConnectionError("SECRET"), "connection"),
        (ValueError("SECRET"), "response_validation"),
    ],
)
def test_local_failure_categories_only_use_safe_metadata(error, category):
    diagnostic = request_diagnostic(error)
    assert diagnostic.category == category
    assert "SECRET" not in json.dumps(diagnostic.model_dump())


def test_bad_request_details_preserve_schema_context_but_redact_credentials_and_values():
    class BadRequest(Exception):
        status_code = 400
        code = None
        param = "text.format.schema"
        body = {
            "error": {
                "message": (
                    "Invalid schema: 'additionalProperties' must be false. "
                    "Rejected value 'private-user-value'. sk-proj-secretcredential123456789 "
                    "Bearer hiddencredential key_anothersecret short-key user@example.com\n"
                )
            }
        }

    diagnostic = request_diagnostic(BadRequest(), "short-key")
    assert diagnostic.api_parameter == "text.format.schema"
    assert "additionalProperties" in diagnostic.detail
    for secret in (
        "private-user-value",
        "secretcredential",
        "hiddencredential",
        "anothersecret",
        "short-key",
        "user@example.com",
    ):
        assert secret not in diagnostic.detail
    assert "\n" not in diagnostic.detail and len(diagnostic.detail) <= 400


def test_non_400_error_does_not_copy_message_or_unknown_parameter():
    class AuthenticationError(Exception):
        status_code = 401
        code = "invalid_api_key"
        param = "SECRET-PARAMETER"
        body = {"message": "SECRET-MESSAGE"}

    diagnostic = request_diagnostic(AuthenticationError())
    assert diagnostic.api_parameter is None and diagnostic.detail is None
    assert "SECRET" not in diagnostic.model_dump_json()


@pytest.mark.parametrize(
    "kind,body,expected,body_format",
    [
        ("text", "Unsupported model 'private-model-id'.", "Unsupported model", "text"),
        ("json", {"detail": "Invalid parameter 'model'."}, "Invalid parameter", "json"),
        ("json", {"error": "Unsupported request format."}, "Unsupported request format", "text"),
        ("empty", "", "Error code: 400", "empty"),
    ],
)
def test_real_sdk_nonstandard_bad_request_body_shapes(kind, body, expected, body_format):
    openai = pytest.importorskip("openai")
    import httpx

    def handler(request):
        if kind == "json":
            return httpx.Response(400, json=body)
        return httpx.Response(400, text=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with openai.OpenAI(
            api_key="test-placeholder", max_retries=0, http_client=http_client
        ) as client:
            provider = OpenAIProvider(OpenAIConfig(model="test-model"), client=client)
            with pytest.raises(ProviderError):
                provider.plan(MockProvider().parse("Set ISSUE-1 to done"))
            assert expected in provider.diagnostic.detail
            assert provider.diagnostic.body_format == body_format
            assert "private-model-id" not in provider.diagnostic.detail


@pytest.mark.parametrize("status", [200, 400, 401, 404])
def test_model_check_only_gets_metadata(status):
    openai = pytest.importorskip("openai")
    import httpx

    requests = []

    def handler(request):
        requests.append(request)
        if status == 200:
            return httpx.Response(
                200, json={"id": "test-model", "object": "model", "created": 0, "owned_by": "test"}
            )
        return httpx.Response(status, content=b"")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with openai.OpenAI(api_key="test-secret", http_client=http_client, max_retries=0) as client:
            provider = OpenAIProvider(OpenAIConfig(model="test-model"), client=client)
            result = provider.check_model()
    assert result["ok"] is (status == 200)
    assert result["generation_requests"] == 0
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/v1/models/test-model"
    assert "test-secret" not in json.dumps(result)
    if status != 200:
        assert result["diagnostic"]["http_status"] == status
    if status == 400:
        assert result["diagnostic"]["body_format"] == "empty"
