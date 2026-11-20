import pytest

from veriagent.browser_controls import compare_control, control_batch_specs


def already_row():
    return dict(
        task_id="already_satisfied",
        scenario="second_drop",
        mode="recover",
        max_retries=2,
        max_actions=1,
        max_decisions=8,
        artifacts="saved",
        claimed_success=True,
        audit_passed=True,
        execution_passed=True,
        failure=None,
        actions=0,
        decisions=0,
        fault_exposed=False,
        recovery_attempts=0,
        application_write_attempts=0,
        commits=0,
        pending_application_faults=1,
        planned_fault_attempt=2,
        injected_attempts=[],
        events_dropped=0,
        untargeted_issues_unchanged=True,
        target_titles_unchanged=True,
        target_statuses={"ISSUE-1": "done"},
        target_versions={"ISSUE-1": 0},
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("actions", 1),
        ("commits", 1),
        ("target_versions", {"ISSUE-1": 1}),
        ("fault_exposed", True),
        ("pending_application_faults", 0),
    ],
)
def test_satisfied_goal_must_not_write_or_claim_unused_fault_exposure(field, value):
    row = already_row()
    assert compare_control(row)["passed"]
    assert field in compare_control({**row, field: value})["mismatches"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("claimed_success", True),
        ("recovery_attempts", 1),
        ("target_versions", {"ISSUE-1": 1, "ISSUE-2": 0}),
    ],
)
def test_partial_goal_with_one_step_retains_seeded_progress_and_fails_honestly(field, value):
    row = already_row() | dict(
        task_id="partial_satisfied",
        claimed_success=False,
        audit_passed=False,
        execution_passed=False,
        failure="budget",
        actions=1,
        decisions=1,
        target_statuses={"ISSUE-1": "done", "ISSUE-2": "open"},
        target_versions={"ISSUE-1": 0, "ISSUE-2": 0},
    )
    assert compare_control(row)["passed"]
    assert field in compare_control({**row, field: value})["mismatches"]


@pytest.mark.parametrize("resource", ["actions", "decisions"])
def test_partial_goal_completes_with_one_write_and_leaves_second_write_fault_unused(resource):
    row = already_row() | dict(
        task_id="partial_satisfied",
        max_actions=2,
        actions=2,
        decisions=2,
        application_write_attempts=1,
        commits=1,
        target_statuses={"ISSUE-1": "done", "ISSUE-2": "done"},
        target_versions={"ISSUE-1": 0, "ISSUE-2": 1},
    )
    if resource == "decisions":
        row.update(max_actions=8, max_decisions=2)
    assert compare_control(row)["passed"]


def test_satisfied_budget_matrix_is_bounded_and_exclusive():
    specs = control_batch_specs(satisfied_budget_boundaries=True)
    assert len(specs) == 4
    assert sum(len(s["tasks"]) * len(s["scenarios"]) for s in specs) == 16
    with pytest.raises(ValueError):
        control_batch_specs(fault_budget_boundaries=True, satisfied_budget_boundaries=True)
