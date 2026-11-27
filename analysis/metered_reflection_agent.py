"""Separate injected metered controller and native report; no live entry point."""

import time
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from analysis.metered_reflection_provider import MeteredReflectionProvider
from veriagent.budgeting import ModelBudgetExceeded
from veriagent.dynamic import normalized_feedback
from veriagent.executor import Executor
from veriagent.models import (
    Budget,
    Decision,
    Failure,
    ModelBudgetState,
    ModelUsage,
    ProviderDiagnostic,
    Task,
)
from veriagent.reflection import ReflectionReport, ReflectionState
from veriagent.trace import TraceStore


class MeteredReflectionReport(ReflectionReport):
    comparator: Literal["llm_self_reflection"] = "llm_self_reflection"
    model_calls: int = Field(default=0, strict=True, ge=0)
    model_tokens: int | None = Field(default=None, strict=True, ge=0)
    request_attempts: int = Field(strict=True, ge=0)
    model_usage: ModelUsage
    model_budget_state: ModelBudgetState
    request_state: dict
    provider_diagnostic: ProviderDiagnostic | None

    @model_validator(mode="after")
    def accounting(self):
        if self.request_state.get("pending") is not False:
            raise ValueError("Terminal report contains pending work")
        if (
            type(self.request_state.get("request_attempts")) is not int
            or self.request_state["request_attempts"] != self.request_attempts
        ):
            raise ValueError("Report request state differs from charged attempts")
        if self.claimed_success and (self.model_tokens is None or self.request_attempts == 0):
            raise ValueError("Metered finish requires accounted request usage")
        if any(
            value < 0
            for value in (
                self.actions,
                self.decisions,
                self.corrective_admissions,
                self.tool_writes,
                self.repeat_write_attempts,
                self.corrective_write_attempts,
            )
        ):
            raise ValueError("Negative metered execution counter")
        if self.corrective_admissions > 2 or self.claimed_success and self.failure is not None:
            raise ValueError("Invalid metered terminal state")
        if self.comparator != "llm_self_reflection" or self.model_calls != self.request_attempts:
            raise ValueError("Invalid metered report identity or request count")
        if (
            self.model_calls != self.model_usage.calls
            or self.model_tokens != self.model_usage.total_tokens
        ):
            raise ValueError("Usage summary differs from cumulative accounting")
        if self.model_usage != self.model_budget_state.usage:
            raise ValueError("Report ledger differs from cumulative usage")
        return self


class MeteredReflectionAgent:
    """Injected metered controller; no verifier argument, SDK factory or new Mode."""

    def __init__(
        self,
        executor: Executor,
        traces: TraceStore,
        budget: Budget | None = None,
        *,
        provider: MeteredReflectionProvider,
        max_reflections: int | None = None,
    ):
        self.executor, self.traces = executor, traces
        self.budget = budget or Budget(max_actions=8, max_decisions=8)
        self.provider = provider
        if type(self.provider) is not MeteredReflectionProvider:
            raise TypeError("Require an explicit injected MeteredReflectionProvider")
        limit = min(2, self.budget.max_retries) if max_reflections is None else max_reflections
        if type(limit) is not int or not 0 <= limit <= min(2, self.budget.max_retries):
            raise ValueError(
                "Corrective admissions must fit the shared retry cap and be at most two"
            )
        self.max_reflections = limit

    def run(self, task: Task) -> MeteredReflectionReport:
        if not isinstance(task, Task):
            raise TypeError("Expected validated original Task")
        task = Task.model_validate_json(task.model_dump_json(), strict=True)
        self.provider.begin_run()
        start = time.monotonic()
        deadline = start + self.budget.timeout_seconds
        run_id = uuid4().hex
        self.traces.append(run_id, "task", task)
        self.traces.append(
            run_id,
            "configuration",
            {
                "comparator": "llm_self_reflection",
                "budget": self.budget.model_dump(mode="json"),
                "max_reflections": self.max_reflections,
                "trusted_oracle_access": False,
                "provider": dict(
                    model=self.provider.model,
                    limits=self.provider.ledger.limits.model_dump(mode="json"),
                    prices=list(self.provider.prices),
                ),
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
                raw = self._decide(task, state, timeout=deadline - time.monotonic(), run_id=run_id)
                decision = Decision.model_validate_json(raw.model_dump_json(), strict=True)
            except Exception as exc:
                failure = (
                    Failure.BUDGET
                    if isinstance(exc, ModelBudgetExceeded)
                    else Failure.PERMISSION
                    if isinstance(exc, PermissionError)
                    else Failure.PLANNING
                )
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
        report = MeteredReflectionReport(
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
            model_calls=self.provider.budget_state.usage.calls,
            model_tokens=self.provider.budget_state.usage.total_tokens,
            request_attempts=self.provider.ledger.state["request_attempts"],
            model_usage=self.provider.budget_state.usage,
            model_budget_state=self.provider.budget_state,
            request_state=self.provider.ledger.state,
            provider_diagnostic=self.provider.diagnostic,
        )
        self.traces.append(run_id, "metered_reflection_report", report)
        return report

    def _decide(self, task, state, *, timeout, run_id):
        before = self.provider.ledger.state
        outcome = "planning"
        try:
            decision = self.provider.decide(task, state, timeout=timeout)
            outcome = "decision"
            return decision
        except ModelBudgetExceeded:
            outcome = "budget"
            raise
        except PermissionError:
            outcome = "permission"
            raise
        except BaseException as exc:
            outcome = "planning" if isinstance(exc, Exception) else "cancelled"
            raise
        finally:
            after = self.provider.ledger.state
            dispatched = after["request_attempts"] > before["request_attempts"]
            self.traces.append(
                run_id,
                "metered_decision_accounting",
                dict(
                    before=before,
                    after=after,
                    outcome=outcome,
                    dispatch=self.provider.ledger.last_dispatch if dispatched else None,
                    diagnostic=self.provider.diagnostic.model_dump(mode="json")
                    if self.provider.diagnostic
                    else None,
                ),
            )
