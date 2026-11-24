"""Replay opt-in verification admission traces without executing tools or an oracle."""

import json

from veriagent.models import RunReport, Task, Verification
from veriagent.verification_budget import (
    VerificationBudgetExceeded,
    VerificationBudgetLedger,
    VerificationLimits,
)
from veriagent.verification_work import verification_work


def _same(left, right):
    # Python equality treats True == 1 and 1.0 == 1; serialized strict states do not.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def reconcile_verification_admission(events: list[dict], *, expected_run_id: str) -> dict:
    work = verification_work(events, expected_run_id=expected_run_id)
    configurations = [e["payload"] for e in events if e["kind"] == "configuration"]
    if len(configurations) != 1:
        raise ValueError("Require one opt-in verification configuration")
    configuration_index = next(i for i, e in enumerate(events) if e["kind"] == "configuration")
    if any(
        e["kind"] in {"action", "decision_context", "verification_budget"}
        for e in events[:configuration_index]
    ):
        raise ValueError("Configuration follows execution work")
    limits = configurations[0].get("verification_limits")
    if not isinstance(limits, dict) or set(limits) != {"max_calls", "max_target_rows"}:
        raise ValueError("Missing or invalid verification limits")
    ledger = VerificationBudgetLedger(VerificationLimits(**limits))
    task = Task.model_validate_json(json.dumps(events[0]["payload"]), strict=True)
    targets = len(task.requirements)
    pending = expected_event = reason = last_verification = None
    terminal = False
    denials = 0
    report = None
    for event in events:
        kind, payload = event["kind"], event["payload"]
        if expected_event is not None:
            if kind != expected_event:
                raise ValueError("Admission settlement lacks its immediate outcome event")
            if kind == "verification_denied" and payload != {"failure": "budget", "reason": reason}:
                raise ValueError("Denial outcome disagrees with admission reason")
            if kind == "verification":
                last_verification = Verification.model_validate_json(
                    json.dumps(payload), strict=True
                )
            expected_event = None
            continue
        if terminal and kind not in {"report", "benchmark_audit"}:
            raise ValueError("Execution continues after verification denial/error")
        if kind == "verification_budget":
            phase = payload.get("phase")
            fields = {"phase", "state"}
            if phase in {"admitted", "denied"}:
                fields.add("requested_target_rows")
                rows = payload.get("requested_target_rows")
                if type(rows) is not int or rows != targets:
                    raise ValueError("Admission target count disagrees with original task")
            if phase == "denied":
                fields.add("reason")
            if set(payload) != fields:
                raise ValueError("Unexpected admission event fields")
            if phase == "admitted":
                try:
                    pending = ledger.reserve(targets)
                except VerificationBudgetExceeded as exc:
                    raise ValueError("Recorded admission exceeds configured limits") from exc
            elif phase in {"completed", "error"}:
                if pending is None:
                    raise ValueError("Settlement without an admitted check")
                if phase == "completed":
                    ledger.complete(pending, observed_target_rows=targets)
                    expected_event = "verification"
                else:
                    ledger.fail(pending)
                    expected_event = "verification_error"
                    terminal = True
                pending = None
            elif phase == "denied":
                try:
                    ledger.reserve(targets)
                except VerificationBudgetExceeded as exc:
                    reason = str(exc)
                else:
                    raise ValueError("Recorded denial was admissible under configured limits")
                if payload["reason"] != reason:
                    raise ValueError("Recorded denial reason disagrees with limits")
                denials += 1
                expected_event = "verification_denied"
                terminal = True
            else:
                raise ValueError("Unknown admission phase")
            if not _same(payload["state"], ledger.state):
                raise ValueError("Recorded admission state disagrees with replay")
        elif kind in {"verification", "verification_error", "verification_denied"}:
            raise ValueError("Verification outcome lacks admission settlement")
        elif pending is not None and kind != "verification_budget":
            raise ValueError("Unsettled verification admission")
        elif kind == "report":
            report = RunReport.model_validate_json(json.dumps(payload), strict=True)
    if pending is not None or expected_event is not None or report is None:
        raise ValueError("Incomplete admission trace")
    state = ledger.state
    if configurations[0].get("mode") != report.mode.value or (
        configurations[0].get("engine", "static") != report.engine
    ):
        raise ValueError("Report policy identity disagrees with configuration")
    if report.mode == "baseline" and (state["reserved_calls"] or denials):
        raise ValueError("Baseline must not request trusted verification")
    if report.verification is not None and report.verification != last_verification:
        raise ValueError("Report verification disagrees with completed evidence")
    if report.verified_success != (report.verification.passed if report.verification else None):
        raise ValueError("Report verified-success flag disagrees with its evidence")
    if (
        report.mode != "baseline"
        and report.claimed_success
        and (report.verification is None or not report.verification.passed)
    ):
        raise ValueError("Protected success requires completed positive verification")
    if (
        state["completed_verification_calls"] != work["completed_verification_calls"]
        or state["verification_errors"] != work["verification_errors"]
        or state["known_verified_target_rows"] != work["known_verified_target_rows"]
    ):
        raise ValueError("Admission counters disagree with observed verification work")
    if denials and (
        report.failure != "budget"
        or report.claimed_success
        or report.verified_success is not None
        or report.verification is not None
    ):
        raise ValueError("Budget denial must have an honest terminal budget outcome")
    if state["verification_errors"] and (report.failure != "internal" or report.claimed_success):
        raise ValueError("Admitted verification error must have an internal failure outcome")
    return {
        "schema_version": 1,
        "scope": "opt_in_verification_admission_trace_consistency",
        "admission_passed": True,
        "run_id": expected_run_id,
        "denied_verifications": denials,
        "final_state": state,
        "verification_work": work,
        "limitations": "Unsigned trace consistency only; no oracle execution or provenance proof.",
    }
