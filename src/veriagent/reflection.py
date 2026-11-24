"""Mock-only observation-based self-reflection prototype, without a trusted oracle."""

import time
from typing import Literal
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator

from veriagent.dynamic import normalized_feedback
from veriagent.executor import Executor
from veriagent.models import Action, ActionFeedback, Budget, Decision, Failure, Schema, Task
from veriagent.trace import TraceStore


class ReflectionState(Schema):
    phase: Literal["execute", "reflect"]
    feedback: tuple[ActionFeedback, ...] = Field(default=(), max_length=16)
    budget: Budget
    actions: int = Field(ge=0)
    decisions: int = Field(ge=0)
    corrective_admissions: int = Field(ge=0, le=2)


class ReflectionReport(Schema):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1
    comparator: Literal["mock_self_reflection"] = "mock_self_reflection"
    run_id: str
    original_claimed_success: bool | None
    claimed_success: bool
    verified_success: None = None
    actions: int
    decisions: int
    corrective_admissions: int
    tool_writes: int
    repeat_write_attempts: int
    corrective_write_attempts: int
    failure: Failure | None
    elapsed_ms: float
    model_calls: int = Field(default=0, strict=True, ge=0, le=0)
    model_tokens: int = Field(default=0, strict=True, ge=0, le=0)

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Schema version must be an integer")
        return value


class MockReflectionProvider:
    """A fixed decision rule, not an LLM or evidence of reflection quality."""

    def decide(self, task: Task, state: ReflectionState, *, timeout: float) -> Decision:
        if state.phase == "execute":
            for req in task.requirements:
                latest = next(
                    (f for f in reversed(state.feedback) if f.action.issue_id == req.issue_id), None
                )
                if latest and latest.reported_success:
                    if latest.action.tool == "set_status" or latest.observed_status == req.status:
                        continue
                    return Decision(
                        kind="action",
                        action=Action(tool="set_status", issue_id=req.issue_id, status=req.status),
                    )
                return Decision(
                    kind="action", action=Action(tool="read_issue", issue_id=req.issue_id)
                )
            return Decision(kind="finish")
        # Reflection uses only fresh reads in this corrective phase. Mutation acks
        # cannot substitute for a post-write observation.
        reads, writes = {}, {}
        for index, feedback in enumerate(state.feedback):
            if feedback.action.tool == "read_issue" and feedback.reported_success:
                reads[feedback.action.issue_id] = (index, feedback.observed_status)
            elif feedback.action.tool == "set_status":
                writes[feedback.action.issue_id] = index
        for req in task.requirements:
            latest = reads.get(req.issue_id)
            if latest is None or latest[0] < writes.get(req.issue_id, -1) or latest[1] is None:
                return Decision(
                    kind="action", action=Action(tool="read_issue", issue_id=req.issue_id)
                )
        for req in task.requirements:
            if reads[req.issue_id][1] != req.status:
                return Decision(
                    kind="action",
                    action=Action(tool="set_status", issue_id=req.issue_id, status=req.status),
                )
        return Decision(kind="finish")


class ReflectionAgent:
    """Explicit Python prototype; no verifier argument, live provider or new Mode."""

    def __init__(
        self,
        executor: Executor,
        traces: TraceStore,
        budget: Budget | None = None,
        *,
        provider: MockReflectionProvider | None = None,
        max_reflections: int | None = None,
    ):
        self.executor, self.traces = executor, traces
        self.budget = budget or Budget(max_actions=8, max_decisions=8)
        self.provider = provider if provider is not None else MockReflectionProvider()
        if type(self.provider) is not MockReflectionProvider:
            raise TypeError("Prototype accepts only MockReflectionProvider")
        limit = min(2, self.budget.max_retries) if max_reflections is None else max_reflections
        if type(limit) is not int or not 0 <= limit <= min(2, self.budget.max_retries):
            raise ValueError(
                "Corrective admissions must fit the shared retry cap and be at most two"
            )
        self.max_reflections = limit

    def run(self, task: Task) -> ReflectionReport:
        if not isinstance(task, Task):
            raise TypeError("Expected validated original Task")
        task = Task.model_validate_json(task.model_dump_json(), strict=True)
        start = time.monotonic()
        deadline = start + self.budget.timeout_seconds
        run_id = uuid4().hex
        self.traces.append(run_id, "task", task)
        self.traces.append(
            run_id,
            "configuration",
            {
                "comparator": "mock_self_reflection",
                "budget": self.budget.model_dump(mode="json"),
                "max_reflections": self.max_reflections,
                "trusted_oracle_access": False,
            },
        )
        phase = "execute"
        feedback = []
        phase_start = actions = decisions = admissions = 0
        writes = {}
        last_reads = {}
        repeat_writes = corrective_writes = 0
        original_claim = None
        claimed = False
        failure = None

        def admit(trigger):
            nonlocal phase, phase_start, admissions, failure
            if (
                admissions >= self.max_reflections
                or actions >= self.budget.max_actions
                or (decisions >= self.budget.max_decisions or time.monotonic() >= deadline)
            ):
                failure = Failure.BUDGET
                self.traces.append(run_id, "reflection_stopped", {"reason": "admission_budget"})
                return False
            admissions += 1
            self.traces.append(
                run_id,
                "reflection_transition",
                {
                    "from_phase": phase,
                    "to_phase": "reflect",
                    "trigger": trigger,
                    "corrective_admission": admissions,
                },
            )
            phase, phase_start = "reflect", len(feedback)
            return True

        while failure is None and not claimed:
            if (
                actions >= self.budget.max_actions
                or decisions >= self.budget.max_decisions
                or (time.monotonic() >= deadline)
            ):
                failure = Failure.BUDGET
                break
            state = ReflectionState(
                phase=phase,
                feedback=tuple(
                    feedback[phase_start:][-16:] if phase == "reflect" else feedback[-16:]
                ),
                budget=self.budget,
                actions=actions,
                decisions=decisions,
                corrective_admissions=admissions,
            )
            self.traces.append(run_id, "reflection_context", state)
            decisions += 1
            try:
                raw = self.provider.decide(task, state, timeout=deadline - time.monotonic())
                decision = Decision.model_validate_json(raw.model_dump_json(), strict=True)
            except Exception:
                failure = Failure.PLANNING
                self.traces.append(run_id, "reflection_decision_error", {"failure": failure.value})
                break
            self.traces.append(run_id, "reflection_decision", decision)
            if time.monotonic() >= deadline:
                failure = Failure.BUDGET
                break
            if decision.kind == "finish":
                self.traces.append(
                    run_id, "reflection_claim", {"phase": phase, "claimed_success": True}
                )
                if phase == "reflect":
                    claimed = True  # A provider claim, never trusted final-state verification.
                    break
                original_claim = True
                if not admit("finish_proposal"):
                    break
                continue
            action = decision.action
            try:
                self.executor.authorize(task, action)
                if (
                    action.tool == "set_status"
                    and action.issue_id in writes
                    and (
                        phase != "reflect"
                        or not self.executor.retry_safe(action)
                        or last_reads.get(action.issue_id, -1) <= writes[action.issue_id]
                    )
                ):
                    raise PermissionError("Repeated write lacks a fresh read or safe retry policy")
            except PermissionError:
                failure = Failure.PERMISSION
                self.traces.append(run_id, "reflection_action_denied", {"failure": failure.value})
                break
            self.traces.append(run_id, "action", action)
            observation = self.executor.execute(
                action, min(self.budget.action_timeout_seconds, deadline - time.monotonic())
            )
            actions += 1
            feedback.append(normalized_feedback(observation))
            self.traces.append(run_id, "observation", observation)
            if action.tool == "read_issue" and observation.reported_success:
                last_reads[action.issue_id] = actions
            if action.tool == "set_status":
                repeat_writes += action.issue_id in writes
                corrective_writes += phase == "reflect"
                writes[action.issue_id] = actions
            if not observation.safe_to_continue:
                failure = Failure.INTERNAL
                break
            if not observation.reported_success:
                if original_claim is None:
                    original_claim = False
                if observation.failure in {Failure.TRANSIENT, Failure.TIMEOUT}:
                    if not admit("recoverable_tool_failure"):
                        break
                else:
                    failure = observation.failure or Failure.INTERNAL
        report = ReflectionReport(
            run_id=run_id,
            original_claimed_success=original_claim,
            claimed_success=claimed,
            actions=actions,
            decisions=decisions,
            corrective_admissions=admissions,
            tool_writes=sum(f.action.tool == "set_status" for f in feedback),
            repeat_write_attempts=repeat_writes,
            corrective_write_attempts=corrective_writes,
            failure=failure,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )
        self.traces.append(run_id, "reflection_report", report)
        return report
