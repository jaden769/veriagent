import json

import pytest

from veriagent.browser_controls import compare_control, evaluate_browser_controls


def row(**overrides):
    return {
        "task_id": "single_done",
        "scenario": "silent_drop",
        "mode": "recover",
        "artifacts": "evidence",
        "fault_exposed": True,
        "claimed_success": True,
        "audit_passed": True,
        "execution_passed": True,
        "recovery_attempts": 1,
        "commits": 1,
        "application_write_attempts": 2,
        "events_dropped": 0,
        **overrides,
    }


def fake_batch(directory, trials):
    path = directory / ("a" * 32)
    path.mkdir(exist_ok=True)
    (path / "manifest.json").write_text(json.dumps({"trials": trials}), encoding="utf-8")
    return {"artifacts": str(path), "trials": trials}


@pytest.mark.parametrize(
    "field,value",
    [
        ("audit_passed", False),
        ("commits", 2),
        ("fault_exposed", False),
        ("recovery_attempts", 0),
        ("events_dropped", 1),
    ],
)
def test_weakened_control_is_reported_as_mismatch(field, value):
    result = compare_control(row(**{field: value}))
    assert not result["passed"]
    assert result["mismatches"][field]["actual"] == value


def test_expected_baseline_false_claim_passes_control_without_passing_task():
    result = compare_control(
        row(
            mode="baseline",
            audit_passed=False,
            execution_passed=False,
            recovery_attempts=0,
            commits=0,
            application_write_attempts=1,
        )
    )
    assert result["passed"]
    assert result["expected"]["audit_passed"] is False


def test_already_satisfied_has_no_fault_exposure_or_writes():
    result = compare_control(
        row(
            task_id="already_satisfied",
            fault_exposed=False,
            recovery_attempts=0,
            commits=0,
            application_write_attempts=0,
        )
    )
    assert result["passed"]


def test_missing_evidence_fails_closed():
    evidence = row()
    del evidence["events_dropped"]
    assert not compare_control(evidence)["passed"]


def test_interrupted_evaluation_retains_completed_controls(tmp_path, monkeypatch):
    calls = []

    def batch(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise KeyboardInterrupt()
        return fake_batch(args[0], [row()])

    monkeypatch.setattr("veriagent.browser_controls.browser_batch", batch)
    with pytest.raises(KeyboardInterrupt):
        evaluate_browser_controls(tmp_path)
    result = json.loads(next(tmp_path.glob("*/controls.json")).read_text())
    assert result["status"] == "interrupted" and not result["passed"]
    assert len(result["controls"]) == 1 and len(result["batches"]) == 1
    assert result["batches"][0].endswith("a" * 32)


@pytest.mark.parametrize("duplicates", [1, 21])
def test_incomplete_matrix_cannot_pass(tmp_path, monkeypatch, duplicates):
    monkeypatch.setattr(
        "veriagent.browser_controls.browser_batch",
        lambda *args, **kwargs: fake_batch(args[0], [row()] * duplicates),
    )
    result = evaluate_browser_controls(tmp_path)
    assert result["status"] == "complete" and not result["passed"]
