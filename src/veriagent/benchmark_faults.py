"""Benchmark-only indexed write faults with an explicit record of realized exposure."""

import time
from typing import Literal

from pydantic import Field

from veriagent.models import Schema, Status
from veriagent.sandbox import Faults, Sandbox, TransientError

DEFAULT_SCENARIOS = ("clean", "silent_drop", "persistent_drop", "transient")
INDEXED_SCENARIOS = ("second_drop", "second_transient", "two_drops")
ALL_SCENARIOS = DEFAULT_SCENARIOS + INDEXED_SCENARIOS


class WriteFault(Schema):
    attempt: int = Field(ge=1, le=10000, strict=True)
    kind: Literal["silent_drop", "transient"]


def scenario_faults(scenario: str, max_actions: int) -> tuple[Faults, tuple[WriteFault, ...]]:
    if scenario not in ALL_SCENARIOS:
        raise ValueError("Unknown fault scenario")
    schedule = {
        "second_drop": (WriteFault(attempt=2, kind="silent_drop"),),
        "second_transient": (WriteFault(attempt=2, kind="transient"),),
        "two_drops": (
            WriteFault(attempt=1, kind="silent_drop"),
            WriteFault(attempt=2, kind="silent_drop"),
        ),
    }.get(scenario, ())
    return Faults(
        silent_drops={"silent_drop": 1, "persistent_drop": max_actions + 1}.get(scenario, 0),
        transient_errors=int(scenario == "transient"),
    ), schedule


class ScheduledSandbox(Sandbox):
    def __init__(self, path, faults: Faults, schedule: tuple[WriteFault, ...] = ()):
        if len(schedule) > 100 or len({event.attempt for event in schedule}) != len(schedule):
            raise ValueError("Use at most 100 unique indexed fault events")
        if schedule and (faults.silent_drops or faults.transient_errors):
            raise ValueError("Do not combine indexed faults with counter faults")
        super().__init__(path, faults)
        self.schedule = {event.attempt: event.kind for event in schedule}
        self.write_attempts: list[dict] = []

    def set_status(self, issue_id: str, status: Status, *, timeout: float) -> dict:
        attempt = len(self.write_attempts) + 1
        scheduled = self.schedule.get(attempt)
        record = {
            "attempt": attempt,
            "issue_id": issue_id,
            "status": status.value,
            "scheduled_fault": scheduled,
            "injected_fault": None,
            "status_before_fault": None,
        }
        self.write_attempts.append(record)
        if scheduled:
            # Match the ordinary adapter's deadline/existence checks before injection.
            # A failed precondition consumes the attempt index, not the fault event.
            if self.faults.delay_seconds >= timeout:
                raise TimeoutError("Simulated tool delay exceeds remaining deadline")
            time.sleep(self.faults.delay_seconds)
            before = self.read_issue(issue_id)
            record["status_before_fault"] = before.status.value
            record["injected_fault"] = scheduled
            if scheduled == "transient":
                raise TransientError("Indexed pre-commit transport failure")
            return {"message": "Status updated", "status": status.value}
        drops = self.faults.silent_drops
        transient = self.faults.transient_errors
        before_status = None
        if (drops or transient) and self.faults.delay_seconds < timeout:
            try:
                before_status = self.read_issue(issue_id).status.value
            except KeyError:
                pass  # Preserve the ordinary adapter's failure and fault-consumption behavior.
        try:
            return super().set_status(issue_id, status, timeout=timeout)
        finally:
            if self.faults.transient_errors < transient:
                record["injected_fault"] = "transient"
                record["status_before_fault"] = before_status
            elif self.faults.silent_drops < drops:
                record["injected_fault"] = "silent_drop"
                record["status_before_fault"] = before_status

    def unused_schedule(self) -> list[dict]:
        injected = {r["attempt"] for r in self.write_attempts if r["injected_fault"] is not None}
        return [
            {"attempt": attempt, "kind": kind}
            for attempt, kind in sorted(self.schedule.items())
            if attempt not in injected
        ]
