"""Verification never trusts executor responses or the planner's success claims."""

import sqlite3
from contextlib import closing
from pathlib import Path

from veriagent.models import Evidence, Failure, Status, Task, Verification


class StateVerifier:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def verify(self, task: Task) -> Verification:
        evidence = []
        # Separate read-only connection, single snapshot, no tool response input.
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("BEGIN")
            for req in task.requirements:
                row = db.execute(
                    "SELECT status, version FROM issues WHERE id = ?", (req.issue_id,)
                ).fetchone()
                evidence.append(
                    Evidence(
                        issue_id=req.issue_id,
                        expected=req.status,
                        actual=Status(row[0]) if row else None,
                        version=row[1] if row else None,
                    )
                )
        passed = all(e.actual == e.expected for e in evidence)
        failure = (
            None
            if passed
            else (
                Failure.NOT_FOUND
                if any(e.actual is None for e in evidence)
                else Failure.STATE_MISMATCH
            )
        )
        return Verification(passed=passed, evidence=tuple(evidence), failure=failure)
