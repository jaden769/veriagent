import copy

import pytest
from test_reflection import setup

from research.reflection_trace import reconcile_reflection_trace
from veriagent.executor import ToolPolicy
from veriagent.models import Action, Budget, Decision, Issue
from veriagent.sandbox import Faults, Sandbox
from veriagent.verification import StateVerifier


def check(events, run_id, **kwargs):
    return reconcile_reflection_trace(events, expected_run_id=run_id, **kwargs)


@pytest.mark.parametrize(
    "faults",
    [
        Faults(),
        Faults(silent_drops=1),
        Faults(silent_drops=100),
        Faults(transient_errors=1),
        Faults(transient_errors=100),
    ],
)
@pytest.mark.parametrize("limit", [0, 1, 2])
def test_actual_success_error_and_budget_traces_reconcile(tmp_path, faults, limit):
    # Faults are mutable per run; do not share consumed parametrized fixtures.
    fresh = Faults(silent_drops=faults.silent_drops, transient_errors=faults.transient_errors)
    agent, task, _, traces = setup(tmp_path, faults=fresh, max_reflections=limit)
    report = agent.run(task)
    events = traces.events(report.run_id)
    before = copy.deepcopy(events)
    result = check(events, report.run_id)
    assert result["consistency_passed"] and events == before
    for field in (
        "actions",
        "decisions",
        "corrective_admissions",
        "claimed_success",
        "original_claimed_success",
        "repeat_write_attempts",
        "corrective_write_attempts",
    ):
        assert result[field] == getattr(report, field)
    assert result["trusted_verification_calls"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "actions",
        "decision_count",
        "admission",
        "phase",
        "feedback",
        "claim",
        "original_claim",
        "oracle",
        "reorder",
        "missing_observation",
        "wrong_trigger",
        "bool_counter",
        "wrong_version",
        "model_calls",
        "late_execution",
    ],
)
def test_corrupt_traces_fail_after_sequence_renumbering(tmp_path, mutation):
    agent, task, _, traces = setup(tmp_path, faults=Faults(silent_drops=1))
    report = agent.run(task)
    events = traces.events(report.run_id)
    contexts = [e for e in events if e["kind"] == "reflection_context"]
    transition = next(e for e in events if e["kind"] == "reflection_transition")
    if mutation == "actions":
        events[-1]["payload"]["actions"] += 1
    elif mutation == "decision_count":
        contexts[1]["payload"]["decisions"] += 1
    elif mutation == "admission":
        transition["payload"]["corrective_admission"] += 1
    elif mutation == "phase":
        contexts[0]["payload"]["phase"] = "reflect"
    elif mutation == "feedback":
        contexts[-1]["payload"]["feedback"] = []
    elif mutation == "claim":
        events[-1]["payload"]["claimed_success"] = False
    elif mutation == "original_claim":
        events[-1]["payload"]["original_claimed_success"] = False
    elif mutation == "oracle":
        contexts[0]["payload"]["verification"] = None
    elif mutation == "reorder":
        events[2], events[3] = events[3], events[2]
    elif mutation == "missing_observation":
        events.remove(next(e for e in events if e["kind"] == "observation"))
    elif mutation == "wrong_trigger":
        transition["payload"]["trigger"] = "recoverable_tool_failure"
    elif mutation == "bool_counter":
        contexts[1]["payload"]["actions"] = True
    elif mutation == "wrong_version":
        events[-1]["payload"]["schema_version"] = True
    elif mutation == "model_calls":
        events[-1]["payload"]["model_calls"] = 1
    else:
        events.append(copy.deepcopy(contexts[0]))
    for seq, event in enumerate(events, 1):
        event["seq"] = seq
    with pytest.raises(ValueError):
        check(events, report.run_id)


def test_false_claim_is_consistent_evidence_not_verified_truth(tmp_path, monkeypatch):
    class LyingTools(Sandbox):
        def read_issue(self, issue_id):
            return Issue(id=issue_id, title="reported", status="done")

    agent, task, tools, traces = setup(tmp_path, tools_class=LyingTools)
    report = agent.run(task)
    assert not StateVerifier(tools.path).verify(task).passed

    def forbidden(*args):
        pytest.fail("Trace reconciliation must not invoke an oracle or policy")

    monkeypatch.setattr(StateVerifier, "verify", forbidden)
    monkeypatch.setattr(agent.provider, "decide", forbidden)
    result = check(traces.events(report.run_id), report.run_id)
    assert result["consistency_passed"] and result["claimed_success"]


def test_explicit_non_idempotent_policy_explains_denied_retry(tmp_path, monkeypatch):
    agent, task, _, traces = setup(tmp_path)
    write = Decision(
        kind="action", action=Action(tool="set_status", issue_id="ISSUE-1", status="done")
    )
    choices = iter(
        [
            write,
            Decision(kind="finish"),
            Decision(kind="action", action=Action(tool="read_issue", issue_id="ISSUE-1")),
            write,
        ]
    )
    agent.executor.policies["set_status"] = ToolPolicy(idempotent=False)
    monkeypatch.setattr(agent.provider, "decide", lambda *args, **kwargs: next(choices))
    report = agent.run(task)
    events = traces.events(report.run_id)
    result = check(events, report.run_id, policies=agent.executor.policies)
    assert result["failure"] == "permission"
    with pytest.raises(ValueError, match="denial"):
        check(events, report.run_id)  # Default safe-policy assumptions do not explain this denial.


def test_late_decision_explains_budget_exit_but_not_early_forgery(tmp_path, monkeypatch):
    agent, task, _, traces = setup(tmp_path, budget=Budget(timeout_seconds=1))
    clock = [0.0]
    monkeypatch.setattr("veriagent.reflection.time.monotonic", lambda: clock[0])

    def late(*args, **kwargs):
        clock[0] = 2.0
        return Decision(kind="finish")

    monkeypatch.setattr(agent.provider, "decide", late)
    report = agent.run(task)
    events = traces.events(report.run_id)
    assert check(events, report.run_id)["failure"] == "budget"
    events[-1]["payload"]["elapsed_ms"] = 1.0
    with pytest.raises(ValueError, match="deadline"):
        check(events, report.run_id)


def test_missing_report_wrong_identity_and_event_bound(tmp_path):
    agent, task, _, traces = setup(tmp_path)
    report = agent.run(task)
    events = traces.events(report.run_id)
    with pytest.raises(ValueError):
        check(events[:-1], report.run_id)
    with pytest.raises(ValueError):
        check(events, "other")
    with pytest.raises(ValueError):
        check([events[0]] * 20001, report.run_id)


def test_executed_action_cannot_bypass_original_task_authorization(tmp_path):
    agent, task, _, traces = setup(tmp_path)
    report = agent.run(task)
    events = traces.events(report.run_id)
    decision = next(e for e in events if e["kind"] == "reflection_decision")
    action = next(e for e in events if e["kind"] == "action")
    decision["payload"]["action"]["issue_id"] = "ISSUE-2"
    action["payload"]["issue_id"] = "ISSUE-2"
    with pytest.raises(ValueError, match="authorization/retry"):
        check(events, report.run_id)


def test_forged_execution_of_denied_stale_retry_is_rejected(tmp_path, monkeypatch):
    agent, task, _, traces = setup(tmp_path)
    write = Decision(
        kind="action", action=Action(tool="set_status", issue_id="ISSUE-1", status="done")
    )
    sequence = iter([write, Decision(kind="finish"), write])
    monkeypatch.setattr(agent.provider, "decide", lambda *args, **kwargs: next(sequence))
    report = agent.run(task)
    events = traces.events(report.run_id)
    assert check(events, report.run_id)["failure"] == "permission"
    denied = next(e for e in events if e["kind"] == "reflection_action_denied")
    denied["kind"] = "action"
    denied["payload"] = write.action.model_dump(mode="json")
    with pytest.raises(ValueError, match="authorization/retry"):
        check(events, report.run_id)


@pytest.mark.parametrize("mutation", ["non_object", "no_payload", "incomplete_config"])
def test_malformed_prefixes_fail_as_validation_errors(tmp_path, mutation):
    agent, task, _, traces = setup(tmp_path)
    report = agent.run(task)
    events = traces.events(report.run_id)
    if mutation == "non_object":
        events[0] = "not an event"
    elif mutation == "no_payload":
        del events[0]["payload"]
    else:
        del events[1]["payload"]["budget"]
    with pytest.raises(ValueError):
        check(events, report.run_id)
