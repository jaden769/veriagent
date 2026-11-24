"""Opt-in trusted-verifier admission adapter; agents do not enable it implicitly."""

from dataclasses import asdict
from pathlib import Path

from veriagent.models import Task, Verification
from veriagent.verification import StateVerifier
from veriagent.verification_budget import VerificationBudgetExceeded, VerificationBudgetLedger


class BudgetedStateVerifier:
    """Reserve original task targets before delegating any trusted database read.

    Use a fresh ledger per sequential execution run. Final evaluation should use its
    own ordinary StateVerifier, outside this execution allowance. Exceptions propagate;
    opt-in agent integration records admission state and maps denial separately.
    """

    def __init__(self, path: Path, ledger: VerificationBudgetLedger):
        if not isinstance(ledger, VerificationBudgetLedger):
            raise TypeError("Expected VerificationBudgetLedger")
        self.ledger = ledger
        self._verifier = StateVerifier(path)
        self._run_id = self._task = None

    def bind_run(self, task: Task, run_id: str):
        if self._run_id is not None or self.ledger.state["reserved_calls"]:
            raise ValueError("Budgeted verifier requires a fresh ledger and adapter per agent run")
        self._run_id, self._task = run_id, task

    def configuration(self):
        return {"verification_limits": asdict(self.ledger.limits)}

    def verify(self, task: Task) -> Verification:
        return self._verify(task)

    def verify_traced(self, task: Task, traces, run_id: str) -> Verification:
        if self._run_id != run_id or task != self._task:
            raise ValueError("Verification does not match its bound run and original task")
        return self._verify(
            task,
            lambda phase, **payload: traces.append(
                run_id,
                "verification_budget",
                {"phase": phase, **payload, "state": self.ledger.state},
            ),
        )

    def _verify(self, task: Task, emit=None) -> Verification:
        if not isinstance(task, Task):
            raise TypeError("Expected original validated Task")
        targets = {requirement.issue_id: requirement.status for requirement in task.requirements}
        if not targets or len(targets) != len(task.requirements):
            raise ValueError("Verification requires unique original targets")
        try:
            reservation = self.ledger.reserve(len(targets))
        except VerificationBudgetExceeded as exc:
            if emit:
                emit("denied", requested_target_rows=len(targets), reason=str(exc))
            raise
        try:
            if emit:
                emit("admitted", requested_target_rows=len(targets))
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
            if emit:
                emit("error")
            raise
        if emit:
            emit("completed")
        return result


def prepare_verification_run(verifier, task, run_id):
    if isinstance(verifier, BudgetedStateVerifier):
        verifier.bind_run(task, run_id)


def verification_configuration(verifier):
    return verifier.configuration() if isinstance(verifier, BudgetedStateVerifier) else {}


def verify_for_run(verifier, task, traces, run_id):
    if isinstance(verifier, BudgetedStateVerifier):
        return verifier.verify_traced(task, traces, run_id)
    return verifier.verify(task)
