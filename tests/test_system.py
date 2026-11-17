import json
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from veriagent.agent import Agent
from veriagent.api import create_app
from veriagent.evaluation import compare
from veriagent.executor import Executor, ToolPolicy
from veriagent.models import Action, Budget, Failure, Mode, Plan, Status, Step
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


@pytest.fixture
def system(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    provider = MockProvider()
    traces = TraceStore(tmp_path / "traces.sqlite")
    verifier = StateVerifier(sandbox.path)
    executor = Executor(sandbox)
    agent = Agent(provider, executor, verifier, traces)
    return sandbox, provider, traces, verifier, executor, agent


@pytest.mark.parametrize(
    "mode,claim,truth,retries",
    [
        (Mode.BASELINE, True, False, 0),
        (Mode.VERIFY, False, False, 0),
        (Mode.RECOVER, True, True, 1),
    ],
)
def test_silent_success_is_detected_and_repaired(system, mode, claim, truth, retries):
    sandbox, provider, traces, verifier, _, agent = system
    sandbox.faults.silent_drops = 1
    task = provider.parse("Set ISSUE-1 to done")
    report = agent.run(task, mode)
    assert report.claimed_success is claim
    assert verifier.verify(task).passed is truth
    assert report.recovery_attempts == retries
    assert report.verified_success is (None if mode == Mode.BASELINE else truth)
    kinds = [e["kind"] for e in traces.events(report.run_id)]
    assert {"task", "plan", "action", "observation", "report"} <= set(kinds)
    if retries:
        assert {"verification", "recovery"} <= set(kinds)


@pytest.mark.parametrize("mode", list(Mode))
def test_clean_completion(system, mode):
    _, provider, _, verifier, _, agent = system
    task = provider.parse("Mark ISSUE-1, ISSUE-2 as done")
    assert agent.run(task, mode).claimed_success
    assert verifier.verify(task).passed


def test_persistent_fault_is_bounded(system):
    sandbox, provider, _, _, _, agent = system
    sandbox.faults.silent_drops = 100
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert not report.claimed_success
    assert report.actions == 3
    assert report.recovery_attempts == 2
    assert report.failure == Failure.STATE_MISMATCH


@pytest.mark.parametrize(
    "budget,actions",
    [
        (Budget(max_retries=0), 1),
        (Budget(max_actions=1), 1),
    ],
)
def test_budget_limits(system, budget, actions):
    sandbox, provider, _, _, _, agent = system
    sandbox.faults.silent_drops = 100
    agent.budget = budget
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.actions == actions
    assert report.recovery_attempts == 0
    assert not report.claimed_success


def test_transient_failure_recovers(system):
    sandbox, provider, _, _, _, agent = system
    sandbox.faults.transient_errors = 1
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.verified_success and report.recovery_attempts == 1


def test_selective_repair_does_not_replay_completed_writes(system):
    sandbox, provider, _, _, _, agent = system
    sandbox.faults.silent_drops = 1
    report = agent.run(provider.parse("Set ISSUE-1, ISSUE-2 to done"))
    assert report.verified_success and report.actions == 3
    assert sandbox.read_issue("ISSUE-2").version == 1


def test_missing_issue_is_not_retried(system):
    _, provider, _, _, _, agent = system
    report = agent.run(provider.parse("Set ISSUE-999 to done"))
    assert report.failure == Failure.NOT_FOUND
    assert not report.claimed_success and report.recovery_attempts == 0


def test_permissions_are_enforced(system):
    sandbox, provider, _, _, _, agent = system
    agent.executor = Executor(sandbox, allowed_tools=frozenset({"read_issue"}))
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.PERMISSION
    assert report.recovery_attempts == 0
    assert sandbox.read_issue("ISSUE-1").status == Status.OPEN


def test_non_idempotent_policy_prevents_retry(system):
    sandbox, provider, _, _, executor, agent = system
    sandbox.faults.silent_drops = 1
    executor.policies["set_status"] = ToolPolicy(idempotent=False)
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.actions == 1 and report.recovery_attempts == 0
    assert not report.claimed_success


def test_timeout_is_bounded(system):
    sandbox, provider, _, _, _, agent = system
    sandbox.faults.delay_seconds = 2
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.TIMEOUT and report.actions == 3
    assert not report.claimed_success


def test_idempotent_assignment(system):
    sandbox, *_ = system
    sandbox.set_status("ISSUE-1", Status.DONE, timeout=1)
    sandbox.set_status("ISSUE-1", Status.DONE, timeout=1)
    assert sandbox.read_issue("ISSUE-1").version == 1


def test_verifier_reads_actual_persisted_state(system):
    sandbox, provider, _, verifier, *_ = system
    task = provider.parse("Set ISSUE-1 to done")
    with sqlite3.connect(sandbox.path) as db:
        db.execute("UPDATE issues SET status='done', version=9 WHERE id='ISSUE-1'")
    result = verifier.verify(task)
    assert result.passed and result.evidence[0].version == 9
    assert result.evidence[0].source == "sqlite_read_only"


def test_missing_evidence_fails_closed(system):
    sandbox, provider, _, _, _, agent = system
    agent.verifier = StateVerifier(sandbox.path.parent / "missing.sqlite")
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert not report.claimed_success
    assert report.failure == Failure.INTERNAL
    assert report.verified_success is None


@pytest.mark.parametrize(
    "objective",
    [
        "do anything",
        "Set ISSUE-1 to done and delete everything",
        "Set ISSUE-1, ISSUE-1 to done",
    ],
)
def test_unsupported_or_ambiguous_objectives_rejected(objective):
    with pytest.raises(ValueError):
        MockProvider().parse(objective)


def test_schemas_and_dependencies(system):
    _, provider, *_ = system
    task = provider.parse("Set ISSUE-1 to done")
    with pytest.raises(ValidationError):
        Action(tool="set_status", issue_id="ISSUE-1", status="done", idempotent=True)
    with pytest.raises(ValidationError):
        Plan(
            steps=(
                Step(
                    id="a",
                    action=Action(tool="set_status", issue_id="ISSUE-1", status="done"),
                    expected=task.requirements[0],
                    depends_on=("a",),
                ),
            )
        )
    with pytest.raises(ValidationError):
        Budget(max_retries=-1)


def test_provider_cannot_change_authorized_target(system):
    _, provider, _, _, _, agent = system
    task = provider.parse("Set ISSUE-1 to done")
    bad = provider.plan(provider.parse("Set ISSUE-2 to done"))
    with pytest.raises(ValueError, match="outside"):
        agent.validate_plan(task, bad)


def test_api_validates_and_exposes_actual_state(system):
    sandbox, *_ = system
    client = TestClient(create_app(sandbox))
    assert client.patch("/issues/ISSUE-1/status", json={"status": "invalid"}).status_code == 422
    assert client.get("/issues/ISSUE-999").status_code == 404
    sandbox.faults.silent_drops = 1
    assert client.patch("/issues/ISSUE-1/status", json={"status": "done"}).status_code == 200
    assert client.get("/issues/ISSUE-1").json()["status"] == "open"
    assert client.patch("/issues/ISSUE-1/status", json={"status": "done"}).status_code == 200
    assert client.get("/issues/ISSUE-1").json()["status"] == "done"


@pytest.mark.parametrize("scenario", ["clean", "silent_drop", "persistent_drop", "transient"])
def test_comparison_and_durable_traces(tmp_path, scenario):
    result = compare(tmp_path, scenario)
    assert len(result["runs"]) == 3
    traces = TraceStore(next(tmp_path.glob("*/traces.sqlite")))
    for row in result["runs"]:
        events = traces.events(row["run_id"])
        assert events[-1]["kind"] == "evaluation_audit"
        assert "report" in [e["kind"] for e in events]
    saved = json.loads(next(tmp_path.glob("*/comparison.json")).read_text())
    assert saved == result
    if scenario == "silent_drop":
        assert result["runs"][0]["false_success"]
        assert result["runs"][2]["recovered"]


def test_installed_cli(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "veriagent.cli", "demo", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "false-success" in result.stdout
