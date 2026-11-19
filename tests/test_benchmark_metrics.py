import pytest

from veriagent.benchmark import (
    conditional_proportion,
    fault_recovery_eligible,
    repeated_trials,
    summarize,
)
from veriagent.benchmark_cases import load_corpus


def test_no_claims_are_undefined_not_perfect_success():
    assert conditional_proportion(0, 0) == {
        "count": 0,
        "trials": 0,
        "rate": None,
        "wilson_95": None,
    }
    with pytest.raises(ValueError):
        conditional_proportion(1, 0)


def test_conditional_denominators_differ_from_all_runs():
    base = dict(
        task_id="single_done",
        scenario="silent_drop",
        mode="recover",
        model_calls=0,
        model_tokens=0,
        actions=1,
        elapsed_ms=1,
        untargeted_changed=False,
    )
    rows = [
        {
            **base,
            "claimed_success": True,
            "ground_truth_success": False,
            "false_success": True,
            "recovered": False,
            "fault_recovery_eligible": True,
        },
        {
            **base,
            "claimed_success": False,
            "ground_truth_success": False,
            "false_success": False,
            "recovered": False,
            "fault_recovery_eligible": False,
        },
        {
            **base,
            "claimed_success": True,
            "ground_truth_success": True,
            "false_success": False,
            "recovered": True,
            "fault_recovery_eligible": True,
        },
        {
            **base,
            "claimed_success": True,
            "ground_truth_success": True,
            "false_success": False,
            "recovered": False,
            "fault_recovery_eligible": False,
        },
    ]
    result = summarize(rows)[0]
    assert result["false_success"]["rate"] == 0.25
    assert result["false_success_given_claim"]["rate"] == pytest.approx(1 / 3)
    assert result["false_success_given_claim"]["trials"] == 3
    assert result["recovered"]["rate"] == 0.25
    assert result["recovery_given_fault_mismatch"]["rate"] == 0.5
    assert result["recovery_given_fault_mismatch"]["trials"] == 2


def test_eligibility_requires_injected_unmet_authorized_write():
    task = load_corpus()[0].cases[0].task
    valid = dict(
        injected_fault="silent_drop", issue_id="ISSUE-1", status="done", status_before_fault="open"
    )
    assert fault_recovery_eligible(task, [valid])
    for change in [
        {"injected_fault": None},
        {"issue_id": "ISSUE-2"},
        {"status": "open"},
        {"status_before_fault": None},
        {"status_before_fault": "done"},
    ]:
        assert not fault_recovery_eligible(task, [{**valid, **change}])


def test_noop_fault_delivery_does_not_create_recovery_opportunity(tmp_path):
    result = repeated_trials(
        tmp_path, repeats=1, scenarios=("silent_drop",), task_ids=("already_satisfied",)
    )
    assert any(r["write_attempts"] for r in result["runs"])
    assert all(not r["fault_recovery_eligible"] for r in result["runs"])
    assert all(g["recovery_given_fault_mismatch"]["rate"] is None for g in result["summary"])
    assert all(g["injected_faults"] == 1 for g in result["summary"])


def test_dropped_required_write_has_measured_recovery_denominator(tmp_path):
    result = repeated_trials(
        tmp_path, repeats=1, scenarios=("second_drop",), task_ids=("pair_done",), engine="dynamic"
    )
    assert all(r["fault_recovery_eligible"] for r in result["runs"])
    recover = next(g for g in result["summary"] if g["mode"] == "recover")
    assert recover["recovery_given_fault_mismatch"]["rate"] == 1
    verify = next(g for g in result["summary"] if g["mode"] == "verify")
    assert verify["false_success_given_claim"]["rate"] is None
    assert verify["recovery_given_fault_mismatch"]["rate"] == 0
