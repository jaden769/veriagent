"""Offline-only strict reflection payload and sequential dispatch accounting primitives."""

import json
import math
from dataclasses import dataclass

from pydantic import ConfigDict, Field, field_validator, model_validator

from veriagent.budgeting import ModelBudgetExceeded, ModelBudgetLedger
from veriagent.models import ModelBudgetState, ModelLimits, ModelUsage, Schema, Task
from veriagent.reflection import ReflectionState


def strict_model(cls, value):
    raw = value.model_dump(mode="json") if isinstance(value, Schema) else value
    return cls.model_validate_json(json.dumps(raw, allow_nan=False), strict=True)


class ReflectionInput(Schema):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    task: Task
    state: ReflectionState

    @field_validator("task", "state", mode="before")
    @classmethod
    def strict_nested(cls, value, info):
        return strict_model(Task if info.field_name == "task" else ReflectionState, value)

    @model_validator(mode="after")
    def counters(self):
        if (
            self.state.actions > self.state.budget.max_actions
            or self.state.decisions > self.state.budget.max_decisions
            or self.state.corrective_admissions > min(2, self.state.budget.max_retries)
        ):
            raise ValueError("Reflection counters exceed shared limits")
        return self


def reflection_payload(task, state):
    return ReflectionInput(task=task, state=state).model_dump(mode="json")


class MeteredRequestLimits(Schema):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    max_requests: int = Field(ge=0)
    per_request_max_output_tokens: int = Field(ge=128)
    request_timeout_seconds: float = Field(gt=0, le=3600, allow_inf_nan=False)
    model_limits: ModelLimits

    @field_validator("model_limits", mode="before")
    @classmethod
    def strict_nested(cls, value):
        return strict_model(ModelLimits, value)


@dataclass(frozen=True, eq=False)
class DispatchTicket:
    output_allowance: int
    timeout_seconds: float


class MeteredRequestLedger:
    """No transport or policy: caller admits at dispatch and settles exactly once.

    Attempt/output admission is not a hard total-token or dollar reservation. Pending
    and failed unknown work stays unknown; explicit run reset is forbidden in flight.
    """

    def __init__(self, limits: MeteredRequestLimits, model: str):
        if not isinstance(limits, MeteredRequestLimits):
            raise TypeError("Expected strict MeteredRequestLimits")
        self.limits = strict_model(MeteredRequestLimits, limits)
        if type(model) is not str or not model.strip() or len(model) > 200:
            raise ValueError("Require explicit bounded model identity")
        self.model = model
        self._pending = None
        self.begin_run()

    def begin_run(self):
        if self._pending is not None:
            raise ValueError("Settle pending dispatch before resetting a run")
        self._ledger = ModelBudgetLedger(self.limits.model_limits, self.model)
        self._attempts = self._settled = self._failed = 0
        self._known_input = self._known_output = 0
        self._known_cost = 0.0
        self._stop_reason = None
        self._provider_failed = False
        self._last_settled = None
        self._last_failed = False
        self._usage = ModelUsage(provider="openai", model=self.model)

    def begin_decision(self):
        if self._pending is not None:
            raise ValueError("A dispatch is already pending")
        self._usage = ModelUsage(provider="openai", model=self.model)

    def _halt(self, reason):
        self._stop_reason = reason
        raise ModelBudgetExceeded(reason)

    def admit(self, *, remaining_seconds):
        self.begin_decision()
        if self._stop_reason:
            raise ModelBudgetExceeded(self._stop_reason)
        if type(remaining_seconds) not in (int, float) or not math.isfinite(remaining_seconds):
            raise ValueError("Require a finite remaining deadline")
        if remaining_seconds <= 0:
            self._halt("request_deadline_exhausted")
        if self._attempts >= self.limits.max_requests:
            self._halt("request_limit_exhausted")
        try:
            allowance = self._ledger.allowance(self.limits.per_request_max_output_tokens)
        except ModelBudgetExceeded as exc:
            self._stop_reason = str(exc)
            raise
        ticket = DispatchTicket(
            allowance, min(float(remaining_seconds), self.limits.request_timeout_seconds)
        )
        self._attempts += 1
        self._pending = ticket
        self._usage = self._unknown_usage()
        return ticket

    def _unknown_usage(self):
        return ModelUsage(
            provider="openai",
            model=self.model,
            calls=1,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
        )

    def _check(self, ticket):
        if self._pending is None or ticket is not self._pending:
            raise ValueError("Unknown, stale or foreign dispatch ticket")

    def complete(self, ticket, usage):
        self._settle(ticket, usage, provider_failed=False)

    def fail(self, ticket, usage=None):
        # Suppress secondary budget errors so the caller can retain its provider failure.
        self._settle(
            ticket, self._unknown_usage() if usage is None else usage, provider_failed=True
        )

    def mark_provider_failure(self, ticket):
        if (
            self._last_settled is None
            or self._pending is not None
            or ticket is not self._last_settled
            or self._last_failed
        ):
            raise ValueError("Require the latest settled, unclassified dispatch")
        self._last_failed = True
        self._failed += 1
        self._provider_failed = True
        if self._stop_reason is None:
            self._stop_reason = "provider_failure"

    def stop(self, reason):
        if reason not in {"shared_budget_exhausted", "response_deadline_exhausted"}:
            raise ValueError("Unknown caller stop reason")
        self._halt(reason)

    def _settle(self, ticket, usage, *, provider_failed):
        self._check(ticket)
        current = strict_model(ModelUsage, usage)
        if current.calls != 1 or current.provider != "openai":
            raise ValueError("Account for exactly one dispatched request")
        self._ledger.record(current)
        self._usage = current
        self._pending = None
        self._last_settled = ticket
        self._last_failed = provider_failed
        self._settled += 1
        self._failed += int(provider_failed)
        self._provider_failed |= provider_failed
        if current.input_tokens is not None:
            self._known_input += current.input_tokens
        if current.output_tokens is not None:
            self._known_output += current.output_tokens
        if current.estimated_cost_usd is not None:
            self._known_cost += current.estimated_cost_usd
        try:
            if (
                current.output_tokens is not None
                and current.output_tokens > ticket.output_allowance
            ):
                self._halt("request_output_exceeded")
            if current.input_tokens is None or current.output_tokens is None:
                self._halt("token_usage_unknown")
            self._ledger.check_response()
        except ModelBudgetExceeded as exc:
            self._stop_reason = str(exc)
            if not provider_failed:
                raise
        if provider_failed and self._stop_reason is None:
            self._stop_reason = "provider_failure"

    @property
    def usage(self):
        return strict_model(ModelUsage, self._usage)

    @property
    def budget_state(self):
        usage = self._ledger.usage
        if self._pending is not None:
            usage = ModelUsage(
                provider="openai",
                model=usage.model,
                calls=self._attempts,
                input_tokens=None,
                output_tokens=None,
                estimated_cost_usd=None,
            )
        return strict_model(
            ModelBudgetState,
            dict(
                limits=self.limits.model_limits.model_dump(mode="json"),
                usage=usage.model_dump(mode="json"),
                stop_reason=self._stop_reason,
            ),
        )

    @property
    def state(self):
        return dict(
            schema_version=1,
            limits=self.limits.model_dump(mode="json"),
            request_attempts=self._attempts,
            settled_requests=self._settled,
            failed_requests=self._failed,
            pending=self._pending is not None,
            provider_failed=self._provider_failed,
            usage=self.usage.model_dump(mode="json"),
            model_budget_state=self.budget_state.model_dump(mode="json"),
            known_input_tokens=self._known_input,
            known_output_tokens=self._known_output,
            known_estimated_cost_usd=self._known_cost,
            stop_reason=self._stop_reason,
        )
