"""Opt-in trusted-verifier admission adapter; agents do not enable it implicitly."""

from pathlib import Path

from veriagent.models import Task, Verification
from veriagent.verification import StateVerifier
from veriagent.verification_budget import VerificationBudgetLedger


class BudgetedStateVerifier:
    """Reserve original task targets before delegating any trusted database read.

    Use a fresh ledger per sequential execution run. Final evaluation should use its
    own ordinary StateVerifier, outside this execution allowance. Exceptions propagate;
    no agent outcome or trace mapping is introduced by the adapter.
    """

    def __init__(self, path: Path, ledger: VerificationBudgetLedger):
        if not isinstance(ledger, VerificationBudgetLedger):
            raise TypeError("Expected VerificationBudgetLedger")
        self.ledger = ledger
        self._verifier = StateVerifier(path)

    def verify(self, task: Task) -> Verification:
        if not isinstance(task, Task):
            raise TypeError("Expected original validated Task")
        targets = {requirement.issue_id: requirement.status for requirement in task.requirements}
        if not targets or len(targets) != len(task.requirements):
            raise ValueError("Verification requires unique original targets")
        reservation = self.ledger.reserve(len(targets))
        try:
            result = self._verifier.verify(task)
            if (
                not isinstance(result, Verification)
                or len(result.evidence) != len(targets)
                or {row.issue_id: row.expected for row in result.evidence} != targets
                or result.passed != all(row.actual == row.expected for row in result.evidence)
            ):
                raise ValueError(
                    "Trusted verification returned incomplete or inconsistent evidence"
                )
            self.ledger.complete(reservation, observed_target_rows=len(result.evidence))
        except BaseException:
            # Includes cancellation: admitted work may already have read some targets.
            self.ledger.fail(reservation)
            raise
        return result
