import json
import os
from pathlib import Path

import pytest

from veriagent.benchmark_cases import load_corpus
from veriagent.browser_controls import compare_control
from veriagent.browser_execution import execute_browser
from veriagent.browser_faults import MULTI_BROWSER_SCENARIOS, BrowserAppFaults
from veriagent.models import Budget, Interpretation, Status, TaskProposal
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore


def test_multiple_events_remain_at_original_positions_when_one_is_ineligible(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults("second_two_drops")
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    faults.write(sandbox, "ISSUE-1", Status.DONE)  # Position two is a no-op.
    faults.write(sandbox, "ISSUE-2", Status.DONE)  # Position three still injects.
    faults.write(sandbox, "ISSUE-2", Status.DONE)
    assert [e["attempt"] for e in faults.events if e["injected"]] == [3]
    assert faults.remaining == 1
    assert sandbox.read_issue("ISSUE-2").version == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_versions", {"ISSUE-1": 2, "ISSUE-2": 0}),
        ("target_statuses", {"ISSUE-1": "open", "ISSUE-2": "open"}),
        ("untargeted_issues_unchanged", False),
    ],
)
def test_partial_progress_control_rejects_lost_or_replayed_work(field, value):
    row = dict(
        task_id="pair_done",
        scenario="second_two_drops",
        mode="recover",
        max_retries=0,
        artifacts="evidence",
        claimed_success=False,
        audit_passed=False,
        execution_passed=False,
        fault_exposed=True,
        recovery_attempts=0,
        application_write_attempts=2,
        commits=1,
        pending_application_faults=1,
        injected_attempts=[2],
        events_dropped=0,
        untargeted_issues_unchanged=True,
        target_titles_unchanged=True,
        target_statuses={"ISSUE-1": "done", "ISSUE-2": "open"},
        target_versions={"ISSUE-1": 1, "ISSUE-2": 0},
    )
    assert compare_control(row)["passed"]
    assert field in compare_control({**row, field: value})["mismatches"]


@pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)
@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("scenario", MULTI_BROWSER_SCENARIOS)
@pytest.mark.parametrize("retries", [0, 2])
def test_multi_event_browser_preserves_progress_and_reports_exhaustion(
    tmp_path, engine, scenario, retries
):
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
        Budget(
            max_actions=10,
            max_decisions=10,
            timeout_seconds=30,
            action_timeout_seconds=1,
            max_retries=retries,
        ),
        output=tmp_path / "evidence",
        engine=engine,
        browser_scenario=scenario,
    )
    assert result["browser_execution_passed"] is bool(retries)
    assert result["claimed_success"] is bool(retries)
    events = json.loads((Path(result["browser_artifacts"]) / "application-events.json").read_text())
    assert sum(e["issue_id"] == "ISSUE-1" for e in events) == 1
    assert sandbox.read_issue("ISSUE-1").version == 1
    assert sandbox.read_issue("ISSUE-2").version == int(bool(retries))
    assert result["browser_audit"]["untargeted_issues_unchanged"]
    assert [e["attempt"] for e in events if e["injected"]] == ([2, 3] if retries else [2])
