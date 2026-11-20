"""Controlled UI ambiguity after a durable commit, never exposed as model fault labels."""

import threading

from fastapi.responses import JSONResponse

from veriagent.models import Status
from veriagent.sandbox import Sandbox, TransientError

TIMEOUT_SCENARIOS = ("timeout_before_commit", "timeout_after_commit")
BROWSER_SCENARIOS = ("clean", "silent_drop", "stale_dom", "lost_ack") + TIMEOUT_SCENARIOS
INDEXED_BROWSER_SCENARIOS = (
    "second_drop",
    "second_lost_ack",
    "second_timeout_before_commit",
    "second_timeout_after_commit",
)
ALL_BROWSER_SCENARIOS = BROWSER_SCENARIOS + INDEXED_BROWSER_SCENARIOS
ACK_HOLD_SECONDS = 10


def validate_browser_deadline(scenario: str, action_timeout: float) -> None:
    if (
        scenario in TIMEOUT_SCENARIOS or scenario.startswith("second_timeout_")
    ) and action_timeout >= ACK_HOLD_SECONDS:
        raise ValueError("Timeout scenarios require --action-timeout below 10 seconds")


class BrowserAppFaults:
    def __init__(self, scenario: str = "clean"):
        if scenario not in ALL_BROWSER_SCENARIOS:
            raise ValueError("Unknown browser scenario")
        self.scenario = scenario
        self.remaining = int(
            scenario in {"stale_dom", "lost_ack", *TIMEOUT_SCENARIOS, *INDEXED_BROWSER_SCENARIOS}
        )
        self.write_attempt = 0
        self.events: list[dict] = []
        self.events_dropped = 0
        self._lock = threading.Lock()
        self._ack_release = threading.Event()
        self._held_event = None

    def release_pending(self, reason: str) -> None:
        # Do not acquire the write lock: the HTTP handler holds it while waiting.
        event = self._held_event
        if event is not None:
            event.setdefault("release_reason", reason)
            self._ack_release.set()

    def _hold_ack(self, event: dict) -> None:
        self._ack_release.clear()
        self._held_event = event
        event["response_state"] = "held"
        if not self._ack_release.wait(timeout=ACK_HOLD_SECONDS):
            event.setdefault("release_reason", "safety_deadline")
        event["response_state"] = "released"
        self._held_event = None

    def _record(self, event: dict):
        event["attempt"] = self.write_attempt
        event["scheduled_fault"] = (
            self.scenario
            if (self.scenario in INDEXED_BROWSER_SCENARIOS and self.write_attempt == 2)
            else None
        )
        if len(self.events) < 2048:
            self.events.append(event)
        else:
            self.events_dropped += 1

    def write(self, sandbox: Sandbox, issue_id: str, status: Status):
        # Serialize fixture writes so before/after event evidence identifies this call.
        with self._lock:
            self.write_attempt += 1
            before = sandbox.read_issue(issue_id)
            indexed = self.scenario in INDEXED_BROWSER_SCENARIOS
            eligible = self.remaining and (not indexed or self.write_attempt == 2)
            kind = self.scenario.removeprefix("second_") if indexed else self.scenario
            if kind == "drop":
                kind = "silent_drop"
            if (
                kind in {"timeout_before_commit", "silent_drop"}
                and eligible
                and before.status != status
            ):
                self.remaining -= 1
                event = {
                    "issue_id": issue_id,
                    "requested_status": status.value,
                    "before_status": before.status.value,
                    "after_status": before.status.value,
                    "before_version": before.version,
                    "after_version": before.version,
                    "http_status": 503 if kind == "timeout_before_commit" else 200,
                    "committed": False,
                    "injected": self.scenario,
                }
                self._record(event)
                if kind == "silent_drop":
                    return {"message": "Status updated", "status": status.value}
                self._hold_ack(event)
                # This controlled request is rejected, never committed after release.
                return JSONResponse({"detail": "Status update failed"}, status_code=503)
            try:
                result = sandbox.set_status(issue_id, status, timeout=1)
            except (TransientError, TimeoutError) as exc:
                self._record(
                    {
                        "issue_id": issue_id,
                        "requested_status": status.value,
                        "before_status": before.status.value,
                        "after_status": before.status.value,
                        "before_version": before.version,
                        "after_version": before.version,
                        "http_status": 503 if isinstance(exc, TransientError) else 504,
                        "committed": False,
                        "injected": None,
                    }
                )
                raise
            after = sandbox.read_issue(issue_id)
            committed = (
                before.status != after.status
                and after.status == status
                and after.version > before.version
            )
            injected = self.scenario if eligible and committed else None
            code = 503 if injected and kind == "lost_ack" else 200
            event = {
                "issue_id": issue_id,
                "requested_status": status.value,
                "before_status": before.status.value,
                "after_status": after.status.value,
                "before_version": before.version,
                "after_version": after.version,
                "http_status": code,
                "injected": injected,
                "committed": committed,
            }
            if injected is not None:
                self.remaining -= 1
            self._record(event)
            if injected and kind == "timeout_after_commit":
                self._hold_ack(event)
            if injected and kind == "lost_ack":
                # Actual commit succeeded, but the caller sees an ordinary service error.
                return JSONResponse({"detail": "Status update failed"}, status_code=503)
            if injected == "stale_dom":
                result = {**result, "display_status": before.status.value}
            return result
