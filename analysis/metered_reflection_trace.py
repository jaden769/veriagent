"""Offline metered request replay plus projected reflection phase reconciliation."""

import copy
import math

from analysis.metered_reflection import MeteredRequestLedger, MeteredRequestLimits, strict_model
from analysis.metered_reflection_agent import MeteredReflectionReport
from research.reflection_trace import reconcile_reflection_trace, same
from veriagent.budgeting import ModelBudgetExceeded
from veriagent.models import ModelUsage, ProviderDiagnostic
from veriagent.reflection import ReflectionReport


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _reconcile_metered_trace(events, *, expected_run_id, policies=None):
    require(
        isinstance(events, list) and 3 <= len(events) <= 20000, "Require bounded complete trace"
    )
    first = events[0].get("seq") if isinstance(events[0], dict) else None
    require(type(first) is int and first >= 1, "Invalid initial sequence")
    for index, event in enumerate(events, first):
        require(
            isinstance(event, dict)
            and event.get("seq") == index
            and type(event.get("seq")) is int
            and isinstance(event.get("kind"), str)
            and isinstance(event.get("payload"), dict),
            "Invalid metered event frame/order",
        )
        require(
            "run_id" not in event or event["run_id"] == expected_run_id, "Run identity mismatch"
        )
    require(
        events[0]["kind"] == "task" and events[1]["kind"] == "configuration",
        "Missing initial configuration",
    )
    config = events[1]["payload"]
    require(
        set(config)
        == {"comparator", "budget", "max_reflections", "trusted_oracle_access", "provider"}
        and config["comparator"] == "llm_self_reflection"
        and config["trusted_oracle_access"] is False,
        "Invalid metered configuration",
    )
    public = config["provider"]
    require(
        set(public) == {"model", "limits", "prices"}, "Unexpected public provider configuration"
    )
    limits = strict_model(MeteredRequestLimits, public["limits"])
    ledger = MeteredRequestLedger(limits, public["model"])
    prices = public["prices"]
    require(
        isinstance(prices, list)
        and len(prices) == 2
        and ((prices[0] is None) == (prices[1] is None)),
        "Invalid price pair",
    )
    require(
        all(p is None or type(p) in (int, float) and math.isfinite(p) and p >= 0 for p in prices),
        "Invalid public prices",
    )
    require(
        limits.model_limits.max_cost_usd is None or prices[0] is not None,
        "Missing prices for cost threshold",
    )
    projected = []
    expected_next = None
    last_outcome = None
    last_diagnostic = None
    terminal_error = None
    report = None
    decisions = 0
    for event in events:
        kind, payload = event["kind"], event["payload"]
        if kind == "metered_decision_accounting":
            require(
                report is None and expected_next == "accounting", "Accounting event out of place"
            )
            require(
                set(payload) == {"before", "after", "outcome", "dispatch", "diagnostic"},
                "Unexpected accounting fields",
            )
            require(same(payload["before"], ledger.state), "Before state mismatch")
            ledger.begin_decision()
            after = payload["after"]
            outcome = payload["outcome"]
            require(
                outcome in {"decision", "budget", "permission", "planning"},
                "Incomplete/cancelled accounting",
            )
            dispatched = after["request_attempts"] - payload["before"]["request_attempts"]
            require(type(dispatched) is int and dispatched in {0, 1}, "Invalid dispatch count")
            if dispatched:
                dispatch = payload["dispatch"]
                require(
                    isinstance(dispatch, dict)
                    and set(dispatch) == {"timeout_seconds", "output_allowance"},
                    "Missing dispatch allowance",
                )
                ticket = ledger.admit(remaining_seconds=dispatch["timeout_seconds"])
                require(
                    same(ticket.output_allowance, dispatch["output_allowance"])
                    and same(ticket.timeout_seconds, dispatch["timeout_seconds"]),
                    "Output allowance mismatch",
                )
                usage = strict_model(ModelUsage, after["usage"]).model_dump(mode="json")
                incoming, outgoing = usage["input_tokens"], usage["output_tokens"]
                expected_cost = None
                if incoming is not None and outgoing is not None and prices[0] is not None:
                    expected_cost = (incoming * prices[0] + outgoing * prices[1]) / 1e6
                require(same(usage["estimated_cost_usd"], expected_cost), "Estimated cost mismatch")
                try:
                    ledger.complete(ticket, usage)
                except ModelBudgetExceeded:
                    pass
                failed = after["failed_requests"] - payload["before"]["failed_requests"]
                require(type(failed) is int and failed in {0, 1}, "Invalid provider failure count")
                if failed:
                    require(
                        outcome in {"planning", "permission"}, "Provider error outcome mismatch"
                    )
                    ledger.mark_provider_failure(ticket)
                elif after["stop_reason"] == "response_deadline_exhausted":
                    try:
                        ledger.stop("response_deadline_exhausted")
                    except ModelBudgetExceeded:
                        pass
            else:
                require(payload["dispatch"] is None, "Phantom dispatch")
                reason = after["stop_reason"]
                if reason == "shared_budget_exhausted":
                    try:
                        ledger.stop(reason)
                    except ModelBudgetExceeded:
                        pass
                elif reason is not None:
                    try:
                        ledger.admit(
                            remaining_seconds=0 if reason == "request_deadline_exhausted" else 1
                        )
                    except ModelBudgetExceeded:
                        pass
            require(same(after, ledger.state), "After state mismatch")
            if outcome == "decision":
                require(
                    dispatched == 1 and after["stop_reason"] is None,
                    "Decision after accounting stop",
                )
                expected_next = "reflection_decision"
            else:
                require(
                    outcome != "budget" or after["stop_reason"] is not None,
                    "Unexplained budget denial",
                )
                expected_next = "reflection_decision_error"
            last_outcome = outcome
            last_diagnostic = payload["diagnostic"]
            if last_diagnostic is not None:
                diagnostic = strict_model(ProviderDiagnostic, last_diagnostic)
                require(
                    diagnostic.detail is None and diagnostic.body_format is None,
                    "Unsafe diagnostic excerpt",
                )
            decisions += 1
            continue
        if kind == "reflection_context":
            require(expected_next is None, "Missing accounting outcome")
            expected_next = "accounting"
        elif kind in {"reflection_decision", "reflection_decision_error"}:
            require(expected_next == kind, "Decision/accounting order mismatch")
            expected_next = None
            if kind == "reflection_decision_error":
                expected_failure = {
                    "budget": "budget",
                    "permission": "permission",
                    "planning": "planning",
                }[last_outcome]
                require(
                    payload == {"failure": expected_failure}, "Request failure mapping mismatch"
                )
                terminal_error = expected_failure
        elif kind == "metered_reflection_report":
            require(report is None and expected_next is None, "Unfinished metered report")
            report = strict_model(MeteredReflectionReport, payload)
            if terminal_error is not None:
                require(report.failure == terminal_error, "Terminal request failure mismatch")
            require(
                report.run_id == expected_run_id and same(payload, report.model_dump(mode="json")),
                "Native report mismatch",
            )
            require(
                same(report.request_state, ledger.state)
                and same(
                    report.model_budget_state.model_dump(mode="json"),
                    ledger.budget_state.model_dump(mode="json"),
                ),
                "Report accounting mismatch",
            )
            require(
                same(
                    report.provider_diagnostic.model_dump(mode="json")
                    if report.provider_diagnostic
                    else None,
                    last_diagnostic,
                ),
                "Report diagnostic mismatch",
            )
        elif expected_next is not None:
            raise ValueError("Missing accounting or decision event")
        projected.append(copy.deepcopy(event))
    require(
        report is not None and decisions == report.decisions, "Missing complete report/decisions"
    )
    # Reuse the frozen phase checker through a detached mock-format projection.
    for index, event in enumerate(projected, 1):
        event["seq"] = index
        if event["kind"] == "configuration":
            event["payload"].pop("provider")
            event["payload"]["comparator"] = "mock_self_reflection"
        elif event["kind"] == "reflection_decision_error":
            event["payload"] = {"failure": "planning"}
        elif event["kind"] == "metered_reflection_report":
            event["kind"] = "reflection_report"
            native = report.model_dump(mode="json")
            event["payload"] = {k: native[k] for k in ReflectionReport.model_fields}
            event["payload"].update(
                comparator="mock_self_reflection", model_calls=0, model_tokens=0
            )
            if terminal_error is not None:
                event["payload"]["failure"] = "planning"
    core = reconcile_reflection_trace(projected, expected_run_id=expected_run_id, policies=policies)
    return dict(
        schema_version=1,
        scope="metered_reflection_trace_consistency",
        consistency_passed=True,
        run_id=expected_run_id,
        request_attempts=report.request_attempts,
        model_tokens=report.model_tokens,
        final_request_state=ledger.state,
        tool_actions=core["actions"],
        trusted_verification_calls=0,
        limitations=(
            "Unsigned phase/accounting consistency; no provider/tool/oracle execution, "
            "billing authenticity or exact deadline proof."
        ),
    )


def reconcile_metered_trace(events, *, expected_run_id, policies=None):
    try:
        return _reconcile_metered_trace(events, expected_run_id=expected_run_id, policies=policies)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("Invalid or inconsistent metered reflection trace") from None
