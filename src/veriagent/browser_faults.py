"""Controlled UI ambiguity after a durable commit, never exposed as model fault labels."""

import threading

from fastapi.responses import JSONResponse

from veriagent.models import Status
from veriagent.sandbox import Sandbox, TransientError

BROWSER_SCENARIOS = ("clean", "silent_drop", "stale_dom", "lost_ack")


class BrowserAppFaults:
    def __init__(self, scenario: str = "clean"):
        if scenario not in BROWSER_SCENARIOS:
            raise ValueError("Unknown browser scenario")
        self.scenario = scenario
        self.remaining = int(scenario in {"stale_dom", "lost_ack"})
        self.events: list[dict] = []
        self.events_dropped = 0
        self._lock = threading.Lock()

    def _record(self, event: dict):
        if len(self.events) < 2048:
            self.events.append(event)
        else:
            self.events_dropped += 1

    def write(self, sandbox: Sandbox, issue_id: str, status: Status):
        # Serialize fixture writes so before/after event evidence identifies this call.
        with self._lock:
            before = sandbox.read_issue(issue_id)
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
            injected = self.scenario if self.remaining and committed else None
            code = 503 if injected == "lost_ack" else 200
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
            if injected == "lost_ack":
                # Actual commit succeeded, but the caller sees an ordinary service error.
                return JSONResponse({"detail": "Status update failed"}, status_code=503)
            if injected == "stale_dom":
                result = {**result, "display_status": before.status.value}
            return result
