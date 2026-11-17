"""Isolated SQLite application state and controlled, process-local tool faults."""

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from veriagent.models import Issue, Status


class TransientError(Exception):
    """A simulated recoverable transport failure before committing a write."""


@dataclass
class Faults:
    silent_drops: int = 0
    transient_errors: int = 0
    delay_seconds: float = 0

    def __post_init__(self) -> None:
        if min(self.silent_drops, self.transient_errors, self.delay_seconds) < 0:
            raise ValueError("Fault counts and delay must be nonnegative")


class Sandbox:
    def __init__(self, path: Path, faults: Faults | None = None):
        self.path = path.resolve()
        self.faults = faults or Faults()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS issues "
                "(id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, "
                "version INTEGER NOT NULL DEFAULT 0)"
            )

    def seed(self) -> None:
        """Initialize sample issues without overwriting existing work."""
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany(
                "INSERT OR IGNORE INTO issues VALUES (?, ?, ?, 0)",
                [
                    (f"ISSUE-{i}", title, "open")
                    for i, title in enumerate(
                        ("Fix login bug", "Update docs", "Add regression test"), start=1
                    )
                ],
            )

    def read_issue(self, issue_id: str) -> Issue:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT id, title, status, version FROM issues WHERE id = ?", (issue_id,)
            ).fetchone()
        if row is None:
            raise KeyError(issue_id)
        return Issue(id=row[0], title=row[1], status=row[2], version=row[3])

    def set_status(self, issue_id: str, status: Status, *, timeout: float) -> dict:
        """Absolute assignment is idempotent; faults occur before any commit.

        Timeout is cooperative for this local adapter. Remote adapters must enforce
        their own transport timeout and resolve ambiguous commits before retrying.
        """
        if self.faults.delay_seconds >= timeout:
            raise TimeoutError("Simulated tool delay exceeds remaining deadline")
        time.sleep(self.faults.delay_seconds)
        self.read_issue(issue_id)
        if self.faults.transient_errors:
            self.faults.transient_errors -= 1
            raise TransientError("Injected pre-commit transport failure")
        if self.faults.silent_drops:
            self.faults.silent_drops -= 1
            return {"message": "Status updated", "status": status.value}
        with closing(sqlite3.connect(self.path, timeout=timeout)) as db, db:
            db.execute(
                "UPDATE issues SET status = ?, version = version + 1 WHERE id = ? AND status != ?",
                (status.value, issue_id, status.value),
            )
        return {"message": "Status updated", "status": status.value}
