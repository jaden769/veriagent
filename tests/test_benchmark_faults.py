import pytest

from veriagent.benchmark import repeated_trials
from veriagent.benchmark_faults import ScheduledSandbox, WriteFault
from veriagent.models import Status
from veriagent.sandbox import Faults, TransientError


def test_reads_do_not_advance_schedule_and_second_write_is_dropped(tmp_path):
    sandbox = ScheduledSandbox(
        tmp_path / "state.sqlite", Faults(), (WriteFault(attempt=2, kind="silent_drop"),)
    )
    sandbox.seed()
    sandbox.read_issue("ISSUE-1")
    sandbox.read_issue("ISSUE-2")
    sandbox.set_status("ISSUE-1", Status.DONE, timeout=1)
    response = sandbox.set_status("ISSUE-2", Status.DONE, timeout=1)
    assert response["status"] == "done"
    assert sandbox.read_issue("ISSUE-1").version == 1
    assert sandbox.read_issue("ISSUE-2").status == Status.OPEN
    assert [r["injected_fault"] for r in sandbox.write_attempts] == [None, "silent_drop"]
    sandbox.set_status("ISSUE-2", Status.DONE, timeout=1)
    assert sandbox.read_issue("ISSUE-2").version == 1
    assert sandbox.unused_schedule() == []


def test_noop_assignment_counts_and_transient_does_not_commit(tmp_path):
    sandbox = ScheduledSandbox(
        tmp_path / "state.sqlite", Faults(), (WriteFault(attempt=2, kind="transient"),)
    )
    sandbox.seed()
    sandbox.set_status("ISSUE-1", Status.OPEN, timeout=1)
    with pytest.raises(TransientError):
        sandbox.set_status("ISSUE-2", Status.DONE, timeout=1)
    assert sandbox.read_issue("ISSUE-1").version == 0
    assert sandbox.read_issue("ISSUE-2").version == 0
    assert sandbox.write_attempts[1]["injected_fault"] == "transient"


def test_failed_precondition_does_not_deliver_or_move_indexed_event(tmp_path):
    sandbox = ScheduledSandbox(
        tmp_path / "state.sqlite", Faults(), (WriteFault(attempt=1, kind="silent_drop"),)
    )
    sandbox.seed()
    with pytest.raises(TimeoutError):
        sandbox.set_status("ISSUE-1", Status.DONE, timeout=0)
    sandbox.set_status("ISSUE-1", Status.DONE, timeout=1)
    assert sandbox.read_issue("ISSUE-1").status == Status.DONE
    assert sandbox.unused_schedule() == [{"attempt": 1, "kind": "silent_drop"}]
    assert all(r["injected_fault"] is None for r in sandbox.write_attempts)


def test_rejects_duplicate_or_mixed_faults_before_database_creation(tmp_path):
    event = WriteFault(attempt=2, kind="silent_drop")
    for faults, schedule in [(Faults(), (event, event)), (Faults(silent_drops=1), (event,))]:
        with pytest.raises(ValueError):
            ScheduledSandbox(tmp_path / "bad.sqlite", faults, schedule)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("scenario", ["second_drop", "second_transient", "two_drops"])
def test_indexed_pair_recovery_and_audited_exposure(tmp_path, engine, scenario):
    result = repeated_trials(
        tmp_path, repeats=1, task_ids=("pair_done",), scenarios=(scenario,), engine=engine
    )
    recovered = next(r for r in result["runs"] if r["mode"] == "recover")
    assert recovered["ground_truth_success"] and recovered["verified_success"]
    assert recovered["recovery_attempts"] > 0
    assert recovered["final_state"][:2] == [("ISSUE-1", "done", 1), ("ISSUE-2", "done", 1)]
    assert not recovered["unused_write_schedule"]
    assert not recovered["untargeted_changed"]
    expected = 2 if scenario == "two_drops" else 1
    summary = next(g for g in result["summary"] if g["mode"] == "recover")
    assert summary["injected_faults"] == expected
    assert summary["runs_with_injected_fault"] == 1
    baseline = next(r for r in result["runs"] if r["mode"] == "baseline")
    assert not baseline["ground_truth_success"]
    assert not any(r["false_success"] for r in result["runs"] if r["mode"] != "baseline")


def test_unreached_second_write_is_not_recovery(tmp_path):
    result = repeated_trials(
        tmp_path, repeats=1, task_ids=("single_done",), scenarios=("second_drop",), engine="dynamic"
    )
    row = next(r for r in result["runs"] if r["mode"] == "recover")
    assert row["ground_truth_success"] and not row["recovered"]
    assert row["unused_write_schedule"] == [{"attempt": 2, "kind": "silent_drop"}]
    group = next(g for g in result["summary"] if g["mode"] == "recover")
    assert group["injected_faults"] == 0
    assert group["unused_indexed_events"] == 1
