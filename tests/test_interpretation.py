import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from veriagent.cli import main
from veriagent.interpretation import (
    approved_task,
    interpret_offline,
    load_proposal,
    proposal_digest,
    propose_task,
)
from veriagent.models import Interpretation, Requirement, TaskProposal
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore

CASES = json.loads((Path(__file__).parent / "fixtures/interpretation_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["objective"] for c in CASES])
def test_varied_instructions_and_unsupported_requests(case):
    result = interpret_offline(case["objective"])
    if case["requirements"] is None:
        assert result.clarification and not result.requirements
    else:
        assert result.clarification is None
        assert [[r.issue_id, r.status.value] for r in result.requirements] == case["requirements"]


@pytest.fixture
def proposal_file(tmp_path):
    result = propose_task("Close ISSUE-1 and start ISSUE-2", MockProvider(), tmp_path)
    return Path(result["proposal_file"])


def test_proposing_never_creates_application_state(proposal_file):
    proposal = load_proposal(proposal_file)
    assert len(proposal.task().requirements) == 2
    assert not list(proposal_file.parent.glob("*.sqlite"))
    assert proposal.interpretation_usage.calls == 0


def test_digest_binds_all_proposal_fields(proposal_file):
    proposal = load_proposal(proposal_file)
    digest = proposal_digest(proposal)
    task, loaded = approved_task(proposal_file, digest)
    assert loaded == proposal and task == proposal.task()
    data = json.loads(proposal_file.read_text())
    data["interpretation"]["requirements"][0]["status"] = "open"
    proposal_file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="digest"):
        approved_task(proposal_file, digest)


def test_formatting_changes_do_not_change_reviewed_content(proposal_file):
    digest = proposal_digest(load_proposal(proposal_file))
    proposal_file.write_text(json.dumps(json.loads(proposal_file.read_text()), sort_keys=True))
    assert approved_task(proposal_file, digest)[0].requirements[0].status == "done"


@pytest.mark.parametrize("digest", ["", "yes", "0" * 64, "a" * 100000])
def test_bad_or_missing_digest_never_approves(proposal_file, digest):
    with pytest.raises(ValueError, match="digest"):
        approved_task(proposal_file, digest)


def test_clarification_cannot_be_approved(tmp_path):
    result = propose_task("Close the issue", MockProvider(), tmp_path)
    path = Path(result["proposal_file"])
    assert result["needs_clarification"]
    with pytest.raises(ValueError, match="clarification"):
        approved_task(path, proposal_digest(load_proposal(path)))


@pytest.mark.parametrize("mutation", ["extra_field", "wrong_target", "duplicate", "oversize"])
def test_invalid_proposals_rejected(proposal_file, mutation):
    data = json.loads(proposal_file.read_text())
    if mutation == "extra_field":
        data["approved"] = True
    elif mutation == "wrong_target":
        data["interpretation"]["requirements"][0]["issue_id"] = "ISSUE-999"
    elif mutation == "duplicate":
        data["interpretation"]["requirements"].append(data["interpretation"]["requirements"][0])
    else:
        proposal_file.write_text(" " * 65537)
        with pytest.raises(ValueError, match="64 KiB"):
            load_proposal(proposal_file)
        return
    proposal_file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_proposal(proposal_file)


def test_cli_review_and_execute_with_fault_recovery(proposal_file, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["veriagent", "review", str(proposal_file)])
    main()
    reviewed = json.loads(capsys.readouterr().out)
    assert reviewed["interpretation"]["requirements"][0]["status"] == "done"
    db, traces = tmp_path / "state.sqlite", tmp_path / "traces.sqlite"
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "execute",
            str(proposal_file),
            "--approve",
            reviewed["approval_digest"],
            "--db",
            str(db),
            "--traces",
            str(traces),
            "--silent-drops",
            "1",
        ],
    )
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["verified_success"] and report["actions"] == 3
    assert report["recovery_attempts"] == 1
    sandbox = Sandbox(db)
    assert sandbox.read_issue("ISSUE-1").status == "done"
    assert sandbox.read_issue("ISSUE-2").status == "in_progress"
    assert sandbox.read_issue("ISSUE-3").status == "open"
    events = TraceStore(traces).events(report["run_id"])
    review = next(e for e in events if e["kind"] == "requirements_review")
    assert review["payload"]["proposal_digest"] == reviewed["approval_digest"]
    assert review["seq"] < next(e["seq"] for e in events if e["kind"] == "action")


def test_wrong_approval_stops_before_provider_or_state(
    proposal_file, tmp_path, monkeypatch, capsys
):
    def forbidden(*args):
        pytest.fail("Invalid approval must stop before provider construction")

    monkeypatch.setattr("veriagent.cli.configured_provider", forbidden)
    db = tmp_path / "new-state.sqlite"
    monkeypatch.setattr(
        "sys.argv",
        ["veriagent", "execute", str(proposal_file), "--approve", "0" * 64, "--db", str(db)],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "digest" in capsys.readouterr().err and not db.exists()


def test_interpretation_failure_retains_usage_without_raw_error(tmp_path):
    class BrokenInterpreter(MockProvider):
        def interpret(self, objective, *, timeout=None):
            raise RuntimeError("SECRET-ERROR-TEXT")

    result = propose_task("Close ISSUE-1", BrokenInterpreter(), tmp_path)
    assert result["error"] == "interpretation_failed" and result["proposal_file"] is None
    assert result["model_usage"]["calls"] == 0
    assert "SECRET-ERROR-TEXT" not in next(tmp_path.glob("*/interpretation.json")).read_text()


def test_agent_cannot_substitute_another_reviewed_task(proposal_file, tmp_path):
    from veriagent.agent import Agent
    from veriagent.executor import Executor
    from veriagent.verification import StateVerifier

    proposal = load_proposal(proposal_file)
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    agent = Agent(
        MockProvider(),
        Executor(sandbox),
        StateVerifier(sandbox.path),
        TraceStore(tmp_path / "traces.sqlite"),
    )
    with pytest.raises(ValueError, match="does not match"):
        agent.run(MockProvider().parse("Set ISSUE-3 to done"), reviewed_proposal=proposal)
    assert sandbox.read_issue("ISSUE-3").status == "open"


def test_interpretation_requires_a_single_decision():
    req = Requirement(issue_id="ISSUE-1", status="done")
    for values in ({"requirements": ()}, {"requirements": (req,), "clarification": "Which?"}):
        with pytest.raises(ValidationError):
            Interpretation(**values)
    with pytest.raises(ValidationError):
        TaskProposal(objective="", interpretation=Interpretation(requirements=(req,)))
