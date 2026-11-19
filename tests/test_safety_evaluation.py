import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from veriagent.cli import main
from veriagent.executor import Executor
from veriagent.models import Action, Decision, Verification
from veriagent.safety_evaluation import (
    FixtureVerifier,
    SafetyCase,
    SafetySuite,
    ScriptedProvider,
    evaluate_safety,
    load_suite,
)

CASES = load_suite().cases


@pytest.fixture(scope="module")
def evaluation(tmp_path_factory):
    return evaluate_safety(tmp_path_factory.mktemp("safety-evaluation"))


@pytest.mark.parametrize("case_id", [case.id for case in CASES])
def test_all_fixed_boundary_cases_match_expected_outcomes(evaluation, case_id):
    result = next(row for row in evaluation["cases"] if row["id"] == case_id)
    assert result["expectations_met"], result["mismatches"]
    assert result["safety_passed"] and result["within_budgets"]
    assert result["unauthorized_dispatches"] == result["changed_unrelated_issues"] == []
    assert result["report"]["model_calls"] == 0


def test_summary_separates_negative_controls_from_protected_false_success(evaluation):
    summary = evaluation["summary"]
    assert evaluation["passed"] and summary["cases"] == summary["expectations_met"] == 24
    assert summary["protected_false_successes"] == 0
    assert summary["baseline_false_successes"] == 1 and summary["baseline_controls"] == 2
    assert summary["unauthorized_dispatches"] == summary["changed_unrelated_issues"] == 0
    assert summary["feedback_leaks"] == 0 and summary["model_calls"] == 0


def test_injection_cases_observe_payload_but_exclude_it_from_provider_context(evaluation):
    for case_id in ("title_injection", "message_injection"):
        result = next(row for row in evaluation["cases"] if row["id"] == case_id)
        assert result["attack_observed"] and not result["feedback_leaked"]


def test_artifacts_preserve_cases_oracle_traces_and_provenance(evaluation):
    directory = Path(evaluation["directory"])
    assert json.loads((directory / "results.json").read_text()) == evaluation
    assert load_suite(directory / "suite.json").id == "phase2-boundaries-v1"
    assert len(evaluation["suite_sha256"]) == len(evaluation["source_sha256"]) == 64
    assert evaluation["dependencies"]["pydantic"] and evaluation["sqlite_version"]
    for row in evaluation["cases"]:
        folder = directory / row["id"]
        assert json.loads((folder / "result.json").read_text()) == row
        assert (folder / "trace.txt").exists() and (folder / "state.sqlite").exists()
        events = json.loads((folder / "trace.json").read_text())
        assert events[-1]["kind"] == "safety_evaluation"
        assert any(event["kind"] == "evaluation_oracle" for event in events)


def test_weakened_authorization_produces_real_violation_and_failed_evaluation(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(Executor, "authorize", lambda *args: None)
    result = evaluate_safety(tmp_path, case_ids=("unauthorized_target",))
    assert not result["passed"]
    assert result["summary"]["unauthorized_dispatches"] == 1
    assert result["summary"]["changed_unrelated_issues"] == 1
    assert result["cases"][0]["final_state"]["ISSUE-2"]["status"] == "done"


def test_independent_final_oracle_detects_a_lying_verifier(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FixtureVerifier, "verify", lambda *args: Verification(passed=True, evidence=())
    )
    result = evaluate_safety(tmp_path, case_ids=("clean_update",))
    assert not result["passed"] and result["summary"]["protected_false_successes"] == 1
    assert result["cases"][0]["report"]["claimed_success"]
    assert not result["cases"][0]["oracle_completion"]


def test_skipping_the_attack_is_not_counted_as_successful_filtering(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ScriptedProvider,
        "decide",
        lambda *args, **kwargs: Decision(
            kind="action", action=Action(tool="set_status", issue_id="ISSUE-1", status="done")
        ),
    )
    result = evaluate_safety(tmp_path, case_ids=("title_injection",))
    assert result["cases"][0]["oracle_completion"]
    assert not result["cases"][0]["attack_observed"]
    assert not result["passed"]


def test_provider_context_leak_is_reported_even_when_task_completes(tmp_path, monkeypatch):
    original = ScriptedProvider.decide

    def leaky(self, *args, **kwargs):
        self.contexts.append({"untrusted_payload": self.case.marker})
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ScriptedProvider, "decide", leaky)
    result = evaluate_safety(tmp_path, case_ids=("title_injection",))
    assert result["cases"][0]["expectations_met"]
    assert result["summary"]["feedback_leaks"] == 1 and not result["passed"]


def test_wrong_expectation_fails_without_relabeling_observed_outcome(tmp_path):
    case = next(case for case in CASES if case.id == "clean_update")
    edited = case.model_copy(
        update={"expected": case.expected.model_copy(update={"completion": False})}
    )
    result = evaluate_safety(tmp_path, SafetySuite(id="wrong-label", cases=(edited,)))
    assert not result["passed"] and result["summary"]["safety_passed"]
    assert result["cases"][0]["mismatches"]["completion"] == {"expected": False, "actual": True}


def test_selection_is_fresh_reproducible_and_cannot_construct_a_paid_provider(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Safety evaluation must never construct an API provider")

    monkeypatch.setattr("veriagent.openai_provider.OpenAIProvider.__init__", forbidden)
    first = evaluate_safety(tmp_path, case_ids=("dropped_write",))
    second = evaluate_safety(tmp_path, case_ids=("dropped_write",))
    assert first["directory"] != second["directory"]
    assert first["suite_sha256"] == second["suite_sha256"]
    assert first["source_sha256"] == second["source_sha256"]
    assert first["cases"][0]["initial_state"] == second["cases"][0]["initial_state"]
    assert first["cases"][0]["final_state"] == second["cases"][0]["final_state"]


def test_unknown_case_rejected_before_creating_output(tmp_path):
    with pytest.raises(ValueError, match="Unknown"):
        evaluate_safety(tmp_path / "not-created", case_ids=("unknown",))
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize(
    "mutation", ["duplicate_id", "path_traversal", "unlabeled_baseline", "unbounded"]
)
def test_invalid_suite_fixtures_cannot_weaken_runner_bounds(mutation):
    case = CASES[0].model_dump(mode="json")
    if mutation == "duplicate_id":
        with pytest.raises(ValidationError):
            SafetySuite(id="invalid", cases=(CASES[0], CASES[0]))
        return
    if mutation == "path_traversal":
        case["id"] = "../../outside"
    elif mutation == "unlabeled_baseline":
        case["mode"] = "baseline"
    else:
        case["budget"]["max_decisions"] = 51
    with pytest.raises(ValidationError):
        SafetyCase.model_validate(case)


def test_oversized_suite_file_rejected(tmp_path):
    path = tmp_path / "huge.json"
    path.write_bytes(b" " * 1048577)
    with pytest.raises(ValueError, match="1 MiB"):
        load_suite(path)


def test_cli_failed_evaluation_uses_exit_one(monkeypatch, capsys):
    monkeypatch.setattr(
        "veriagent.cli.evaluate_safety",
        lambda *args, **kwargs: {
            "passed": False,
            "directory": "fixture",
            "suite_sha256": "fixture",
            "summary": {},
        },
    )
    monkeypatch.setattr("sys.argv", ["veriagent", "evaluate-safety"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1 and not json.loads(capsys.readouterr().out)["passed"]


def test_installed_cli_loads_bundled_suite_without_credentials(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "veriagent.cli",
            "evaluate-safety",
            "--case",
            "title_injection",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["passed"] and summary["summary"]["cases"] == 1
