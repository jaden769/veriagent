"""Provider boundary; deliberately narrow and deterministic Phase 1 planning."""

import re
from typing import Protocol

from veriagent.models import Action, ModelUsage, Plan, Requirement, Status, Step, Task


class PlanningProvider(Protocol):
    """Phase 2 providers can implement this without changing execution or verification.

    A real provider must validate structured output, meter usage, use bounded API
    timeouts, and obtain credentials from the environment. No paid calls in Phase 1.
    """

    def parse(self, objective: str) -> Task: ...

    @property
    def usage(self) -> ModelUsage: ...

    def plan(self, task: Task, *, timeout: float | None = None) -> Plan: ...


class MockProvider:
    @property
    def usage(self) -> ModelUsage:
        return ModelUsage()

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
