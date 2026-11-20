import json
import os
import sqlite3
import threading
import time

import pytest

from veriagent.benchmark_cases import load_corpus
from veriagent.browser_execution import execute_browser
from veriagent.browser_faults import BrowserAppFaults
from veriagent.cli import main
from veriagent.models import Budget, Interpretation, Status, TaskProposal
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.smoke import smoke_test
from veriagent.trace import TraceStore

browser_test = pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)


@pytest.mark.parametrize(
    "scenario,expected", [("timeout_before_commit", "open"), ("timeout_after_commit", "done")]
)
@pytest.mark.parametrize("reason", ["action_timeout", "browser_cleanup"])
def test_held_response_has_known_commit_boundary_and_releases_without_deadlock(
    tmp_path, scenario, expected, reason
):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults(scenario)
    errors = []

    def write():
        try:
            faults.write(sandbox, "ISSUE-1", Status.DONE)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=write, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while (
            not any(e.get("response_state") == "held" for e in faults.events)
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)
        assert faults.events and faults.events[0]["response_state"] == "held"
        assert sandbox.read_issue("ISSUE-1").status == expected
    finally:
        faults.release_pending(reason)
        worker.join(timeout=2)
    assert not worker.is_alive() and not errors
    assert faults.events[0]["release_reason"] == reason
    assert faults.events[0]["response_state"] == "released"
    assert sandbox.read_issue("ISSUE-1").status == expected  # No late pre-commit write.


def test_safety_release_is_not_reported_as_action_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("veriagent.browser_faults.ACK_HOLD_SECONDS", 0.02)
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults("timeout_after_commit")
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    assert faults.events[0]["release_reason"] == "safety_deadline"
    assert sandbox.read_issue("ISSUE-1").version == 1


def test_invalid_timeout_budget_is_rejected_before_provider_or_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "veriagent.cli.configured_provider",
        lambda args: pytest.fail("No provider should be constructed"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "browser-smoke",
            "--browser-scenario",
            "timeout_after_commit",
            "--action-timeout",
            "10",
            "--output",
            str(tmp_path / "output"),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not (tmp_path / "output").exists()


@browser_test
@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("scenario", ["timeout_before_commit", "timeout_after_commit"])
def test_real_browser_deadline_resolves_persisted_state_before_retry(tmp_path, engine, scenario):
    result = smoke_test(
        tmp_path,
        MockProvider(),
        Budget(timeout_seconds=30, action_timeout_seconds=1),
        engine=engine,
        tool_backend="browser",
        browser_scenario=scenario,
    )
    assert result["smoke_passed"] and result["anomaly_observed"]
    before = scenario == "timeout_before_commit"
    assert result["recovery_required"] is before
    assert result["report"]["recovery_attempts"] == int(before)
    assert result["final_state"][0]["version"] == 1
    assert result["report"]["model_calls"] == 0
    events = result["browser"]["application_events"]
    assert len(events) == (2 if before else 1)
    assert events[0]["committed"] is not before
    assert events[0]["release_reason"] == "action_timeout"
    assert events[0]["response_state"] == "released"
    assert sum(e["committed"] for e in events) == 1
    assert result["untargeted_issues_unchanged"]


@browser_test
def test_before_commit_timeout_with_no_retries_fails_without_late_commit(tmp_path):
    result = smoke_test(
        tmp_path,
        MockProvider(),
        Budget(max_retries=0, timeout_seconds=30, action_timeout_seconds=1),
        engine="dynamic",
        tool_backend="browser",
        browser_scenario="timeout_before_commit",
    )
    assert not result["smoke_passed"] and not result["audit"]["passed"]
    assert result["final_state"][0]["status"] == "open"
    assert result["final_state"][0]["version"] == 0
    assert len(result["browser"]["application_events"]) == 1


@browser_test
@pytest.mark.parametrize("case_id", ["mixed_status", "reopen", "partial_satisfied"])
@pytest.mark.parametrize("scenario", ["timeout_before_commit", "timeout_after_commit"])
def test_timeout_boundaries_across_varied_reviewed_tasks(tmp_path, case_id, scenario):
    case = next(c for c in load_corpus()[0].cases if c.id == case_id)
    proposal = TaskProposal(
        objective=case.task.objective,
        interpretation=Interpretation(requirements=case.task.requirements),
    )
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    with sqlite3.connect(sandbox.path) as db:
        db.executemany(
            "UPDATE issues SET status=? WHERE id=?",
            [(status.value, issue) for issue, status in case.initial_statuses.items()],
        )
    result = execute_browser(
        proposal,
        MockProvider(),
        sandbox,
        TraceStore(tmp_path / "traces.sqlite"),
        Budget(
            max_retries=2 if scenario == "timeout_before_commit" else 0,
            timeout_seconds=30,
            action_timeout_seconds=1,
            max_actions=8,
            max_decisions=8,
        ),
        output=tmp_path / "evidence",
        engine="dynamic",
        browser_scenario=scenario,
    )
    assert result["browser_execution_passed"] and result["browser_audit"]["passed"]
    assert result["recovery_attempts"] == int(scenario == "timeout_before_commit")
    from pathlib import Path

    events = json.loads((Path(result["browser_artifacts"]) / "application-events.json").read_text())
    assert sum(e["injected"] == scenario for e in events) == 1
    assert (
        next(e for e in events if e["injected"] == scenario)["release_reason"] == "action_timeout"
    )
    for requirement in case.task.requirements:
        issue = sandbox.read_issue(requirement.issue_id)
        assert issue.status == requirement.status
        assert issue.version == int(case.initial_statuses[issue.id] != requirement.status)
