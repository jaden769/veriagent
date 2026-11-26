"""Pinned, mock-only common-corpus runner; execution is explicit and never resumes."""

import argparse
import itertools
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from research.reflection_trace import reconcile_reflection_trace
from research.run_bounded_oracle import digest, read_state, save
from veriagent.benchmark import fault_recovery_eligible
from veriagent.benchmark_cases import load_corpus
from veriagent.benchmark_faults import DEFAULT_SCENARIOS, ScheduledSandbox, scenario_faults
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
PLAN = ROOT / "docs/review/reflection-comparison-plan.json"
LOCK = ROOT / "docs/review/reflection-execution-lock.json"
ARMS = ["dynamic_baseline", "dynamic_verify", "dynamic_recover", "mock_self_reflection"]


def bindings(plan_path):
    return {
        "schema_version": 1,
        "plan_sha256": digest(plan_path),
        "runner_sha256": digest(Path(__file__)),
        "reflection_auditor_sha256": digest(ROOT / "research/reflection_trace.py"),
        "support_sha256": digest(ROOT / "research/run_bounded_oracle.py"),
    }


def validate_plan(plan):
    # Pin the entire reviewed specification, including metadata, ordering and types.
    if digest(PLAN) != "913babf753dcc1b58eb946deb62cc7cff77e5be02eb831cda9379916fcb69239":
        raise ValueError("Published plan bytes changed")
    reviewed = json.loads(PLAN.read_text(encoding="utf-8"))
    if json.dumps(plan, sort_keys=True) != json.dumps(reviewed, sort_keys=True):
        raise ValueError("Require the exact reviewed common-corpus plan")
    corpus, corpus_hash = load_corpus()
    if corpus_hash != plan["corpus_sha256"]:
        raise ValueError("Corpus fingerprint changed")
    sources = {
        p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT / "src/veriagent").rglob("*.py")
    }
    if sources != plan["source_sha256"]:
        raise ValueError("Source fingerprints changed")
    budget = Budget.model_validate_json(json.dumps(plan["budget_per_run"]), strict=True)
    conditions = []
    blocks = []
    for index, (task, scenario) in enumerate(
        itertools.product(plan["task_ids"], DEFAULT_SCENARIOS)
    ):
        order = ARMS[index % 4 :] + ARMS[: index % 4]
        blocks.append(dict(block=index + 1, task_id=task, scenario=scenario, arm_order=order))
        for position, arm in enumerate(order, 1):
            conditions.append(
                dict(
                    block=index + 1,
                    position=position,
                    task_id=task,
                    scenario=scenario,
                    arm=arm,
                    repetition=1,
                )
            )
    if plan["blocks"] != blocks or plan["conditions"] != conditions or len(conditions) != 96:
        raise ValueError("Require all 96 ordered conditions")
    return {case.id: case for case in corpus.cases}, budget


def run_condition(directory, condition, plan, cases, budget):
    directory.mkdir()
    case = cases[condition["task_id"]]
    faults, schedule = scenario_faults(condition["scenario"], budget.max_actions)
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
    return row


def execute(plan_path, lock_path, output):
    if plan_path.stat().st_size > 1024 * 1024 or lock_path.stat().st_size > 16384:
        raise ValueError("Oversized plan or lock")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases, budget = validate_plan(plan)
    binding = bindings(plan_path)
    if json.dumps(json.loads(lock_path.read_text(encoding="utf-8")), sort_keys=True) != json.dumps(
        binding, sort_keys=True
    ):
        raise ValueError("Execution lock does not bind current code and plan")
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    manifest = dict(
        schema_version=1,
        complete=False,
        planned_runs=96,
        completed_runs=0,
        provider="mock",
        bindings=binding,
        runs=[],
        active_condition=None,
        limitations="Fixed mock mechanisms; no equal-cost or stochastic claim.",
    )
    save(directory / "plan.json", plan)
    save(directory / "execution-lock.json", binding)
    save(directory / "manifest.json", manifest)
    try:
        for index, condition in enumerate(plan["conditions"], 1):
            manifest["active_condition"] = condition
            save(directory / "manifest.json", manifest)
            row = run_condition(directory / f"trial-{index:03d}", condition, plan, cases, budget)
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
    manifest["complete"] = len(ids) == len(set(ids)) == 96
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
