"""Read-only replay of reflection phases and accounting; no policy or oracle execution."""

import json
import math

from veriagent.dynamic import normalized_feedback
from veriagent.executor import Executor, ToolPolicy
from veriagent.models import Action, Budget, Decision, Failure, Observation, Task
from veriagent.reflection import ReflectionReport, ReflectionState


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def model(cls, payload):
    return cls.model_validate_json(json.dumps(payload, allow_nan=False), strict=True)


def reconcile_reflection_trace(events, *, expected_run_id, policies=None):
    if not isinstance(events, list) or not 3 <= len(events) <= 20000:
        raise ValueError("Require a complete bounded reflection trace")
    if any(
        not isinstance(e, dict)
        or not isinstance(e.get("kind"), str)
        or not isinstance(e.get("payload"), dict)
        for e in events
    ):
        raise ValueError("Invalid reflection event frame")
    policies = (
        policies
        if policies is not None
        else {name: ToolPolicy(idempotent=True) for name in ("read_issue", "set_status")}
    )
    if set(policies) != {"read_issue", "set_status"} or any(
        not isinstance(p, ToolPolicy)
        or type(p.allowed) is not bool
        or type(p.idempotent) is not bool
        for p in policies.values()
    ):
        raise ValueError("Require explicit trusted tool policies")
    if events[0].get("kind") != "task" or events[1].get("kind") != "configuration":
        raise ValueError("Task and configuration must precede reflection execution")
    task = model(Task, events[0]["payload"])
    configuration = events[1]["payload"]
    if set(configuration) != {"comparator", "budget", "max_reflections", "trusted_oracle_access"}:
        raise ValueError("Incomplete reflection configuration")
    budget = model(Budget, configuration["budget"])
    limit = configuration["max_reflections"]
    if (
        type(limit) is not int
        or not 0 <= limit <= min(2, budget.max_retries)
        or not same(
            configuration,
            {
                "comparator": "mock_self_reflection",
                "budget": budget.model_dump(mode="json"),
                "max_reflections": limit,
                "trusted_oracle_access": False,
            },
        )
    ):
        raise ValueError("Invalid reflection configuration")
    stage, phase = "loop", "execute"
    feedback = []
    phase_start = actions = decisions = admissions = repeat_writes = corrective_writes = 0
    writes, reads = {}, {}
    original = None
    claimed = False
    failure = None
    trigger = pending = decision = None
    report = None
    deadline_required = False
    previous = None

    def action_allowed(action):
        try:
            Executor.authorize(task, action)
        except PermissionError:
            return False
        if action.tool == "set_status" and action.issue_id in writes:
            policy = policies[action.tool]
            return (
                phase == "reflect"
                and policy.allowed
                and policy.idempotent
                and reads.get(action.issue_id, -1) > writes[action.issue_id]
            )
        return True

    for index, event in enumerate(events):
        if not isinstance(event, dict) or (
            "run_id" in event and event["run_id"] != expected_run_id
        ):
            raise ValueError("Reflection trace identity mismatch")
        seq = event.get("seq")
        if type(seq) is not int or seq < 1 or (previous is not None and seq != previous + 1):
            raise ValueError("Incomplete or unordered reflection trace")
        previous = seq
        kind, payload = event.get("kind"), event.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Invalid reflection payload")
        if index < 2:
            continue
        if report is not None:
            if kind not in {"benchmark_audit", "experiment_audit"}:
                raise ValueError("Execution follows the terminal reflection report")
            continue
        if kind == "reflection_report":
            report = model(ReflectionReport, payload)
            if (
                not same(payload, report.model_dump(mode="json"))
                or not math.isfinite(report.elapsed_ms)
                or report.elapsed_ms < 0
            ):
                raise ValueError("Invalid reflection report types/time")
            deadline_hit = report.elapsed_ms >= budget.timeout_seconds * 1000
            if stage in {"claim", "action"}:
                deadline_required = True
                failure = Failure.BUDGET
            elif stage == "loop":
                if actions < budget.max_actions and decisions < budget.max_decisions:
                    deadline_required = True
                failure = Failure.BUDGET
            elif stage != "terminal":
                raise ValueError("Reflection report truncates an unfinished operation")
            if deadline_required and not deadline_hit:
                raise ValueError("Unexplained deadline termination")
            expected = {
                "run_id": expected_run_id,
                "original_claimed_success": original,
                "claimed_success": claimed,
                "verified_success": None,
                "actions": actions,
                "decisions": decisions,
                "corrective_admissions": admissions,
                "tool_writes": len([f for f in feedback if f.action.tool == "set_status"]),
                "repeat_write_attempts": repeat_writes,
                "corrective_write_attempts": corrective_writes,
                "failure": failure.value if failure else None,
                "model_calls": 0,
                "model_tokens": 0,
            }
            if any(not same(payload[key], value) for key, value in expected.items()):
                raise ValueError("Reflection report disagrees with replayed phases/counters/claims")
            continue
        if kind == "reflection_context" and stage == "loop":
            if actions >= budget.max_actions or decisions >= budget.max_decisions:
                raise ValueError("Decision admitted after shared budget exhaustion")
            expected = ReflectionState(
                phase=phase,
                feedback=tuple(
                    feedback[phase_start:][-16:] if phase == "reflect" else feedback[-16:]
                ),
                budget=budget,
                actions=actions,
                decisions=decisions,
                corrective_admissions=admissions,
            )
            model(ReflectionState, payload)
            if not same(payload, expected.model_dump(mode="json")):
                raise ValueError("Provider context disagrees with normalized phase feedback")
            decisions += 1
            stage = "decision"
        elif kind == "reflection_decision" and stage == "decision":
            decision = model(Decision, payload)
            stage = "claim" if decision.kind == "finish" else "action"
        elif kind == "reflection_decision_error" and stage == "decision":
            if payload != {"failure": "planning"}:
                raise ValueError("Invalid reflection decision error")
            stage, failure = "terminal", Failure.PLANNING
        elif kind == "reflection_claim" and stage == "claim":
            if not same(payload, {"phase": phase, "claimed_success": True}):
                raise ValueError("Claim phase or label is inconsistent")
            if phase == "execute":
                original, trigger, stage = True, "finish_proposal", "transition"
            else:
                claimed, stage = True, "terminal"
        elif kind == "reflection_transition" and stage == "transition":
            if (
                admissions >= limit
                or actions >= budget.max_actions
                or decisions >= budget.max_decisions
            ):
                raise ValueError("Corrective phase admitted after exhaustion")
            if not same(
                payload,
                {
                    "from_phase": phase,
                    "to_phase": "reflect",
                    "trigger": trigger,
                    "corrective_admission": admissions + 1,
                },
            ):
                raise ValueError("Invalid corrective transition or trigger")
            admissions += 1
            phase, phase_start, stage, trigger = "reflect", len(feedback), "loop", None
        elif kind == "reflection_stopped" and stage == "transition":
            if payload != {"reason": "admission_budget"}:
                raise ValueError("Invalid corrective admission stop")
            if (
                admissions < limit
                and actions < budget.max_actions
                and decisions < budget.max_decisions
            ):
                deadline_required = True
            failure, stage = Failure.BUDGET, "terminal"
        elif kind == "reflection_action_denied" and stage == "action":
            if payload != {"failure": "permission"} or action_allowed(decision.action):
                raise ValueError("Action denial disagrees with trusted authorization/retry policy")
            failure, stage = Failure.PERMISSION, "terminal"
        elif kind == "action" and stage == "action":
            pending = model(Action, payload)
            if pending != decision.action or not action_allowed(pending):
                raise ValueError(
                    "Action disagrees with decision or bypasses authorization/retry guard"
                )
            stage = "observation"
        elif kind == "observation" and stage == "observation":
            observation = model(Observation, payload)
            if observation.action != pending:
                raise ValueError("Observation/action mismatch")
            actions += 1
            feedback.append(normalized_feedback(observation))
            if pending.tool == "read_issue" and observation.reported_success:
                reads[pending.issue_id] = actions
            if pending.tool == "set_status":
                repeat_writes += pending.issue_id in writes
                corrective_writes += phase == "reflect"
                writes[pending.issue_id] = actions
            pending = None
            stage = "loop"
            if not observation.safe_to_continue:
                failure, stage = Failure.INTERNAL, "terminal"
            elif not observation.reported_success:
                if original is None:
                    original = False
                if observation.failure in {Failure.TRANSIENT, Failure.TIMEOUT}:
                    trigger, stage = "recoverable_tool_failure", "transition"
                else:
                    failure, stage = observation.failure or Failure.INTERNAL, "terminal"
        else:
            raise ValueError("Unexpected, oracle-bearing or out-of-order reflection event")
    if report is None:
        raise ValueError("Missing terminal reflection report")
    return {
        "schema_version": 1,
        "scope": "reflection_trace_consistency",
        "consistency_passed": True,
        "run_id": expected_run_id,
        "actions": actions,
        "decisions": decisions,
        "tool_reads": sum(f.action.tool == "read_issue" for f in feedback),
        "tool_writes": sum(f.action.tool == "set_status" for f in feedback),
        "corrective_admissions": admissions,
        "repeat_write_attempts": repeat_writes,
        "corrective_write_attempts": corrective_writes,
        "claimed_success": claimed,
        "original_claimed_success": original,
        "failure": failure.value if failure else None,
        "trusted_verification_calls": 0,
        "known_verified_target_rows": 0,
        "limitations": (
            "Unsigned phase/counter consistency, not final-state truth, policy authenticity "
            "or exact deadline proof."
        ),
    }
