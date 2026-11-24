"""Descriptive verification work from complete, single-run benchmark traces."""

import json

from veriagent.models import Action, Observation, RunReport, Task, Verification

MAX_EVENTS = 20000


def _model(model, payload):
    return model.model_validate_json(json.dumps(payload, allow_nan=False), strict=True)


def verification_work(events: list[dict], *, expected_run_id: str) -> dict:
    """Reconcile trace counters; error-path verifier work remains unknown.

    Requires consecutive sequence numbers from a dedicated single-run TraceStore.
    This checks unsigned saved records, not authenticity or actual elapsed query cost.
    """
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError("Invalid trace event count")
    previous = None
    task = report = pending_action = None
    calls = errors = target_rows = actions = reads = writes = decisions = recoveries = 0
    for event in events:
        if not isinstance(event, dict) or (
            "run_id" in event and event["run_id"] != expected_run_id
        ):
            raise ValueError("Trace run identity mismatch")
        sequence = event.get("seq")
        if (
            type(sequence) is not int
            or sequence < 1
            or (previous is not None and sequence != previous + 1)
        ):
            raise ValueError("Trace sequence is incomplete or unordered")
        previous = sequence
        kind, payload = event.get("kind"), event.get("payload")
        if not isinstance(kind, str) or not isinstance(payload, dict):
            raise ValueError("Invalid trace event")
        if report is not None:
            if kind != "benchmark_audit":
                raise ValueError("Execution event follows final report")
            continue
        if kind == "task":
            if task is not None:
                raise ValueError("Duplicate task")
            task = _model(Task, payload)
        elif task is None:
            raise ValueError("Trace must begin with a task")
        elif kind == "verification":
            check = _model(Verification, payload)
            expected = {r.issue_id: r.status for r in task.requirements}
            actual = {row.issue_id: row.expected for row in check.evidence}
            if (
                actual != expected
                or len(check.evidence) != len(expected)
                or check.passed != all(row.actual == row.expected for row in check.evidence)
            ):
                raise ValueError("Verification evidence disagrees with task")
            calls += 1
            target_rows += len(check.evidence)
        elif kind == "verification_error":
            if payload.get("failure") != "internal":
                raise ValueError("Invalid verification error record")
            errors += 1
        elif kind == "action":
            if pending_action is not None:
                raise ValueError("Action lacks matching observation")
            pending_action = _model(Action, payload.get("action", payload))
        elif kind == "observation":
            observation = _model(Observation, payload)
            if pending_action is None or observation.action != pending_action:
                raise ValueError("Observation does not match admitted action")
            actions += 1
            reads += pending_action.tool == "read_issue"
            writes += pending_action.tool == "set_status"
            pending_action = None
        elif kind == "decision_context":
            decisions += 1
        elif kind == "recovery":
            recoveries += 1
        elif kind == "report":
            report = _model(RunReport, payload)
    if report is None or pending_action is not None:
        raise ValueError("Trace lacks a complete terminal report")
    if (
        report.run_id != expected_run_id
        or report.actions != actions
        or report.decisions != decisions
        or report.recovery_attempts != recoveries
    ):
        raise ValueError("Report counters disagree with trace")
    return {
        "schema_version": 1,
        "run_id": expected_run_id,
        "engine": report.engine,
        "mode": report.mode.value,
        "tool_actions": actions,
        "tool_reads": reads,
        "tool_writes": writes,
        "decisions": decisions,
        "recovery_admissions": recoveries,
        "completed_verification_calls": calls,
        "verification_errors": errors,
        "observed_verification_attempts": calls + errors,
        "known_verified_target_rows": target_rows,
        "verified_target_rows": None if errors else target_rows,
        "verification_work_complete": errors == 0,
        "limitations": (
            "Unsigned single-run trace reconciliation. Completed evidence rows count logical "
            "target reads, not total database work, time or money. Partial error-path work "
            "is unknown. Setup and final evaluator reads are excluded."
        ),
    }
