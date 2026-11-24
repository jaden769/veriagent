import json

import pytest

from veriagent.executor import Executor, ToolPolicy
from veriagent.models import Action, Budget, Decision, Issue, Observation, Requirement, Task
from veriagent.reflection import (
    MockReflectionProvider,
    ReflectionAgent,
    ReflectionReport,
    ReflectionState,
)
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def setup(tmp_path, *, faults=None, tools_class=Sandbox, budget=None, max_reflections=None):
    tools = tools_class(tmp_path / "state.sqlite", faults)
    tools.seed()
    traces = TraceStore(tmp_path / "traces.sqlite")
    executor = Executor(tools)
    agent = ReflectionAgent(executor, traces, budget, max_reflections=max_reflections)
    task = Task(
        objective="Set ISSUE-1 to done",
        requirements=(Requirement(issue_id="ISSUE-1", status="done"),),
    )
    return agent, task, tools, traces


@pytest.mark.parametrize("drops,actions,decisions,repeat", [(0, 3, 5, 0), (1, 5, 7, 1)])
def test_clean_and_dropped_write_reflection(tmp_path, drops, actions, decisions, repeat):
    agent, task, tools, traces = setup(tmp_path, faults=Faults(silent_drops=drops))
    report = agent.run(task)
    assert report.claimed_success and report.original_claimed_success
    assert report.verified_success is None and report.failure is None
    assert (report.actions, report.decisions, report.repeat_write_attempts) == (
        actions,
        decisions,
        repeat,
    )
    assert report.corrective_admissions == 1
    assert StateVerifier(tools.path).verify(task).passed
    assert not any(e["kind"] == "verification" for e in traces.events(report.run_id))


def test_precommit_error_enters_corrective_phase_without_finish_proposal(tmp_path):
    agent, task, tools, _ = setup(tmp_path, faults=Faults(transient_errors=1))
    report = agent.run(task)
    assert report.original_claimed_success is False and report.claimed_success
    assert report.corrective_admissions == report.repeat_write_attempts == 1
    assert StateVerifier(tools.path).verify(task).passed


def test_postcommit_timeout_is_read_back_without_replaying_write(tmp_path):
    class LostAck(Sandbox):
        writes = 0

        def set_status(self, *args, **kwargs):
            self.writes += 1
            result = super().set_status(*args, **kwargs)
            if self.writes == 1:
                raise TimeoutError("lost acknowledgement")
            return result

    agent, task, tools, _ = setup(tmp_path, tools_class=LostAck)
    report = agent.run(task)
    assert report.claimed_success and report.original_claimed_success is False
    assert tools.writes == 1 and report.repeat_write_attempts == 0
    assert StateVerifier(tools.path).verify(task).passed


def test_persistent_drop_exhausts_shared_budget_honestly(tmp_path):
    agent, task, tools, _ = setup(tmp_path, faults=Faults(silent_drops=100))
    report = agent.run(task)
    assert not report.claimed_success and report.failure == "budget"
    assert report.actions <= 8 and report.decisions <= 8
    assert not StateVerifier(tools.path).verify(task).passed


@pytest.mark.parametrize("drops,claimed", [(0, True), (1, False)])
def test_two_target_finish_and_repair_share_the_same_eight_decisions(tmp_path, drops, claimed):
    agent, _, tools, _ = setup(tmp_path, faults=Faults(silent_drops=drops))
    task = Task(
        objective="Set ISSUE-1 and ISSUE-2 to done",
        requirements=tuple(Requirement(issue_id=f"ISSUE-{i}", status="done") for i in (1, 2)),
    )
    report = agent.run(task)
    assert report.claimed_success is claimed and report.decisions == 8
    assert report.failure == (None if claimed else "budget")
    # The dropped-write repair commits at the cap; no free confirmation/finish is granted.
    assert StateVerifier(tools.path).verify(task).passed


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_corrective_admission_cap(tmp_path, limit):
    agent, task, _, _ = setup(tmp_path, faults=Faults(transient_errors=100), max_reflections=limit)
    report = agent.run(task)
    assert report.failure == "budget" and not report.claimed_success
    assert report.corrective_admissions == limit


def test_zero_retry_budget_blocks_even_clean_corrective_claim(tmp_path):
    agent, task, tools, _ = setup(
        tmp_path, budget=Budget(max_actions=8, max_decisions=8, max_retries=0)
    )
    report = agent.run(task)
    assert report.original_claimed_success and not report.claimed_success
    assert report.corrective_admissions == 0 and report.failure == "budget"
    assert StateVerifier(tools.path).verify(task).passed


def test_no_trusted_oracle_or_raw_tool_text_reaches_provider(tmp_path, monkeypatch):
    class CanaryTools(Sandbox):
        def read_issue(self, issue_id):
            return super().read_issue(issue_id).model_copy(update={"title": "SECRET-CANARY"})

    agent, task, _, _ = setup(tmp_path, tools_class=CanaryTools)
    original = agent.provider.decide
    contexts = []

    def capture(task, state, **kwargs):
        contexts.append(state.model_dump_json())
        return original(task, state, **kwargs)

    def forbidden(*args):
        pytest.fail("Reflection must never invoke trusted verification")

    monkeypatch.setattr(agent.provider, "decide", capture)
    monkeypatch.setattr(StateVerifier, "verify", forbidden)
    assert agent.run(task).claimed_success
    assert all("SECRET-CANARY" not in context for context in contexts)
    assert all("verification" not in json.loads(context) for context in contexts)


def test_spoofed_ordinary_reads_can_still_produce_a_false_claim(tmp_path):
    class LyingTools(Sandbox):
        def read_issue(self, issue_id):
            return Issue(id=issue_id, title="reported", status="done", version=0)

    agent, task, tools, _ = setup(tmp_path, tools_class=LyingTools)
    report = agent.run(task)
    assert report.claimed_success and report.verified_success is None
    assert report.tool_writes == 0
    assert not StateVerifier(tools.path).verify(task).passed


@pytest.mark.parametrize(
    "action",
    [
        Action(tool="read_issue", issue_id="ISSUE-2"),
        Action(tool="set_status", issue_id="ISSUE-1", status="open"),
    ],
)
def test_task_authorization_precedes_execution(tmp_path, monkeypatch, action):
    agent, task, tools, _ = setup(tmp_path)
    monkeypatch.setattr(
        agent.provider, "decide", lambda *args, **kwargs: Decision(kind="action", action=action)
    )
    report = agent.run(task)
    assert report.failure == "permission" and report.actions == 0
    assert tools.read_issue("ISSUE-1").version == 0


@pytest.mark.parametrize("fresh_read,idempotent", [(False, True), (True, False)])
def test_repeated_writes_require_fresh_read_and_safe_policy(
    tmp_path, monkeypatch, fresh_read, idempotent
):
    agent, task, tools, _ = setup(tmp_path)
    write = Decision(
        kind="action", action=Action(tool="set_status", issue_id="ISSUE-1", status="done")
    )
    choices = [write, Decision(kind="finish")]
    if fresh_read:
        choices.append(
            Decision(kind="action", action=Action(tool="read_issue", issue_id="ISSUE-1"))
        )
    choices.append(write)
    sequence = iter(choices)
    agent.executor.policies["set_status"] = ToolPolicy(idempotent=idempotent)
    monkeypatch.setattr(agent.provider, "decide", lambda *args, **kwargs: next(sequence))
    report = agent.run(task)
    assert report.failure == "permission" and not report.claimed_success
    assert report.tool_writes == 1 and tools.read_issue("ISSUE-1").version == 1


def test_unsafe_cleanup_stops_without_correction(tmp_path, monkeypatch):
    agent, task, _, _ = setup(tmp_path)
    monkeypatch.setattr(
        agent.executor,
        "execute",
        lambda action, timeout: Observation(
            action=action, reported_success=False, failure="internal", safe_to_continue=False
        ),
    )
    report = agent.run(task)
    assert report.failure == "internal" and not report.claimed_success
    assert report.actions == 1 and report.corrective_admissions == 0


def test_late_decision_cannot_cause_a_write(tmp_path, monkeypatch):
    agent, task, tools, _ = setup(tmp_path, budget=Budget(timeout_seconds=1))
    clock = [0.0]
    monkeypatch.setattr("veriagent.reflection.time.monotonic", lambda: clock[0])

    def late(*args, **kwargs):
        clock[0] = 2.0
        return Decision(
            kind="action", action=Action(tool="set_status", issue_id="ISSUE-1", status="done")
        )

    monkeypatch.setattr(agent.provider, "decide", late)
    report = agent.run(task)
    assert report.failure == "budget" and report.actions == 0
    assert tools.read_issue("ISSUE-1").version == 0


@pytest.mark.parametrize("field", ["verification", "fault_schedule", "oracle_quota"])
def test_provider_context_forbids_hidden_fields(field):
    with pytest.raises(ValueError):
        ReflectionState(
            phase="execute",
            budget=Budget(),
            actions=0,
            decisions=0,
            corrective_admissions=0,
            **{field: None},
        )


@pytest.mark.parametrize("limit", [-1, 3, True, 1.0, "1"])
def test_corrective_limits_are_strict(tmp_path, limit):
    with pytest.raises(ValueError):
        setup(tmp_path, max_reflections=limit)


def test_live_or_unknown_provider_is_rejected_before_use(tmp_path):
    tools = Sandbox(tmp_path / "state.sqlite")
    with pytest.raises(TypeError, match="MockReflectionProvider"):
        ReflectionAgent(Executor(tools), TraceStore(tmp_path / "traces.sqlite"), provider=object())


def test_reused_stateless_mock_starts_fresh_run_counters(tmp_path):
    agent, task, _, _ = setup(tmp_path)
    first = agent.run(task)
    second = agent.run(task)
    assert first.run_id != second.run_id and second.claimed_success
    assert second.actions == 2 and second.corrective_admissions == 1
    assert type(agent.provider) is MockReflectionProvider


@pytest.mark.parametrize("field", ["model_calls", "model_tokens"])
@pytest.mark.parametrize("value", [False, True, 0.0, "0"])
def test_mock_report_counters_require_exact_integer_zero(field, value):
    payload = dict(
        run_id="run",
        original_claimed_success=None,
        claimed_success=False,
        actions=0,
        decisions=0,
        corrective_admissions=0,
        tool_writes=0,
        repeat_write_attempts=0,
        corrective_write_attempts=0,
        failure=None,
        elapsed_ms=0.0,
    )
    with pytest.raises(ValueError):
        ReflectionReport(**payload, **{field: value})


@pytest.mark.parametrize("version", [True, 1.0, "1"])
def test_reflection_report_versions_are_strict(version):
    with pytest.raises(ValueError):
        ReflectionReport(
            schema_version=version,
            run_id="run",
            original_claimed_success=None,
            claimed_success=False,
            actions=0,
            decisions=0,
            corrective_admissions=0,
            tool_writes=0,
            repeat_write_attempts=0,
            corrective_write_attempts=0,
            failure=None,
            elapsed_ms=0.0,
        )
