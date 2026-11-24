"""Explicit execution / observation / verification / bounded recovery loop."""

import time
from uuid import uuid4

from veriagent.bounded_verification import (
    prepare_verification_run,
    verification_configuration,
    verify_for_run,
)
from veriagent.budgeting import ModelBudgetExceeded
from veriagent.executor import Executor
from veriagent.interpretation import proposal_digest
from veriagent.models import Budget, Failure, Mode, Observation, Plan, RunReport, Task, TaskProposal
from veriagent.planner import PlanningProvider
from veriagent.recovery import RecoveryPolicy
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier
from veriagent.verification_budget import VerificationBudgetExceeded


class Agent:
    def __init__(
        self,
        provider: PlanningProvider,
        executor: Executor,
        verifier: StateVerifier,
        traces: TraceStore,
        budget: Budget | None = None,
    ):
        self.provider = provider
        self.executor = executor
        self.verifier = verifier
        self.traces = traces
        self.budget = budget or Budget()

    @staticmethod
    def validate_plan(task: Task, plan: Plan) -> None:
        targets = {(r.issue_id, r.status) for r in task.requirements}
        writes = set()
        for step in plan.steps:
            action = step.action
            if (step.expected.issue_id, step.expected.status) not in targets:
                raise ValueError("Plan expectation is outside the authorized task")
            if action.issue_id != step.expected.issue_id:
                raise ValueError("Action and expected outcome disagree")
            if action.tool == "set_status":
                if action.status != step.expected.status:
                    raise ValueError("Plan attempts an unauthorized state change")
                writes.add((action.issue_id, action.status))
        if writes != targets:
            raise ValueError("Plan does not cover all task requirements")

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
        prepare_verification_run(self.verifier, task, run_id)
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
                "mode": mode.value,
                "budget": self.budget.model_dump(),
                "tool_execution": self.executor.execution_mode,
                **verification_configuration(self.verifier),
            },
        )
        try:
            plan = self.provider.plan(task, timeout=deadline - time.monotonic())
            self.validate_plan(task, plan)
        except Exception as exc:
            failure = (
                Failure.BUDGET
                if isinstance(exc, ModelBudgetExceeded) or (time.monotonic() >= deadline)
                else Failure.PLANNING
            )
            self.traces.append(run_id, "planning_error", {"failure": failure.value})
            usage = self.provider.usage
            self.traces.append(run_id, "model_usage", usage)
            if self.provider.diagnostic is not None:
                self.traces.append(run_id, "provider_diagnostic", self.provider.diagnostic)
            if self.provider.budget_state is not None:
                self.traces.append(run_id, "model_budget", self.provider.budget_state)
            report = RunReport(
                run_id=run_id,
                mode=mode,
                claimed_success=False,
                verified_success=None,
                actions=0,
                recovery_attempts=0,
                elapsed_ms=(time.monotonic() - start) * 1000,
                failure=failure,
                model_calls=usage.calls,
                model_tokens=usage.total_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
                model_usage=usage,
                model_budget=self.provider.budget_state,
                tool_execution=self.executor.execution_mode,
                provider_diagnostic=self.provider.diagnostic,
            )
            self.traces.append(run_id, "report", report)
            return report
        self.traces.append(run_id, "model_usage", self.provider.usage)
        if self.provider.diagnostic is not None:
            self.traces.append(run_id, "provider_diagnostic", self.provider.diagnostic)
        if self.provider.budget_state is not None:
            self.traces.append(run_id, "model_budget", self.provider.budget_state)
        self.traces.append(run_id, "plan", plan)
        actions = retries = 0
        verification = None
        failure = None
        observations: dict[str, Observation] = {}
        claimed = False
        unsafe_execution = False
        while True:
            completed: set[str] = set()
            for step in plan.steps:
                if actions >= self.budget.max_actions or time.monotonic() >= deadline:
                    failure = Failure.BUDGET
                    break
                if not set(step.depends_on) <= completed:
                    failure = Failure.DEPENDENCY
                    self.traces.append(run_id, "step_skipped", {"step_id": step.id})
                    continue
                self.traces.append(
                    run_id,
                    "action",
                    {"step_id": step.id, "action": step.action.model_dump(mode="json")},
                )
                observation = self.executor.execute(
                    step.action,
                    min(self.budget.action_timeout_seconds, deadline - time.monotonic()),
                )
                actions += 1
                observations[step.id] = observation
                self.traces.append(run_id, "observation", observation)
                if not observation.safe_to_continue:
                    failure = Failure.INTERNAL
                    verification = None
                    unsafe_execution = True
                    self.traces.append(
                        run_id, "execution_stopped", {"reason": "worker_cleanup_unconfirmed"}
                    )
                    break
                if observation.reported_success:
                    completed.add(step.id)
                else:
                    failure = observation.failure
            claimed = failure is None and len(completed) == len(plan.steps)
            if unsafe_execution:
                break
            if mode == Mode.BASELINE:
                break
            try:
                verification = verify_for_run(self.verifier, task, self.traces, run_id)
                self.traces.append(run_id, "verification", verification)
            except VerificationBudgetExceeded as exc:
                verification = None
                failure = Failure.BUDGET
                claimed = False
                self.traces.append(
                    run_id, "verification_denied", {"failure": failure.value, "reason": str(exc)}
                )
                break
            except Exception:
                # Missing/unreadable evidence must never become a success claim.
                failure = Failure.INTERNAL
                claimed = False
                self.traces.append(run_id, "verification_error", {"failure": failure.value})
                break
            if verification.passed:
                claimed = True
                failure = None
                break
            claimed = False
            failure = failure or verification.failure
            if mode == Mode.VERIFY:
                break
            if retries >= self.budget.max_retries:
                self.traces.append(run_id, "recovery_stopped", {"reason": "retry_limit"})
                break
            if actions >= self.budget.max_actions or time.monotonic() >= deadline:
                failure = Failure.BUDGET
                self.traces.append(run_id, "recovery_stopped", {"reason": "execution_budget"})
                break
            revised = RecoveryPolicy().revise(plan, verification, observations, self.executor)
            if revised is None:
                self.traces.append(run_id, "recovery_stopped", {"reason": "unsafe_or_persistent"})
                break
            retries += 1
            self.traces.append(
                run_id,
                "recovery",
                {"attempt": retries, "reason": failure.value if failure else None},
            )
            plan = revised
            self.traces.append(run_id, "plan", plan)
            failure = None
        report = RunReport(
            run_id=run_id,
            mode=mode,
            claimed_success=claimed,
            verified_success=verification.passed if verification else None,
            actions=actions,
            recovery_attempts=retries,
            elapsed_ms=(time.monotonic() - start) * 1000,
            failure=failure,
            verification=verification,
            model_calls=self.provider.usage.calls,
            model_tokens=self.provider.usage.total_tokens,
            estimated_cost_usd=self.provider.usage.estimated_cost_usd,
            model_usage=self.provider.usage,
            model_budget=self.provider.budget_state,
            tool_execution=self.executor.execution_mode,
            provider_diagnostic=self.provider.diagnostic,
        )
        self.traces.append(run_id, "report", report)
        return report
