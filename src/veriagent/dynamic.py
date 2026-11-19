"""Observation-driven decisions with independent verification and bounded repair."""

import time
from typing import Protocol
from uuid import uuid4

from veriagent.budgeting import ModelBudgetExceeded
from veriagent.executor import Executor
from veriagent.interpretation import proposal_digest
from veriagent.models import (
    ActionFeedback,
    Budget,
    Decision,
    DecisionState,
    Failure,
    Mode,
    ModelBudgetState,
    ModelUsage,
    Observation,
    RunReport,
    Status,
    Task,
    TaskProposal,
)
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


class DecisionProvider(Protocol):
    def begin_run(self) -> None: ...

    @property
    def budget_state(self) -> ModelBudgetState | None: ...

    @property
    def usage(self) -> ModelUsage: ...

    def decide(
        self, task: Task, state: DecisionState, *, timeout: float | None = None
    ) -> Decision: ...


def add_usage(total: ModelUsage, current: ModelUsage) -> ModelUsage:
    if current.calls == 0:
        return total

    def add(a, b):
        return None if a is None or b is None else a + b

    model = (
        current.model
        if not total.calls
        else (total.model if total.model == current.model else None)
    )
    return ModelUsage(
        provider=current.provider,
        model=model,
        calls=total.calls + current.calls,
        input_tokens=add(total.input_tokens, current.input_tokens),
        output_tokens=add(total.output_tokens, current.output_tokens),
        estimated_cost_usd=add(total.estimated_cost_usd, current.estimated_cost_usd),
    )


def normalized_feedback(observation: Observation) -> ActionFeedback:
    status = None
    if observation.action.tool == "read_issue" and observation.reported_success:
        try:
            status = Status(observation.data.get("status"))
        except (ValueError, TypeError):
            pass
    return ActionFeedback(
        action=observation.action,
        reported_success=observation.reported_success,
        failure=observation.failure,
        observed_status=status,
    )


class DynamicAgent:
    def __init__(
        self,
        provider: DecisionProvider,
        executor: Executor,
        verifier: StateVerifier,
        traces: TraceStore,
        budget: Budget | None = None,
    ):
        self.provider, self.executor, self.verifier, self.traces = (
            provider,
            executor,
            verifier,
            traces,
        )
        self.budget = budget or Budget()

    def run(
        self,
        task: Task,
        mode: Mode = Mode.RECOVER,
        *,
        reviewed_proposal: TaskProposal | None = None,
    ) -> RunReport:
        if reviewed_proposal is not None and reviewed_proposal.task() != task:
            raise ValueError("Reviewed proposal does not match the execution task")
        self.provider.begin_run()
        start = time.monotonic()
        deadline = start + self.budget.timeout_seconds
        run_id = uuid4().hex
        self.traces.append(run_id, "task", task)
        if reviewed_proposal is not None:
            self.traces.append(
                run_id,
                "requirements_review",
                {
                    "proposal_digest": proposal_digest(reviewed_proposal),
                    "interpretation_usage": reviewed_proposal.interpretation_usage.model_dump(
                        mode="json"
                    ),
                },
            )
        self.traces.append(
            run_id,
            "configuration",
            {
                "engine": "dynamic",
                "mode": mode.value,
                "budget": self.budget.model_dump(mode="json"),
            },
        )
        metadata = self.provider.usage
        usage = ModelUsage(provider=metadata.provider, model=metadata.model)
        feedback: list[ActionFeedback] = []
        writes: dict[str, int] = {}
        retry_allowed: set[str] = set()
        actions = decisions = retries = 0
        verification = None
        failure = None
        claimed = False

        def verify() -> bool:
            nonlocal verification, failure
            try:
                verification = self.verifier.verify(task)
                self.traces.append(run_id, "verification", verification)
                return True
            except Exception:
                verification = None
                failure = Failure.INTERNAL
                self.traces.append(run_id, "verification_error", {"failure": failure.value})
                return False

        if mode != Mode.BASELINE:
            if not verify():
                failure = Failure.INTERNAL
            elif verification.passed:
                claimed = True
            elif verification.failure == Failure.NOT_FOUND:
                failure = Failure.NOT_FOUND

        while not claimed and failure is None:
            if (
                actions >= self.budget.max_actions
                or decisions >= self.budget.max_decisions
                or time.monotonic() >= deadline
            ):
                failure = Failure.BUDGET
                break
            state = DecisionState(
                budget=self.budget,
                feedback=tuple(feedback[-16:]),
                verification=verification,
                actions=actions,
                recovery_attempts=retries,
                decisions=decisions,
            )
            self.traces.append(run_id, "decision_context", state)
            decisions += 1
            try:
                decision = self.provider.decide(task, state, timeout=deadline - time.monotonic())
            except Exception as exc:
                usage = add_usage(usage, self.provider.usage)
                self.traces.append(run_id, "model_usage", self.provider.usage)
                if self.provider.budget_state is not None:
                    self.traces.append(run_id, "model_budget", self.provider.budget_state)
                failure = (
                    Failure.BUDGET
                    if isinstance(exc, ModelBudgetExceeded) or (time.monotonic() >= deadline)
                    else Failure.PLANNING
                )
                self.traces.append(run_id, "decision_error", {"failure": failure.value})
                break
            usage = add_usage(usage, self.provider.usage)
            self.traces.append(run_id, "model_usage", self.provider.usage)
            if self.provider.budget_state is not None:
                self.traces.append(run_id, "model_budget", self.provider.budget_state)
            self.traces.append(run_id, "decision", decision)
            if time.monotonic() >= deadline:
                failure = Failure.BUDGET
                break
            observation = None
            if decision.kind == "finish":
                if mode == Mode.BASELINE:
                    claimed = True
                    break
            else:
                action = decision.action
                assert action is not None
                try:
                    self.executor.authorize(task, action)
                    if action.tool == "set_status":
                        if verification and any(
                            e.issue_id == action.issue_id and e.actual == e.expected
                            for e in verification.evidence
                        ):
                            raise PermissionError("Cannot rewrite a verified completed target")
                        if writes.get(action.issue_id, 0) and (
                            mode != Mode.RECOVER
                            or action.issue_id not in retry_allowed
                            or not self.executor.retry_safe(action)
                        ):
                            raise PermissionError(
                                "Repeated write has no safe recovery authorization"
                            )
                except PermissionError:
                    failure = Failure.PERMISSION
                    self.traces.append(
                        run_id,
                        "action_rejected",
                        {"action": action.model_dump(mode="json"), "failure": failure.value},
                    )
                    break
                if action.tool == "set_status":
                    writes[action.issue_id] = writes.get(action.issue_id, 0) + 1
                    retry_allowed.discard(action.issue_id)
                self.traces.append(run_id, "action", action)
                observation = self.executor.execute(
                    action, min(self.budget.action_timeout_seconds, deadline - time.monotonic())
                )
                actions += 1
                feedback.append(normalized_feedback(observation))
                self.traces.append(run_id, "observation", observation)
                if mode == Mode.BASELINE:
                    if not observation.reported_success:
                        failure = observation.failure or Failure.INTERNAL
                    continue
                if action.tool == "read_issue" and observation.reported_success:
                    continue
            if not verify():
                break
            if verification.passed:
                claimed = True
                break
            # An unfinished multi-issue task is normal if this particular write persisted.
            if (
                observation
                and observation.reported_success
                and any(
                    e.issue_id == observation.action.issue_id and e.actual == e.expected
                    for e in verification.evidence
                )
            ):
                continue
            cause = (
                observation.failure if observation and observation.failure else verification.failure
            )
            if cause not in {Failure.STATE_MISMATCH, Failure.TRANSIENT, Failure.TIMEOUT}:
                failure = cause or Failure.INTERNAL
                break
            if mode != Mode.RECOVER or retries >= self.budget.max_retries:
                failure = cause
                self.traces.append(run_id, "recovery_stopped", {"reason": "mode_or_retry_limit"})
                break
            if observation and observation.action.tool == "set_status":
                if not self.executor.retry_safe(observation.action):
                    failure = cause
                    self.traces.append(run_id, "recovery_stopped", {"reason": "unsafe_retry"})
                    break
                retry_allowed.add(observation.action.issue_id)
            if (
                actions >= self.budget.max_actions
                or decisions >= self.budget.max_decisions
                or time.monotonic() >= deadline
            ):
                failure = Failure.BUDGET
                break
            retries += 1
            self.traces.append(run_id, "recovery", {"attempt": retries, "reason": cause.value})
        report = RunReport(
            run_id=run_id,
            mode=mode,
            engine="dynamic",
            claimed_success=claimed,
            verified_success=verification.passed if verification is not None else None,
            actions=actions,
            decisions=decisions,
            recovery_attempts=retries,
            elapsed_ms=(time.monotonic() - start) * 1000,
            failure=failure,
            verification=verification,
            model_calls=usage.calls,
            model_tokens=usage.total_tokens,
            estimated_cost_usd=usage.estimated_cost_usd,
            model_usage=usage,
            model_budget=self.provider.budget_state,
        )
        self.traces.append(run_id, "report", report)
        return report
