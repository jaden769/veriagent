import json

import pytest

from veriagent.cli import main
from veriagent.models import Budget, Plan
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.smoke import smoke_test


def test_smoke_saves_complete_evidence_and_uses_fresh_state(tmp_path):
    first = smoke_test(tmp_path, MockProvider())
    second = smoke_test(tmp_path, MockProvider())
    assert first["directory"] != second["directory"]
    for result in (first, second):
        assert result["smoke_passed"] and result["fault_detected"]
        assert result["untargeted_issues_unchanged"]
        assert result["initial_state"][0]["status"] == "open"
        assert result["final_state"][0]["status"] == "done"
        assert result["report"]["actions"] == 2
        assert result["report"]["recovery_attempts"] == 1
        assert result["report"]["model_calls"] == 0
        from pathlib import Path

        directory = Path(result["directory"])
        assert json.loads((directory / "result.json").read_text()) == result
        events = json.loads((directory / "trace.json").read_text())
        assert {"verification", "recovery", "evaluation_audit", "smoke_result"} <= {
            e["kind"] for e in events
        }
        assert (directory / "trace.txt").exists()
        assert (directory / "traces.sqlite").exists()
        assert (directory / "state.sqlite").exists()


def test_smoke_without_recovery_reports_failure(tmp_path):
    result = smoke_test(tmp_path, MockProvider(), Budget(max_retries=0))
    assert not result["smoke_passed"]
    assert result["fault_detected"] and not result["audit"]["passed"]


def test_planning_failure_still_saves_audit_and_report(tmp_path):
    class BrokenProvider(MockProvider):
        def plan(self, task, *, timeout=None):
            raise RuntimeError("SECRET-ERROR-DETAIL")

    result = smoke_test(tmp_path, BrokenProvider())
    assert not result["smoke_passed"] and not result["fault_detected"]
    assert result["report"]["failure"] == "planning"
    assert result["report"]["actions"] == 0
    for file in tmp_path.glob("*/*.json"):
        assert "SECRET-ERROR-DETAIL" not in file.read_text()


def test_task_completion_alone_does_not_pass_recovery_smoke(tmp_path):
    class DuplicateWrites(MockProvider):
        def plan(self, task, *, timeout=None):
            step = super().plan(task).steps[0]
            return Plan(steps=(step, step.model_copy(update={"id": "second-write"})))

    result = smoke_test(tmp_path, DuplicateWrites())
    assert result["audit"]["passed"] and result["report"]["verified_success"]
    assert not result["fault_detected"] and not result["smoke_passed"]


def test_smoke_detects_collateral_state_changes(tmp_path, monkeypatch):
    original = Sandbox.set_status

    def buggy_update(self, issue_id, status, *, timeout):
        result = original(self, issue_id, status, timeout=timeout)
        original(self, "ISSUE-2", status, timeout=timeout)
        return result

    monkeypatch.setattr(Sandbox, "set_status", buggy_update)
    result = smoke_test(tmp_path, MockProvider())
    assert result["audit"]["passed"]
    assert not result["untargeted_issues_unchanged"] and not result["smoke_passed"]


def test_cli_defaults_to_offline_even_with_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("OPENAI_MODEL", "not-a-real-model")

    def forbidden(*args):
        pytest.fail("Default smoke must not construct a paid provider")

    monkeypatch.setattr("veriagent.cli.OpenAIProvider.from_env", forbidden)
    monkeypatch.setattr("sys.argv", ["veriagent", "smoke", "--output", str(tmp_path)])
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["smoke_passed"] and result["report"]["model_calls"] == 0


@pytest.mark.parametrize("has_model", [False, True])
def test_cli_missing_configuration_exits_before_artifacts(tmp_path, monkeypatch, capsys, has_model):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    argv = ["veriagent", "smoke", "--provider", "openai", "--output", str(tmp_path / "output")]
    if has_model:
        argv += ["--model", "test-model"]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert ("OPENAI_API_KEY" if has_model else "OPENAI_MODEL") in capsys.readouterr().err
    assert not (tmp_path / "output").exists()


def test_cli_reports_failed_smoke_with_exit_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["veriagent", "smoke", "--output", str(tmp_path)])
    monkeypatch.setattr("veriagent.cli.smoke_test", lambda *args: {"smoke_passed": False})
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)["smoke_passed"] is False
