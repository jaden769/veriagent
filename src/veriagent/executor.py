"""Tool policy lives in trusted code, never in model-provided action metadata."""

import time
from dataclasses import dataclass
from typing import Protocol

from veriagent.models import Action, Failure, Issue, Observation, Status
from veriagent.sandbox import TransientError


class IssueTools(Protocol):
    def read_issue(self, issue_id: str) -> Issue: ...

    def set_status(self, issue_id: str, status: Status, *, timeout: float) -> dict: ...


@dataclass(frozen=True)
class ToolPolicy:
    idempotent: bool
    allowed: bool = True


class Executor:
    def __init__(self, tools: IssueTools, allowed_tools: frozenset[str] | None = None):
        self.tools = tools
        allowed = (
            allowed_tools if allowed_tools is not None else frozenset({"read_issue", "set_status"})
        )
        self.policies = {
            name: ToolPolicy(idempotent=True, allowed=name in allowed)
            for name in ("read_issue", "set_status")
        }

    def retry_safe(self, action: Action) -> bool:
        policy = self.policies.get(action.tool)
        return bool(policy and policy.allowed and policy.idempotent)

    def execute(self, action: Action, timeout: float) -> Observation:
        start = time.monotonic()
        data = {}
        failure = None
        try:
            if timeout <= 0:
                raise TimeoutError("No execution time remaining")
            policy = self.policies.get(action.tool)
            if not policy or not policy.allowed:
                raise PermissionError(action.tool)
            if action.tool == "read_issue":
                data = self.tools.read_issue(action.issue_id).model_dump(mode="json")
            else:
                assert action.status is not None
                data = self.tools.set_status(action.issue_id, action.status, timeout=timeout)
            if time.monotonic() - start > timeout:
                raise TimeoutError("Tool exceeded its deadline; commit status may be ambiguous")
        except PermissionError:
            failure = Failure.PERMISSION
        except KeyError:
            failure = Failure.NOT_FOUND
        except TransientError:
            failure = Failure.TRANSIENT
        except TimeoutError:
            failure = Failure.TIMEOUT
        except Exception:
            # Do not place arbitrary exception strings (possibly credentials) in traces.
            failure = Failure.INTERNAL
        return Observation(
            action=action,
            reported_success=failure is None,
            data=data,
            failure=failure,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )
