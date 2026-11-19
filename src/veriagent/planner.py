"""Provider boundary; deliberately narrow and deterministic Phase 1 planning."""

import re
from typing import Protocol

from veriagent.interpretation import interpret_offline
from veriagent.models import (
    Action,
    Decision,
    DecisionState,
    Interpretation,
    ModelBudgetState,
    ModelUsage,
    Plan,
    ProviderDiagnostic,
    Requirement,
    Status,
    Step,
    Task,
)


class PlanningProvider(Protocol):
    @property
    def diagnostic(self) -> ProviderDiagnostic | None: ...

    """Phase 2 providers can implement this without changing execution or verification.

    A real provider must validate structured output, meter usage, use bounded API
    timeouts, and obtain credentials from the environment. No paid calls in Phase 1.
    """

    def parse(self, objective: str) -> Task: ...

    def begin_run(self) -> None: ...

    @property
    def budget_state(self) -> ModelBudgetState | None: ...

    @property
    def usage(self) -> ModelUsage: ...

    def plan(self, task: Task, *, timeout: float | None = None) -> Plan: ...


class MockProvider:
    @property
    def diagnostic(self) -> ProviderDiagnostic | None:
        return None

    def begin_run(self) -> None:
        pass

    @property
    def budget_state(self) -> ModelBudgetState | None:
        return None

    @property
    def usage(self) -> ModelUsage:
        return ModelUsage()

    def interpret(self, objective: str, *, timeout: float | None = None) -> Interpretation:
        return interpret_offline(objective)

    def decide(self, task: Task, state: DecisionState, *, timeout: float | None = None) -> Decision:
        verified = (
            {e.issue_id: e.actual for e in state.verification.evidence}
            if state.verification
            else {}
        )
        for req in task.requirements:
            if verified.get(req.issue_id) == req.status:
                continue
            latest = next(
                (f for f in reversed(state.feedback) if f.action.issue_id == req.issue_id), None
            )
            if latest and latest.reported_success:
                if latest.action.tool == "read_issue":
                    if latest.observed_status == req.status:
                        continue
                    return Decision(
                        kind="action",
                        action=Action(tool="set_status", issue_id=req.issue_id, status=req.status),
                    )
                if state.verification is None:
                    # Baseline deliberately accepts successful mutation acknowledgments.
                    continue
            return Decision(kind="action", action=Action(tool="read_issue", issue_id=req.issue_id))
        return Decision(kind="finish")

    def parse(self, objective: str) -> Task:
        # Full-match prevents ignored trailing instructions or partial interpretations.
        match = re.fullmatch(
            r"\s*(?:set|mark)\s+(ISSUE-\d+(?:\s*,\s*ISSUE-\d+)*)\s+"
            r"(?:to|as)\s+(open|in_progress|done)\s*\.?\s*",
            objective,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("Use: Set ISSUE-1, ISSUE-2 to done (or open / in_progress)")
        targets, status = match.groups()
        return Task(
            objective=objective,
            requirements=tuple(
                Requirement(issue_id=target.strip().upper(), status=Status(status.lower()))
                for target in targets.split(",")
            ),
        )

    def plan(self, task: Task, *, timeout: float | None = None) -> Plan:
        return Plan(
            steps=tuple(
                Step(
                    id=f"step-{i}",
                    action=Action(tool="set_status", issue_id=req.issue_id, status=req.status),
                    expected=req,
                )
                for i, req in enumerate(task.requirements, start=1)
            )
        )
