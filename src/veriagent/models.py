"""Validated contracts shared by independently testable components."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Status(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Mode(StrEnum):
    BASELINE = "baseline"
    VERIFY = "verify"
    RECOVER = "recover"


class Failure(StrEnum):
    TRANSIENT = "transient"
    STATE_MISMATCH = "state_mismatch"
    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    BUDGET = "budget"
    DEPENDENCY = "dependency"
    INTERNAL = "internal"
    PLANNING = "planning"


class Issue(Schema):
    id: str
    title: str
    status: Status = Status.OPEN
    version: int = 0


class Requirement(Schema):
    issue_id: str = Field(pattern=r"^ISSUE-\d+$")
    status: Status


class Task(Schema):
    objective: str = Field(min_length=1, max_length=2000)
    requirements: tuple[Requirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_targets(self) -> "Task":
        ids = [r.issue_id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("Each issue may have only one final requirement")
        return self


class Action(Schema):
    tool: Literal["read_issue", "set_status"]
    issue_id: str = Field(pattern=r"^ISSUE-\d+$")
    status: Status | None = None

    @model_validator(mode="after")
    def status_argument(self) -> "Action":
        if (self.tool == "set_status") != (self.status is not None):
            raise ValueError("Only set_status requires a status")
        return self


class Step(Schema):
    id: str
    action: Action
    depends_on: tuple[str, ...] = ()
    expected: Requirement


class Plan(Schema):
    steps: tuple[Step, ...] = Field(min_length=1)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def ordered_dependencies(self) -> "Plan":
        seen: set[str] = set()
        for step in self.steps:
            if step.id in seen or not set(step.depends_on) <= seen:
                raise ValueError("Step IDs must be unique and dependencies must precede each step")
            seen.add(step.id)
        return self


class Observation(Schema):
    action: Action
    reported_success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    failure: Failure | None = None
    elapsed_ms: float = 0
    safe_to_continue: bool = True


class Evidence(Schema):
    issue_id: str
    expected: Status
    actual: Status | None
    version: int | None
    source: Literal["sqlite_read_only"] = "sqlite_read_only"


class Verification(Schema):
    passed: bool
    evidence: tuple[Evidence, ...]
    failure: Failure | None = None


class Budget(Schema):
    max_actions: int = Field(default=20, ge=1, le=10000)
    max_retries: int = Field(default=2, ge=0, le=100)
    timeout_seconds: float = Field(default=10, gt=0, le=3600)
    action_timeout_seconds: float = Field(default=1, gt=0, le=60)
    max_decisions: int = Field(default=20, ge=1, le=1000)


class ToolExecutionConfig(Schema):
    mode: Literal["in_process", "process"] = "in_process"
    hangs_before_commit: int = Field(default=0, ge=0, le=100)
    hangs_after_commit: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def process_faults(self) -> "ToolExecutionConfig":
        if self.mode != "process" and (self.hangs_before_commit or self.hangs_after_commit):
            raise ValueError("Worker hang injection requires --isolate-tools")
        return self


class ActionFeedback(Schema):
    action: Action
    reported_success: bool
    failure: Failure | None
    observed_status: Status | None


class DecisionState(Schema):
    budget: Budget = Field(default_factory=Budget)
    feedback: tuple[ActionFeedback, ...] = ()
    verification: Verification | None = None
    actions: int = 0
    recovery_attempts: int = 0
    decisions: int = 0


class Decision(Schema):
    kind: Literal["action", "finish"]
    action: Action | None = None
    call_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_choice(self) -> "Decision":
        if (self.kind == "action") != (self.action is not None):
            raise ValueError("An action decision needs an action; finish must not include one")
        return self


class ModelUsage(Schema):
    provider: str = "mock"
    model: str | None = None
    calls: int = Field(default=0, ge=0)
    input_tokens: int | None = Field(default=0, ge=0)
    output_tokens: int | None = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=0.0, ge=0, allow_inf_nan=False)

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


class ModelLimits(Schema):
    max_total_tokens: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, ge=0)
    max_cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ModelBudgetState(Schema):
    limits: ModelLimits
    usage: ModelUsage
    stop_reason: str | None = None


class ProviderDiagnostic(Schema):
    category: Literal[
        "authentication",
        "permission",
        "rate_limit",
        "api_status",
        "timeout",
        "connection",
        "response_validation",
        "usage_unavailable",
        "incomplete_response",
    ]
    http_status: int | None = Field(default=None, ge=100, le=599)
    api_code: (
        Literal[
            "invalid_api_key",
            "insufficient_quota",
            "invalid_json_schema",
            "unsupported_parameter",
            "model_not_found",
            "rate_limit_exceeded",
            "context_length_exceeded",
        ]
        | None
    ) = None
    api_parameter: str | None = Field(default=None, max_length=100)
    detail: str | None = Field(default=None, max_length=400)
    body_format: Literal["json", "text", "empty", "other"] | None = None


class Interpretation(Schema):
    requirements: tuple[Requirement, ...] = Field(max_length=100)
    clarification: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def decision(self) -> "Interpretation":
        if bool(self.requirements) == (self.clarification is not None):
            raise ValueError("Return requirements or a clarification, never both or neither")
        if self.requirements:
            Task(objective="Validate interpreted requirements", requirements=self.requirements)
        return self


class TaskProposal(Schema):
    schema_version: Literal[1] = 1
    objective: str = Field(min_length=1, max_length=2000)
    interpretation: Interpretation
    interpretation_usage: ModelUsage = Field(default_factory=ModelUsage)

    def task(self) -> Task:
        if self.interpretation.clarification is not None:
            raise ValueError("This proposal needs clarification and cannot be executed")
        return Task(objective=self.objective, requirements=self.interpretation.requirements)


class RunReport(Schema):
    run_id: str
    mode: Mode
    claimed_success: bool
    verified_success: bool | None
    actions: int
    recovery_attempts: int
    elapsed_ms: float
    failure: Failure | None = None
    verification: Verification | None = None
    model_calls: int = 0
    model_tokens: int | None = 0
    estimated_cost_usd: float | None = 0.0
    model_usage: ModelUsage = Field(default_factory=ModelUsage)
    engine: Literal["static", "dynamic"] = "static"
    decisions: int = 0
    model_budget: ModelBudgetState | None = None
    tool_execution: Literal["in_process", "process", "browser"] = "in_process"
    provider_diagnostic: ProviderDiagnostic | None = None
