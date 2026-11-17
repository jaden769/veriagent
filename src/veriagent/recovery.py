"""Conservative failure classification and bounded, selective plan revision."""

from veriagent.executor import Executor
from veriagent.models import Failure, Observation, Plan, Verification


class RecoveryPolicy:
    recoverable = frozenset({Failure.TRANSIENT, Failure.STATE_MISMATCH, Failure.TIMEOUT})

    def revise(
        self,
        plan: Plan,
        verification: Verification,
        observations: dict[str, Observation],
        executor: Executor,
    ) -> Plan | None:
        if verification.failure not in self.recoverable:
            return None
        mismatched = {e.issue_id for e in verification.evidence if e.actual != e.expected}
        steps = []
        for step in plan.steps:
            if step.action.issue_id not in mismatched:
                continue
            observation = observations.get(step.id)
            if observation and observation.failure not in self.recoverable | {None}:
                return None
            if not executor.retry_safe(step.action):
                return None
            steps.append(step)
        if not steps:
            return None
        # Dependencies outside this revision were already satisfied and verified.
        pending = {s.id for s in steps}
        return Plan(
            revision=plan.revision + 1,
            steps=tuple(
                s.model_copy(update={"depends_on": tuple(d for d in s.depends_on if d in pending)})
                for s in steps
            ),
        )
