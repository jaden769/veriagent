import copy
import json
import os
from pathlib import Path

import pytest

from veriagent.browser import BrowserSetupError, BrowserTools
from veriagent.browser_execution import audit_browser_state
from veriagent.cli import main
from veriagent.interpretation import load_proposal, proposal_digest, propose_task
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore

browser_test = pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)


@pytest.fixture
def proposal_file(tmp_path):
    result = propose_task("Close ISSUE-1 and start ISSUE-2", MockProvider(), tmp_path / "proposals")
    return Path(result["proposal_file"])


def argv_for(proposal_file, tmp_path, *options):
    return [
        "veriagent",
        "execute",
        str(proposal_file),
        "--approve",
        proposal_digest(load_proposal(proposal_file)),
        "--tool-backend",
        "browser",
        "--db",
        str(tmp_path / "state.sqlite"),
        "--traces",
        str(tmp_path / "traces.sqlite"),
        "--browser-artifacts",
        str(tmp_path / "evidence"),
        *options,
    ]


@pytest.mark.parametrize(
    "options",
    [
        ("--isolate-tools",),
        ("--hang-before-commit", "1"),
        ("--hang-after-commit", "1"),
        ("--approve", "0" * 64),
    ],
)
def test_browser_preflight_rejects_before_provider_state_or_browser(
    proposal_file, tmp_path, monkeypatch, options
):
    monkeypatch.setattr(
        "veriagent.cli.configured_provider",
        lambda args: pytest.fail("Provider must not be created"),
    )
    monkeypatch.setattr(
        BrowserTools, "__enter__", lambda self: pytest.fail("Browser must not start")
    )
    monkeypatch.setattr("sys.argv", argv_for(proposal_file, tmp_path, *options))
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not (tmp_path / "state.sqlite").exists()
    assert not (tmp_path / "traces.sqlite").exists()
    assert not (tmp_path / "evidence").exists()


def test_audit_checks_all_targets_titles_and_unrelated_rows(proposal_file):
    task = load_proposal(proposal_file).task()
    initial = [
        {"id": f"ISSUE-{i}", "title": f"Title {i}", "status": "open", "version": 0}
        for i in range(1, 4)
    ]
    final = copy.deepcopy(initial)
    final[0].update(status="done", version=1)
    assert not audit_browser_state(task, initial, final)["targets_passed"]
    final[1].update(status="in_progress", version=1)
    assert audit_browser_state(task, initial, final)["passed"]
    for change in ("unrelated_title", "unrelated_version", "target_title", "delete", "add"):
        changed = copy.deepcopy(final)
        if change == "unrelated_title":
            changed[2]["title"] = "Changed"
        elif change == "unrelated_version":
            changed[2]["version"] += 1
        elif change == "target_title":
            changed[0]["title"] = "Changed"
        elif change == "delete":
            changed.pop()
        else:
            changed.append({"id": "ISSUE-4", "title": "New", "status": "open", "version": 0})
        assert not audit_browser_state(task, initial, changed)["passed"]


@browser_test
@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_real_reviewed_browser_multi_target_execution(
    proposal_file, tmp_path, monkeypatch, capsys, engine
):
    monkeypatch.setenv("OPENAI_API_KEY", "unused-fake-key")
    monkeypatch.setattr(
        "sys.argv", argv_for(proposal_file, tmp_path, "--engine", engine, "--silent-drops", "1")
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["browser_execution_passed"] and result["verified_success"]
    assert result["browser_audit"]["passed"]
    assert result["tool_execution"] == "browser" and result["model_calls"] == 0
    assert result["recovery_attempts"] == 1
    assert result["browser"]["cleanup_completed"]
    assert len(result["browser"]["captures"]) == 4
    assert all(c["captured"] for c in result["browser"]["captures"])
    bundle = json.loads((Path(result["browser_artifacts"]) / "result.json").read_text())
    assert bundle["result"] == result
    assert bundle["budget"]["action_timeout_seconds"] == 5
    assert bundle["approval_digest"] == proposal_digest(load_proposal(proposal_file))
    assert [(r["id"], r["status"], r["version"]) for r in bundle["final_state"]] == [
        ("ISSUE-1", "done", 1),
        ("ISSUE-2", "in_progress", 1),
        ("ISSUE-3", "open", 0),
    ]
    events = TraceStore(tmp_path / "traces.sqlite").events(result["run_id"])
    review = next(e for e in events if e["kind"] == "requirements_review")
    assert review["seq"] < next(e["seq"] for e in events if e["kind"] == "action")
    assert review["payload"]["proposal_digest"] == bundle["approval_digest"]
    assert events[-1]["kind"] == "browser_execution_audit"


@browser_test
def test_browser_evaluator_rejects_collateral_changes_without_overwriting_claim(
    proposal_file, tmp_path, monkeypatch, capsys
):
    original = Sandbox.set_status

    def collateral(self, issue_id, status, *, timeout):
        response = original(self, issue_id, status, timeout=timeout)
        original(self, "ISSUE-3", status, timeout=timeout)
        return response

    monkeypatch.setattr(Sandbox, "set_status", collateral)
    monkeypatch.setattr("sys.argv", argv_for(proposal_file, tmp_path))
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["claimed_success"] and result["verified_success"]
    assert result["browser_audit"]["targets_passed"]
    assert not result["browser_execution_passed"]
    assert not result["browser_audit"]["untargeted_issues_unchanged"]


@browser_test
def test_browser_baseline_false_success_is_retained_but_cli_fails(
    proposal_file, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        "sys.argv", argv_for(proposal_file, tmp_path, "--mode", "baseline", "--silent-drops", "1")
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["claimed_success"] and result["verified_success"] is None
    assert not result["browser_execution_passed"]
    assert not result["browser_audit"]["targets_passed"]


@browser_test
def test_cleanup_failure_cannot_pass_even_with_correct_state(
    proposal_file, tmp_path, monkeypatch, capsys
):
    original = BrowserTools.close

    def close_with_error(self):
        original(self)
        raise BrowserSetupError("Injected cleanup failure")

    monkeypatch.setattr(BrowserTools, "close", close_with_error)
    monkeypatch.setattr("sys.argv", argv_for(proposal_file, tmp_path))
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["claimed_success"] and result["browser_audit"]["passed"]
    assert not result["browser"]["cleanup_completed"]
    assert not result["browser_execution_passed"]
