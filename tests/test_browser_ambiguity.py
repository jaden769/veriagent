import json
import os
from pathlib import Path

import pytest

from veriagent.browser_faults import BrowserAppFaults
from veriagent.cli import main
from veriagent.interpretation import load_proposal, proposal_digest, propose_task
from veriagent.models import Budget, Status
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.smoke import smoke_test

browser_test = pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)


def test_post_commit_fault_waits_for_real_change_and_is_one_shot(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite", Faults(silent_drops=1))
    sandbox.seed()
    faults = BrowserAppFaults("lost_ack")
    faults.write(sandbox, "ISSUE-1", Status.DONE)
    assert faults.remaining == 1 and not faults.events[-1]["committed"]
    response = faults.write(sandbox, "ISSUE-1", Status.DONE)
    assert response.status_code == 503
    assert faults.remaining == 0 and faults.events[-1]["committed"]
    assert sandbox.read_issue("ISSUE-1").version == 1
    assert isinstance(faults.write(sandbox, "ISSUE-1", Status.DONE), dict)
    assert faults.events[-1]["injected"] is None
    assert sandbox.read_issue("ISSUE-1").version == 1


def test_noop_does_not_consume_stale_page_fault(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    faults = BrowserAppFaults("stale_dom")
    faults.write(sandbox, "ISSUE-1", Status.OPEN)
    assert faults.remaining == 1 and faults.events[-1]["injected"] is None
    response = faults.write(sandbox, "ISSUE-2", Status.DONE)
    assert response["display_status"] == "open"
    assert sandbox.read_issue("ISSUE-2").status == Status.DONE
    assert faults.events[-1]["after_status"] == "done"


@pytest.mark.parametrize(
    "arguments",
    [
        ["--browser-scenario", "lost_ack"],
        ["--tool-backend", "browser", "--browser-scenario", "stale_dom", "--silent-drops", "1"],
    ],
)
def test_invalid_scenario_combinations_stop_before_provider_or_state(
    tmp_path, monkeypatch, arguments
):
    proposal = Path(
        propose_task("Close ISSUE-1", MockProvider(), tmp_path / "proposal")["proposal_file"]
    )
    monkeypatch.setattr(
        "veriagent.cli.configured_provider",
        lambda args: pytest.fail("Provider should not be created"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "execute",
            str(proposal),
            "--approve",
            proposal_digest(load_proposal(proposal)),
            "--db",
            str(tmp_path / "state.sqlite"),
            *arguments,
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not (tmp_path / "state.sqlite").exists()


@browser_test
@pytest.mark.parametrize("engine", ["static", "dynamic"])
@pytest.mark.parametrize("scenario", ["stale_dom", "lost_ack", "clean"])
def test_real_ambiguity_smoke_resolves_state_without_replay(tmp_path, engine, scenario):
    result = smoke_test(
        tmp_path,
        MockProvider(),
        Budget(timeout_seconds=60, action_timeout_seconds=5),
        engine=engine,
        tool_backend="browser",
        browser_scenario=scenario,
    )
    assert result["smoke_passed"] and not result["recovery_required"]
    assert not result[
        "fault_detected"
    ]  # Initial unsatisfied verification is not a post-write fault.
    assert result["anomaly_observed"] is (scenario != "clean")
    assert result["report"]["verified_success"] and result["report"]["recovery_attempts"] == 0
    assert result["report"]["model_calls"] == 0
    assert result["final_state"][0]["version"] == 1
    assert result["untargeted_issues_unchanged"]
    events = result["browser"]["application_events"]
    assert len(events) == 1 and events[0]["committed"]
    dom = result["browser"]["browser_events"]
    if scenario == "stale_dom":
        assert any(
            e["kind"] == "dom_write_result"
            and e["displayed_status"] == "open"
            and e["requested_status"] == "done"
            for e in dom
        )
    elif scenario == "lost_ack":
        assert events[0]["http_status"] == 503
        assert any(e["kind"] == "action_result" and e["failure"] == "transient" for e in dom)
    directory = Path(result["directory"])
    assert json.loads((directory / "application-events.json").read_text()) == events
    assert json.loads((directory / "browser-events.json").read_text()) == dom


@browser_test
def test_fault_labels_are_not_supplied_to_decision_provider(tmp_path):
    contexts = []

    class Spy(MockProvider):
        def decide(self, task, state, *, timeout=None):
            contexts.append(state.model_dump_json())
            return super().decide(task, state, timeout=timeout)

    result = smoke_test(
        tmp_path,
        Spy(),
        Budget(timeout_seconds=60, action_timeout_seconds=5),
        engine="dynamic",
        tool_backend="browser",
        browser_scenario="lost_ack",
    )
    assert result["smoke_passed"] and contexts
    assert all(
        "lost_ack" not in value and "application_events" not in value and "committed" not in value
        for value in contexts
    )


@browser_test
@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_reviewed_lost_ack_continues_to_other_target_with_zero_retries(
    tmp_path, monkeypatch, capsys, engine
):
    proposal = Path(
        propose_task("Close ISSUE-1 and start ISSUE-2", MockProvider(), tmp_path / "proposals")[
            "proposal_file"
        ]
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "execute",
            str(proposal),
            "--approve",
            proposal_digest(load_proposal(proposal)),
            "--tool-backend",
            "browser",
            "--browser-scenario",
            "lost_ack",
            "--engine",
            engine,
            "--max-retries",
            "0",
            "--db",
            str(tmp_path / "state.sqlite"),
            "--traces",
            str(tmp_path / "traces.sqlite"),
            "--browser-artifacts",
            str(tmp_path / "evidence"),
        ],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["browser_execution_passed"] and result["verified_success"]
    assert result["recovery_attempts"] == 0
    events = json.loads((Path(result["browser_artifacts"]) / "application-events.json").read_text())
    assert [e["issue_id"] for e in events] == ["ISSUE-1", "ISSUE-2"]
    assert [e["after_version"] for e in events] == [1, 1]
    assert events[0]["http_status"] == 503 and events[0]["committed"]
