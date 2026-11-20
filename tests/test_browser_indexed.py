import json
import os
from pathlib import Path

import pytest

from veriagent.benchmark_cases import load_corpus
from veriagent.browser_controls import compare_control
from veriagent.browser_execution import execute_browser
from veriagent.browser_faults import INDEXED_BROWSER_SCENARIOS, BrowserAppFaults
from veriagent.models import Budget, Interpretation, Status, TaskProposal
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore


def test_second_drop_preserves_first_commit_and_records_exact_attempt(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults("second_drop")
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    sandbox.read_issue("ISSUE-2")  # Reads do not advance mutation positions.
    faults.write(sandbox, "ISSUE-2", Status.DONE)
    assert sandbox.read_issue("ISSUE-1").version == 1
    assert sandbox.read_issue("ISSUE-2").status == Status.OPEN
    faults.write(sandbox, "ISSUE-2", Status.DONE)
    assert [e["attempt"] for e in faults.events] == [1, 2, 3]
    assert [e["injected"] for e in faults.events] == [None, "second_drop", None]
    assert sandbox.read_issue("ISSUE-2").version == 1 and faults.remaining == 0


def test_noop_at_scheduled_position_leaves_fault_unused_without_shifting(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults("second_lost_ack")
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    faults.write(sandbox, "ISSUE-2", Status.DONE)
    assert faults.remaining == 1 and not any(e["injected"] for e in faults.events)
    assert faults.events[1]["scheduled_fault"] == "second_lost_ack"


def test_missing_target_consumes_position_without_shifting_fault(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults("second_drop")
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    with pytest.raises(KeyError):
        faults.write(sandbox, "ISSUE-99", Status.DONE)
    faults.write(sandbox, "ISSUE-2", Status.DONE)
    assert faults.remaining == 1 and faults.events[-1]["attempt"] == 3


def test_indexed_expectation_rejects_fault_shift():
    result = compare_control(
        dict(
            task_id="pair_done",
            scenario="second_drop",
            mode="recover",
            artifacts="evidence",
            fault_exposed=True,
            claimed_success=True,
            audit_passed=True,
            execution_passed=True,
            recovery_attempts=1,
            commits=2,
            application_write_attempts=3,
            events_dropped=0,
            planned_fault_attempt=2,
            injected_attempts=[3],
            pending_application_faults=0,
        )
    )
    assert result["mismatches"] == {"injected_attempts": {"expected": [2], "actual": [3]}}


@pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)
@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("scenario", INDEXED_BROWSER_SCENARIOS)
def test_second_write_browser_fault_does_not_replay_first_target(tmp_path, engine, scenario):
    case = next(c for c in load_corpus()[0].cases if c.id == "pair_done")
    proposal = TaskProposal(
        objective=case.task.objective,
        interpretation=Interpretation(requirements=case.task.requirements),
    )
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    result = execute_browser(
        proposal,
        MockProvider(),
        sandbox,
        TraceStore(tmp_path / "traces.sqlite"),
        Budget(max_actions=8, max_decisions=8, timeout_seconds=30, action_timeout_seconds=1),
        output=tmp_path / "evidence",
        engine=engine,
        browser_scenario=scenario,
    )
    assert result["browser_execution_passed"]
    events = json.loads((Path(result["browser_artifacts"]) / "application-events.json").read_text())
    assert [e["attempt"] for e in events if e["injected"]] == [2]
    assert sum(e["issue_id"] == "ISSUE-1" for e in events) == 1
    assert sandbox.read_issue("ISSUE-1").version == sandbox.read_issue("ISSUE-2").version == 1
