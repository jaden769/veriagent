"""Per-run request admission using observed usage and reserved output allowance."""

from veriagent.models import ModelBudgetState, ModelLimits, ModelUsage


class ModelBudgetExceeded(Exception):
    """A sanitized reason code; never contains request data or credentials."""


class ModelBudgetLedger:
    # Local policy, not a claim about an API-wide minimum. Smaller remainders are unused.
    minimum_output_allowance = 128

    def __init__(self, limits: ModelLimits, model: str):
        self.limits, self.model = limits, model
        self.reset()

    def reset(self) -> None:
        self.usage = ModelUsage(provider="openai", model=self.model)
        self.stop_reason = None

    @property
    def state(self) -> ModelBudgetState:
        return ModelBudgetState(limits=self.limits, usage=self.usage, stop_reason=self.stop_reason)

    def stop(self, reason: str) -> None:
        self.stop_reason = reason
        raise ModelBudgetExceeded(reason)

    def check_known(self) -> None:
        if self.stop_reason:
            raise ModelBudgetExceeded(self.stop_reason)
        if self.limits.max_total_tokens is not None and self.usage.total_tokens is None:
            self.stop("token_usage_unknown")
        if self.limits.max_output_tokens is not None and self.usage.output_tokens is None:
            self.stop("output_usage_unknown")
        if self.limits.max_cost_usd is not None and self.usage.estimated_cost_usd is None:
            self.stop("cost_usage_unknown")

    def allowance(self, requested: int) -> int:
        self.check_known()
        if self.limits.max_total_tokens is not None:
            if self.usage.total_tokens >= self.limits.max_total_tokens:
                self.stop("total_tokens_exhausted")
        if self.limits.max_cost_usd is not None:
            if self.usage.estimated_cost_usd >= self.limits.max_cost_usd:
                self.stop("cost_threshold_reached")
        if self.limits.max_output_tokens is not None:
            remaining = self.limits.max_output_tokens - self.usage.output_tokens
            if remaining < self.minimum_output_allowance:
                self.stop("output_allowance_insufficient")
            return min(requested, remaining)
        return requested

    def record(self, current: ModelUsage) -> None:
        def add(a, b):
            return None if a is None or b is None else a + b

        self.usage = ModelUsage(
            provider="openai",
            model=current.model
            if not self.usage.calls
            else (self.usage.model if self.usage.model == current.model else None),
            calls=self.usage.calls + current.calls,
            input_tokens=add(self.usage.input_tokens, current.input_tokens),
            output_tokens=add(self.usage.output_tokens, current.output_tokens),
            estimated_cost_usd=add(self.usage.estimated_cost_usd, current.estimated_cost_usd),
        )

    def check_response(self) -> None:
        self.check_known()
        for limit, observed, reason in (
            (self.limits.max_total_tokens, self.usage.total_tokens, "total_tokens_exceeded"),
            (self.limits.max_output_tokens, self.usage.output_tokens, "output_tokens_exceeded"),
            (self.limits.max_cost_usd, self.usage.estimated_cost_usd, "cost_threshold_exceeded"),
        ):
            if limit is not None and observed > limit:
                self.stop(reason)
