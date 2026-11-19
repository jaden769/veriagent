import json
import math
import sys

import pytest

from veriagent.benchmark import proportion, repeated_trials, summarize
from veriagent.models import ProviderDiagnostic, Verification
from veriagent.openai_provider import ProviderError
from veriagent.planner import MockProvider


def test_wilson_reference_and_invalid_counts():
    assert proportion(5, 10)["wilson_95"] == pytest.approx([0.2365930905, 0.7634069095])
    assert proportion(0, 10)["wilson_95"][1] == pytest.approx(0.2775327999)
    assert proportion(10, 10)["wilson_95"][0] == pytest.approx(0.7224672001)
    for successes, count in [(0, 0), (-1, 10), (11, 10)]:
        with pytest.raises(ValueError):
            proportion(successes, count)


@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_repeats_have_fresh_state_and_expected_fault_outcomes(tmp_path, engine):
    result = repeated_trials(tmp_path, repeats=2, engine=engine)
    assert result["complete"] and result["completed_runs"] == 24
    assert len({r["run_id"] for r in result["runs"]}) == 24
    assert len({r["artifact"] for r in result["runs"]}) == 24
    groups = {(g["scenario"], g["mode"]): g for g in result["summary"]}
    assert groups["silent_drop", "baseline"]["false_success"]["count"] == 2
    assert groups["silent_drop", "verify"]["ground_truth_success"]["count"] == 0
    assert groups["silent_drop", "recover"]["recovered"]["count"] == 2
    assert groups["persistent_drop", "recover"]["ground_truth_success"]["count"] == 0
    assert groups["clean", "recover"]["ground_truth_success"]["count"] == 2
    assert all(not r["untargeted_changed"] for r in result["runs"])
    assert all(r["model_calls"] == 0 for r in result["runs"])
    assert [r["mode"] for r in result["runs"][:6]] == [
        "baseline",
        "verify",
        "recover",
        "verify",
        "recover",
        "baseline",
    ]
    from pathlib import Path

    directory = Path(result["directory"])
    saved = json.loads((directory / "benchmark.json").read_text())
    assert saved["complete"] and len(saved["source_sha256"]) > 10
    assert all((directory / r["artifact"] / "trace.json").exists() for r in result["runs"])


def test_final_oracle_does_not_trust_execution_verifier(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "veriagent.verification.StateVerifier.verify",
        lambda *a, **k: Verification(passed=True, evidence=()),
    )
    result = repeated_trials(tmp_path, repeats=1, scenarios=("silent_drop",))
    verify = next(r for r in result["runs"] if r["mode"] == "verify")
    assert verify["claimed_success"]
    assert not verify["ground_truth_success"]
    assert verify["false_success"]


def test_interrupted_benchmark_keeps_completed_evidence(tmp_path):
    count = 0

    def factory():
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("interrupted")
        return MockProvider()

    with pytest.raises(RuntimeError, match="interrupted"):
        repeated_trials(tmp_path, repeats=1, scenarios=("clean",), provider_factory=factory)
    saved = json.loads(next(tmp_path.glob("*/benchmark.json")).read_text())
    assert not saved["complete"]
    assert saved["completed_runs"] == 1 and len(saved["runs"]) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"repeats": 0},
        {"repeats": 20},
        {"scenarios": ()},
        {"scenarios": ("clean", "clean")},
        {"scenarios": ("unknown",)},
    ],
)
def test_invalid_selection_creates_no_artifacts(tmp_path, kwargs):
    with pytest.raises(ValueError):
        repeated_trials(tmp_path, **kwargs)
    assert not list(tmp_path.iterdir())


def test_cli_rejects_unbounded_live_before_constructing_provider(tmp_path, monkeypatch):
    from veriagent.cli import main

    monkeypatch.setattr(
        sys, "argv", ["veriagent", "benchmark", "--provider", "openai", "--output", str(tmp_path)]
    )
    monkeypatch.setattr(
        "veriagent.cli.configured_provider", lambda args: pytest.fail("must reject before provider")
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not list(tmp_path.iterdir())


def test_unknown_usage_is_not_summed_as_zero():
    rows = [
        dict(
            scenario="clean",
            mode="recover",
            ground_truth_success=True,
            false_success=False,
            recovered=False,
            untargeted_changed=False,
            model_calls=1,
            model_tokens=tokens,
            actions=1,
            elapsed_ms=1,
        )
        for tokens in (20, None)
    ]
    summary = summarize(rows)[0]
    assert summary["model_tokens"] is None
    assert summary["unknown_usage_runs"] == 1
    assert summary["model_calls"] == 2
    assert math.isfinite(summary["ground_truth_success"]["wilson_95"][0])


def test_provider_failure_stops_batch_and_closes_client(tmp_path):
    closed = []

    class FailedProvider(MockProvider):
        @property
        def diagnostic(self):
            return ProviderDiagnostic(category="rate_limit", http_status=429)

        def plan(self, *args, **kwargs):
            raise ProviderError("request failed")

        def close(self):
            closed.append(True)

    result = repeated_trials(tmp_path, repeats=2, provider_factory=FailedProvider)
    assert not result["complete"]
    assert result["stop_reason"] == "provider_diagnostic"
    assert result["completed_runs"] == 1
    assert closed == [True]
