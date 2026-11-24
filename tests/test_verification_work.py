import copy

import pytest

from veriagent.models import Action, Observation, RunReport
from veriagent.verification_work import verification_work


def trace(*, error=False, action=False):
    check = {
        "passed": True,
        "evidence": [
            {
                "issue_id": "ISSUE-1",
                "expected": "done",
                "actual": "done",
                "version": 1,
                "source": "sqlite_read_only",
            }
        ],
        "failure": None,
    }
    events = [
        (
            "task",
            {
                "objective": "Set ISSUE-1 to done",
                "requirements": [{"issue_id": "ISSUE-1", "status": "done"}],
            },
        ),
        ("verification", check),
    ]
    if error:
        events.append(("verification_error", {"failure": "internal"}))
    if action:
        tool = Action(tool="read_issue", issue_id="ISSUE-1")
        events.extend(
            [
                ("decision_context", {}),
                ("action", tool.model_dump(mode="json")),
                (
                    "observation",
                    Observation(action=tool, reported_success=True).model_dump(mode="json"),
                ),
                ("recovery", {"attempt": 1}),
            ]
        )
    report = RunReport(
        run_id="run",
        mode="recover",
        claimed_success=not error,
        verified_success=None if error else True,
        actions=int(action),
        decisions=int(action),
        recovery_attempts=int(action),
        elapsed_ms=0,
        engine="dynamic",
        failure="internal" if error else None,
    )
    events.append(("report", report.model_dump(mode="json")))
    return [
        {"seq": i, "kind": kind, "payload": payload} for i, (kind, payload) in enumerate(events, 1)
    ]


def test_completed_reads_and_action_units_stay_separate():
    events = trace(action=True)
    before = copy.deepcopy(events)
    ledger = verification_work(events, expected_run_id="run")
    assert ledger["tool_actions"] == ledger["tool_reads"] == ledger["decisions"] == 1
    assert ledger["tool_writes"] == 0
    assert ledger["completed_verification_calls"] == ledger["verified_target_rows"] == 1
    assert ledger["recovery_admissions"] == 1
    assert ledger["verification_work_complete"] and events == before


def test_error_keeps_known_rows_but_total_work_unknown():
    ledger = verification_work(trace(error=True), expected_run_id="run")
    assert ledger["known_verified_target_rows"] == 1
    assert ledger["verified_target_rows"] is None
    assert ledger["observed_verification_attempts"] == 2
    assert ledger["verification_errors"] == 1 and not ledger["verification_work_complete"]


def test_error_without_completed_check_does_not_become_zero_total():
    events = trace(error=True)
    del events[1]
    for sequence, event in enumerate(events, 1):
        event["seq"] = sequence
    ledger = verification_work(events, expected_run_id="run")
    assert ledger["known_verified_target_rows"] == 0
    assert ledger["verified_target_rows"] is None


def test_final_evaluator_work_is_excluded():
    events = trace()
    events.append({"seq": 4, "kind": "benchmark_audit", "payload": {"final_state": []}})
    assert verification_work(events, expected_run_id="run")["completed_verification_calls"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "gap",
        "boolean_seq",
        "missing_report",
        "wrong_run",
        "counter",
        "task",
        "duplicate_evidence",
        "false_pass",
        "late_event",
        "unmatched_action",
        "error_record",
    ],
)
def test_inconsistent_or_incomplete_traces_are_rejected(mutation):
    events = trace()
    if mutation == "gap":
        events[1]["seq"] = 3
    elif mutation == "boolean_seq":
        events[0]["seq"] = True
    elif mutation == "missing_report":
        events.pop()
    elif mutation == "wrong_run":
        events[-1]["payload"]["run_id"] = "other"
    elif mutation == "counter":
        events[-1]["payload"]["actions"] = 1
    elif mutation == "task":
        events[1]["payload"]["evidence"][0]["expected"] = "open"
    elif mutation == "duplicate_evidence":
        events[1]["payload"]["evidence"] *= 2
    elif mutation == "false_pass":
        events[1]["payload"]["passed"] = False
    elif mutation == "late_event":
        events.append({"seq": 4, "kind": "verification", "payload": events[1]["payload"]})
    elif mutation == "unmatched_action":
        events = trace(action=True)
        events[4]["payload"]["action"]["issue_id"] = "ISSUE-2"
    else:
        events = trace(error=True)
        events[2]["payload"] = {}
    with pytest.raises(ValueError):
        verification_work(events, expected_run_id="run")


def test_size_limit_and_absent_trace(monkeypatch):
    with pytest.raises(ValueError):
        verification_work([], expected_run_id="run")
    monkeypatch.setattr("veriagent.verification_work.MAX_EVENTS", 1)
    with pytest.raises(ValueError):
        verification_work(trace(), expected_run_id="run")
