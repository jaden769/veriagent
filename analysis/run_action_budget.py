"""Pinned mock action-cap runner with a fixed fault-generation ceiling."""

import argparse
import itertools
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from research.reflection_evidence import audit_condition, require, same
from research.reflection_trace import reconcile_reflection_trace
from research.run_bounded_oracle import digest, read_state, save
from research.run_decision_budget import diagnostics
from veriagent.benchmark import fault_recovery_eligible
from veriagent.benchmark_cases import load_corpus
from veriagent.benchmark_faults import ScheduledSandbox, scenario_faults
from veriagent.bounded_verification import BudgetedStateVerifier
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget, Mode
from veriagent.planner import MockProvider
from veriagent.reflection import ReflectionAgent
from veriagent.trace import TraceStore
from veriagent.verification_admission_audit import reconcile_verification_admission
from veriagent.verification_budget import VerificationBudgetLedger, VerificationLimits

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/review/action-budget-plan.json"
LOCK = ROOT / "docs/review/action-budget-execution-lock.json"
PLAN_SHA = "698015632a2ef1e7b9dd3317a10aa9c6ec73c8779c9e74f76e95adf6de15f770"
ARMS = ["dynamic_baseline", "dynamic_verify", "dynamic_recover", "mock_self_reflection"]


def bindings(plan_path):
    files = [*sorted((ROOT / "research").glob("*.py")), Path(__file__)]
    return dict(
        schema_version=1,
        plan_sha256=digest(plan_path),
        execution_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in files},
    )


def budget_for(plan, cap):
    require(type(cap) is int and cap in plan["action_caps"], "Unknown action cap")
    return Budget.model_validate_json(
        json.dumps(dict(plan["fixed_budget"], max_actions=cap)), strict=True
    )


def configured_faults(plan, scenario):
    faults, schedule = scenario_faults(
        scenario, plan["fault_configuration"]["max_actions_argument"]
    )
    require(not schedule, "Unexpected indexed fault schedule")
    return asdict(faults)


def validate_plan(plan):
    require(digest(PLAN) == PLAN_SHA, "Published plan bytes changed")
    require(same(plan, json.loads(PLAN.read_text(encoding="utf-8"))), "Require exact reviewed plan")
    corpus, fingerprint = load_corpus()
    require(plan["corpus_sha256"] == fingerprint, "Corpus changed")
    require(
        same(
            plan["source_sha256"],
            {
                p.relative_to(ROOT).as_posix(): digest(p)
                for p in (ROOT / "src/veriagent").rglob("*.py")
            },
        ),
        "Product source changed",
    )
    require(
        plan["prior_results_sha256"] == digest(ROOT / "docs/review/decision-budget-results.json"),
        "Prior result binding changed",
    )
    expected = []
    for index, (task, scenario) in enumerate(
        itertools.product(plan["task_ids"], plan["scenarios"])
    ):
        caps = plan["action_caps"]
        order = caps[index % 3 :] + caps[: index % 3]
        for cap_position, cap in enumerate(order, 1):
            rotation = (index + cap_position - 1) % 4
            for arm_position, arm in enumerate(ARMS[rotation:] + ARMS[:rotation], 1):
                expected.append(
                    dict(
                        block=index + 1,
                        task_id=task,
                        scenario=scenario,
                        max_actions=cap,
                        cap_position=cap_position,
                        arm_position=arm_position,
                        arm=arm,
                        repetition=1,
                    )
                )
    require(
        len(expected) == 288 and same(expected, plan["conditions"]),
        "Require 288 ordered conditions",
    )
    for cap in plan["action_caps"]:
        budget_for(plan, cap)
    for scenario in plan["scenarios"]:
        configured_faults(plan, scenario)
    require(
        configured_faults(plan, "persistent_drop")["silent_drops"] == 13 > max(plan["action_caps"]),
        "Persistent fault ceiling changed",
    )
    return {c.id: c for c in corpus.cases}


def reconcile_condition(directory, row, case, plan, budget):
    result = audit_condition(
        directory, row, case, dict(budget_per_run=budget.model_dump(mode="json"))
    )
    require(same(row["budget"], budget.model_dump(mode="json")), "Recorded budget mismatch")
    require(
        type(row["condition"]["max_actions"]) is int
        and row["condition"]["max_actions"] == budget.max_actions,
        "Assigned action cap mismatch",
    )
    require(
        same(row["faults_configured"], configured_faults(plan, row["condition"]["scenario"])),
        "Fixed fault configuration mismatch",
    )
    require(
        same(row["stopping_diagnostics"], diagnostics(row, budget)), "Stopping diagnostics mismatch"
    )
    require(
        same(
            row["additional_resources"],
            dict(
                repeat_write_attempts=row["report"].get("repeat_write_attempts"),
                elapsed_ms=row["report"]["elapsed_ms"],
            ),
        ),
        "Additional resources mismatch",
    )
    return result


def run_condition(directory, condition, plan, cases, budget):
    directory.mkdir()
    case = cases[condition["task_id"]]
    faults, schedule = scenario_faults(
        condition["scenario"], plan["fault_configuration"]["max_actions_argument"]
    )
    configured = asdict(faults)
    sandbox = ScheduledSandbox(directory / "state.sqlite", faults, schedule)
    sandbox.seed()
    with closing(sqlite3.connect(sandbox.path)) as db, db:
        db.executemany(
            "UPDATE issues SET status=? WHERE id=?",
            [(s.value, issue) for issue, s in case.initial_statuses.items()],
        )
    initial = read_state(sandbox.path)
    traces = TraceStore(directory / "traces.sqlite")
    ledger = None
    if condition["arm"] == "mock_self_reflection":
        agent = ReflectionAgent(Executor(sandbox), traces, budget, max_reflections=2)
        report = agent.run(case.task)
    else:
        ledger = VerificationBudgetLedger(VerificationLimits())
        agent = DynamicAgent(
            MockProvider(),
            Executor(sandbox),
            BudgetedStateVerifier(sandbox.path, ledger),
            traces,
            budget,
        )
        report = agent.run(case.task, Mode(condition["arm"].removeprefix("dynamic_")))
    save(directory / "agent-report.json", report.model_dump(mode="json"))
    traces.export(report.run_id, directory / "trace.json")
    events = json.loads((directory / "trace.json").read_text(encoding="utf-8"))
    if ledger is None:
        replay = reconcile_reflection_trace(events, expected_run_id=report.run_id)
        work = replay
        admissions = report.corrective_admissions
        calls, rows = 0, 0
    else:
        replay = reconcile_verification_admission(events, expected_run_id=report.run_id)
        if replay["final_state"] != ledger.state:
            raise ValueError("Live ledger differs from replay")
        work = replay["verification_work"]
        admissions = report.recovery_attempts
        calls = work["completed_verification_calls"]
        rows = work["known_verified_target_rows"]
    save(directory / "trace-replay.json", replay)
    # Independent final audit occurs only after policy termination and never feeds it.
    final = read_state(sandbox.path)
    before, after = ({r[0]: r[1:] for r in state} for state in (initial, final))
    targets = {r.issue_id: r.status.value for r in case.task.requirements}
    passed = all(after.get(issue, [None])[0] == goal for issue, goal in targets.items())
    collateral = any(
        before.get(i) != after.get(i) for i in (before.keys() | after.keys()) - targets.keys()
    )
    row = {
        "condition": condition,
        "run_id": report.run_id,
        "directory": directory.name,
        "ground_truth_success": passed,
        "claimed_success": report.claimed_success,
        "false_success": report.claimed_success and not passed,
        "untargeted_changed": collateral,
        "trace_consistency_passed": True,
        "report": report.model_dump(mode="json"),
        "resources": {
            "actions": report.actions,
            "decisions": report.decisions,
            "tool_reads": work["tool_reads"],
            "tool_writes": work["tool_writes"],
            "trusted_verification_calls": calls,
            "known_verified_target_rows": rows,
            "policy_admissions": admissions,
            "model_calls": report.model_calls,
            "model_tokens": report.model_tokens,
        },
        "live_ledger": ledger.state if ledger else None,
        "initial_state": initial,
        "final_state": final,
        "faults_configured": configured,
        "unused_faults": asdict(faults),
        "realized_faults": sandbox.write_attempts,
        "fault_recovery_eligible": fault_recovery_eligible(case.task, sandbox.write_attempts),
        "files_sha256": {
            name: digest(directory / name)
            for name in (
                "agent-report.json",
                "trace.json",
                "trace-replay.json",
                "state.sqlite",
                "traces.sqlite",
            )
        },
    }
    save(directory / "result.json", row)
    row["budget"] = budget.model_dump(mode="json")
    row["stopping_diagnostics"] = diagnostics(row, budget)
    row["additional_resources"] = dict(
        repeat_write_attempts=row["report"].get("repeat_write_attempts"),
        elapsed_ms=row["report"]["elapsed_ms"],
    )
    save(directory / "result.json", row)
    reconcile_condition(directory, row, case, plan, budget)
    return row


def execute(plan_path, lock_path, output):
    require(
        plan_path.stat().st_size <= 1024 * 1024 and lock_path.stat().st_size <= 65536,
        "Oversized plan or lock",
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = validate_plan(plan)
    binding = bindings(plan_path)
    require(
        same(json.loads(lock_path.read_text(encoding="utf-8")), binding), "Execution lock changed"
    )
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    manifest = dict(
        schema_version=1,
        provider="mock",
        complete=False,
        planned_runs=288,
        completed_runs=0,
        bindings=binding,
        runs=[],
        active_condition=None,
    )
    save(directory / "plan.json", plan)
    save(directory / "execution-lock.json", binding)
    save(directory / "manifest.json", manifest)
    try:
        for index, condition in enumerate(plan["conditions"], 1):
            manifest["active_condition"] = condition
            save(directory / "manifest.json", manifest)
            row = run_condition(
                directory / f"trial-{index:03d}",
                condition,
                plan,
                cases,
                budget_for(plan, condition["max_actions"]),
            )
            manifest["runs"].append(row)
            manifest["completed_runs"] += 1
            manifest["active_condition"] = None
            save(directory / "manifest.json", manifest)
    except BaseException as exc:
        manifest["stop_reason"] = type(exc).__name__
        manifest["active_outcome"] = "unknown"
        save(directory / "manifest.json", manifest)
        raise
    ids = [r["run_id"] for r in manifest["runs"]]
    manifest["complete"] = len(ids) == len(set(ids)) == 288
    manifest["evidence_passed"] = manifest["complete"] and all(
        r["trace_consistency_passed"] for r in manifest["runs"]
    )
    save(directory / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.plan, args.lock, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "runs"}, indent=2))
    if not result["evidence_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
