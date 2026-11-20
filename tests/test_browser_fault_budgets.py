import pytest

from veriagent.browser_controls import compare_control, control_batch_specs


def drop_row(limit):
    passed = limit == 6
    return dict(
        task_id="pair_done",
        scenario="second_drop",
        mode="recover",
        max_retries=2,
        max_actions=limit,
        max_decisions=8,
        artifacts="saved",
        claimed_success=passed,
        audit_passed=passed,
        execution_passed=passed,
        failure=None if passed else "budget",
        actions=limit,
        decisions=limit,
        fault_exposed=True,
        recovery_attempts=int(limit >= 5),
        application_write_attempts=3 if passed else 2,
        commits=2 if passed else 1,
        pending_application_faults=0,
        injected_attempts=[2],
        planned_fault_attempt=2,
        events_dropped=0,
        untargeted_issues_unchanged=True,
        target_titles_unchanged=True,
        target_statuses={"ISSUE-1": "done", "ISSUE-2": "done" if passed else "open"},
        target_versions={"ISSUE-1": 1, "ISSUE-2": int(passed)},
    )


@pytest.mark.parametrize("limit", [4, 5, 6])
@pytest.mark.parametrize("resource", ["actions", "decisions"])
def test_drop_controls_distinguish_recovery_admission_from_completion(limit, resource):
    row = drop_row(limit)
    if resource == "decisions":
        row.update(max_actions=8, max_decisions=limit)
    assert compare_control(row)["passed"]


@pytest.mark.parametrize("limit", [4, 5, 6])
def test_confirmed_postcommit_error_needs_no_additional_budget_or_retry(limit):
    row = drop_row(6)
    row.update(
        scenario="second_lost_ack",
        max_actions=limit,
        actions=4,
        decisions=4,
        recovery_attempts=0,
        application_write_attempts=2,
    )
    assert compare_control(row)["passed"]
    replay = compare_control({**row, "application_write_attempts": 3, "recovery_attempts": 1})
    assert not replay["passed"]


def test_recovery_is_not_admitted_when_the_fault_consumes_final_action():
    row = drop_row(4)
    result = compare_control({**row, "recovery_attempts": 1})
    assert result["mismatches"]["recovery_attempts"] == {"expected": 0, "actual": 1}


def test_admitted_recovery_with_only_a_read_left_is_not_success():
    row = drop_row(5)
    result = compare_control({**row, "claimed_success": True, "execution_passed": True})
    assert not result["passed"]
    assert result["expected"]["target_versions"] == {"ISSUE-1": 1, "ISSUE-2": 0}


def test_fault_budget_matrix_has_unique_limits_and_conflicting_flags_fail():
    specs = control_batch_specs(fault_budget_boundaries=True)
    assert len(specs) == 6
    assert sum(len(s["tasks"]) * len(s["scenarios"]) for s in specs) == 24
    with pytest.raises(ValueError):
        control_batch_specs(budget_boundaries=True, fault_budget_boundaries=True)
