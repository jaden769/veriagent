import pytest

from veriagent.browser_controls import compare_control, control_batch_specs, expected_control
from veriagent.browser_review import render_control_review, summarize_control_audit


def boundary_row(**changes):
    return (
        dict(
            task_id="pair_done",
            scenario="clean",
            mode="recover",
            max_retries=2,
            max_actions=2,
            max_decisions=8,
            artifacts="saved",
            claimed_success=False,
            audit_passed=False,
            execution_passed=False,
            failure="budget",
            actions=2,
            decisions=2,
            fault_exposed=False,
            recovery_attempts=0,
            application_write_attempts=1,
            commits=1,
            pending_application_faults=0,
            injected_attempts=[],
            events_dropped=0,
            untargeted_issues_unchanged=True,
            target_titles_unchanged=True,
            target_statuses={"ISSUE-1": "done", "ISSUE-2": "open"},
            target_versions={"ISSUE-1": 1, "ISSUE-2": 0},
        )
        | changes
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("actions", 3),
        ("decisions", 3),
        ("failure", None),
        ("claimed_success", True),
        ("target_versions", {"ISSUE-1": 0, "ISSUE-2": 0}),
    ],
)
def test_budget_controls_reject_overrun_false_claim_or_lost_progress(field, value):
    assert compare_control(boundary_row())["passed"]
    result = compare_control(boundary_row(**{field: value}))
    assert not result["passed"] and field in result["mismatches"]


def test_action_and_decision_limits_have_distinct_control_identities():
    specs = control_batch_specs(budget_boundaries=True)
    assert len(specs) == 6
    assert {(s["max_actions"], s["max_decisions"]) for s in specs} == {
        (2, 8),
        (3, 8),
        (4, 8),
        (8, 2),
        (8, 3),
        (8, 4),
    }
    action = compare_control(boundary_row())
    decision = compare_control(boundary_row(max_actions=8, max_decisions=2))
    assert action["passed"] and decision["passed"]
    assert (action["max_actions"], action["max_decisions"]) != (
        decision["max_actions"],
        decision["max_decisions"],
    )


def test_exact_completion_boundary_requires_success_without_budget_failure():
    expected = expected_control("mixed_status", "clean", "recover", 2, 8, 4)
    assert expected["failure"] is None and expected["execution_passed"]
    assert expected["actions"] == expected["decisions"] == 4
    assert expected["target_statuses"] == {"ISSUE-1": "done", "ISSUE-2": "in_progress"}


def test_budget_matrix_flags_are_mutually_exclusive():
    with pytest.raises(ValueError):
        control_batch_specs(indexed=True, budget_boundaries=True)


def test_review_shows_limits_for_expected_budget_failure():
    row = {
        **compare_control(boundary_row()),
        "batch_directory": "a" * 32,
        "bundle_directory": "trial-001/" + "b" * 32,
    }
    audit = dict(
        evidence_passed=True,
        controls_passed=True,
        checks=[],
        controls=[row],
        batches=[
            dict(
                directory="a" * 32,
                checks=[],
                trials=[
                    dict(bundle_directory=row["bundle_directory"], task_passed=False, checks=[])
                ],
            )
        ],
    )
    text = render_control_review(summarize_control_audit(audit))
    assert "Limits: actions=2, decisions=8" in text
