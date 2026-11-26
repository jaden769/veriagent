"""Pinned mock decision-cap sensitivity runner; no automatic resume or live provider."""

import argparse
import itertools
import json
from pathlib import Path
from uuid import uuid4

from research.reflection_evidence import audit_condition, require, same
from research.run_bounded_oracle import digest, save
from research.run_reflection_comparison import ARMS
from research.run_reflection_comparison import run_condition as run_base_condition
from veriagent.benchmark_cases import load_corpus
from veriagent.models import Budget

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/review/decision-budget-plan.json"
LOCK = ROOT / "docs/review/decision-budget-execution-lock.json"
PLAN_SHA = "5b7a96df05794fc2fe5e284641331f4f189e18f50aea672d8724fcab79b18f3f"


def bindings(plan_path):
    return dict(
        schema_version=1,
        plan_sha256=digest(plan_path),
        research_sha256={
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted((ROOT / "research").glob("*.py"))
        },
    )


def validate_plan(plan):
    require(digest(PLAN) == PLAN_SHA, "Published plan bytes changed")
    require(same(plan, json.loads(PLAN.read_text(encoding="utf-8"))), "Require exact reviewed plan")
    corpus, fingerprint = load_corpus()
    require(plan["corpus_sha256"] == fingerprint, "Corpus changed")
    sources = {
        p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT / "src/veriagent").rglob("*.py")
    }
    require(same(plan["source_sha256"], sources), "Product source changed")
    require(
        plan["prior_results_sha256"]
        == digest(ROOT / "docs/review/reflection-comparison-results.json"),
        "Prior result binding changed",
    )
    expected = []
    for index, (task, scenario) in enumerate(
        itertools.product(plan["task_ids"], plan["scenarios"])
    ):
        caps = plan["decision_caps"]
        order = caps[index % 3 :] + caps[: index % 3]
        for cap_position, cap in enumerate(order, 1):
            rotation = (index + cap_position - 1) % 4
            for position, arm in enumerate(ARMS[rotation:] + ARMS[:rotation], 1):
                expected.append(
                    dict(
                        block=index + 1,
                        task_id=task,
                        scenario=scenario,
                        max_decisions=cap,
                        cap_position=cap_position,
                        arm_position=position,
                        arm=arm,
                        repetition=1,
                    )
                )
    require(
        len(expected) == 288 and same(expected, plan["conditions"]),
        "Require 288 ordered conditions",
    )
    for cap in plan["decision_caps"]:
        budget_for(plan, cap)
    return {c.id: c for c in corpus.cases}


def budget_for(plan, cap):
    require(type(cap) is int and cap in plan["decision_caps"], "Unknown decision cap")
    return Budget.model_validate_json(
        json.dumps(dict(plan["fixed_budget"], max_decisions=cap)), strict=True
    )


def diagnostics(row, budget):
    report = row["report"]
    reflection = row["condition"]["arm"] == "mock_self_reflection"
    return dict(
        action_cap_reached=report["actions"] >= budget.max_actions,
        decision_cap_reached=report["decisions"] >= budget.max_decisions,
        corrective_cap_reached=report[
            "corrective_admissions" if reflection else "recovery_attempts"
        ]
        >= budget.max_retries,
        reported_deadline_reached=report["elapsed_ms"] >= budget.timeout_seconds * 1000,
        failure=report["failure"],
        achieved_goal_with_budget_failure=row["ground_truth_success"]
        and report["failure"] == "budget",
        limitations="Counter/deadline flags may overlap; not a unique causal stopping diagnosis.",
    )


def reconcile_condition(directory, row, case, budget):
    # Existing portable auditor reads native traces/counters and independently rereads SQL.
    audited = audit_condition(
        directory, row, case, dict(budget_per_run=budget.model_dump(mode="json"))
    )
    require(same(row["budget"], budget.model_dump(mode="json")), "Recorded budget mismatch")
    require(row["condition"]["max_decisions"] == budget.max_decisions, "Assigned cap mismatch")
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
    require(
        same(row["stopping_diagnostics"], diagnostics(row, budget)), "Stopping diagnostics mismatch"
    )
    return audited


def run_condition(directory, condition, plan, cases):
    budget = budget_for(plan, condition["max_decisions"])
    row = run_base_condition(directory, condition, plan, cases, budget)
    row["budget"] = budget.model_dump(mode="json")
    row["stopping_diagnostics"] = diagnostics(row, budget)
    row["additional_resources"] = dict(
        repeat_write_attempts=row["report"].get("repeat_write_attempts"),
        elapsed_ms=row["report"]["elapsed_ms"],
    )
    save(directory / "result.json", row)
    reconcile_condition(directory, row, cases[condition["task_id"]], budget)
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
            row = run_condition(directory / f"trial-{index:03d}", condition, plan, cases)
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
