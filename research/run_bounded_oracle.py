"""Execute the reviewed 72-condition mock plan, retaining failures and raw evidence."""

import argparse
import hashlib
import itertools
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from veriagent.benchmark import fault_recovery_eligible
from veriagent.benchmark_cases import load_corpus
from veriagent.benchmark_faults import ScheduledSandbox, scenario_faults
from veriagent.bounded_verification import BudgetedStateVerifier
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget, Mode
from veriagent.planner import MockProvider
from veriagent.trace import TraceStore
from veriagent.verification_admission_audit import reconcile_verification_admission
from veriagent.verification_budget import VerificationBudgetLedger, VerificationLimits

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FIELDS = (
    "denial_phase",
    "denial_reason",
    "ground_truth_success",
    "claimed_success",
    "failure",
    "verified_success",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_plan(plan):
    if (
        type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("engine") != "dynamic"
        or plan.get("provider") != "mock"
        or plan.get("repeats") != 1
        or type(plan["repeats"]) is not int
        or plan.get("planned_runs") != 72
        or type(plan["planned_runs"]) is not int
    ):
        raise ValueError("Require the reviewed dynamic mock-only 72-run plan")
    corpus, corpus_hash = load_corpus()
    if plan["corpus_sha256"] != corpus_hash:
        raise ValueError("Corpus fingerprint changed")
    actual_sources = {
        p.relative_to(ROOT).as_posix(): digest(p) for p in (ROOT / "src/veriagent").rglob("*.py")
    }
    if plan["source_sha256"] != actual_sources:
        raise ValueError("Source fingerprints changed; revise the plan explicitly")
    if plan["task_ids"] != ["single_done", "already_satisfied", "partial_satisfied"] or (
        plan["scenarios"] != ["clean", "silent_drop"] or plan["modes"] != [m.value for m in Mode]
    ):
        raise ValueError("Unexpected condition selection")
    expected_profiles = {
        "zero_calls": {"max_calls": 0, "max_target_rows": None},
        "one_call": {"max_calls": 1, "max_target_rows": None},
        "one_row": {"max_calls": None, "max_target_rows": 1},
        "unlimited": {"max_calls": None, "max_target_rows": None},
    }
    if json.dumps(plan["quota_profiles"], sort_keys=True) != json.dumps(
        expected_profiles, sort_keys=True
    ):
        raise ValueError("Unexpected quota profiles")
    expected_budget = Budget(max_actions=8, max_decisions=8, timeout_seconds=60)
    budget = Budget.model_validate_json(json.dumps(plan["budget_per_run"]), strict=True)
    if budget != expected_budget:
        raise ValueError("Unexpected execution budget")
    rows = plan["cases"]
    keys = [(r["task_id"], r["scenario"], r["mode"], r["quota_profile"]) for r in rows]
    expected = set(
        itertools.product(
            plan["task_ids"], plan["scenarios"], plan["modes"], plan["quota_profiles"]
        )
    )
    if len(keys) != 72 or len(set(keys)) != 72 or set(keys) != expected:
        raise ValueError("Plan must cover all 72 unique conditions")
    for row in rows:
        if row["expected_denial_phase"] not in {"none", "initial", "post_write"}:
            raise ValueError("Invalid predicted denial phase")
        if row["expected_denial_reason"] not in {
            None,
            "verification_calls_exhausted",
            "verification_target_rows_exhausted",
        } or (row["expected_denial_phase"] == "none") != (row["expected_denial_reason"] is None):
            raise ValueError("Invalid predicted denial reason")
        if any(
            type(row["expected_" + key]) is not bool
            for key in ("ground_truth_success", "claimed_success")
        ):
            raise ValueError("Expected outcomes must be booleans")
        if row["expected_failure"] not in {None, "budget", "state_mismatch"} or (
            row["expected_verified_success"] is not None
            and type(row["expected_verified_success"]) is not bool
        ):
            raise ValueError("Invalid predicted report outcome")
    if type(plan["expected_denied_runs"]) is not int or plan["expected_denied_runs"] != sum(
        row["expected_denial_phase"] != "none" for row in rows
    ):
        raise ValueError("Predicted denial inventory is inconsistent")
    return {case.id: case for case in corpus.cases}, budget


def read_state(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        return [list(row) for row in db.execute("SELECT id,status,version FROM issues ORDER BY id")]


def run_condition(directory, condition, plan, cases, budget):
    directory.mkdir()
    case = cases[condition["task_id"]]
    faults, schedule = scenario_faults(condition["scenario"], budget.max_actions)
    configured_faults = asdict(faults)
    sandbox = ScheduledSandbox(directory / "state.sqlite", faults, schedule)
    sandbox.seed()
    with closing(sqlite3.connect(sandbox.path)) as db, db:
        db.executemany(
            "UPDATE issues SET status=? WHERE id=?",
            [(status.value, issue) for issue, status in case.initial_statuses.items()],
        )
    initial = read_state(sandbox.path)
    ledger = VerificationBudgetLedger(
        VerificationLimits(**plan["quota_profiles"][condition["quota_profile"]])
    )
    traces = TraceStore(directory / "traces.sqlite")
    report = DynamicAgent(
        MockProvider(),
        Executor(sandbox),
        BudgetedStateVerifier(sandbox.path, ledger),
        traces,
        budget,
    ).run(case.task, Mode(condition["mode"]))
    save(directory / "agent-report.json", report.model_dump(mode="json"))
    traces.export(report.run_id, directory / "trace.json")
    events = json.loads((directory / "trace.json").read_text())
    final = read_state(sandbox.path)
    before, after = ({row[0]: row[1:] for row in state} for state in (initial, final))
    targets = {r.issue_id: r.status.value for r in case.task.requirements}
    passed = all(after.get(issue, [None])[0] == status for issue, status in targets.items())
    changed = any(
        before.get(issue) != after.get(issue)
        for issue in (before.keys() | after.keys()) - targets.keys()
    )
    replay = reconcile_verification_admission(events, expected_run_id=report.run_id)
    save(directory / "admission-replay.json", replay)
    state_matches = replay["final_state"] == ledger.state
    denials = [
        e["payload"]
        for e in events
        if e["kind"] == "verification_budget" and e["payload"]["phase"] == "denied"
    ]
    actual = {
        "denial_phase": ("post_write" if sandbox.write_attempts else "initial")
        if denials
        else "none",
        "denial_reason": denials[0]["reason"] if denials else None,
        "ground_truth_success": passed,
        "claimed_success": report.claimed_success,
        "failure": report.failure.value if report.failure else None,
        "verified_success": report.verified_success,
    }
    mismatches = {
        key: {"expected": condition["expected_" + key], "actual": actual[key]}
        for key in EXPECTED_FIELDS
        if condition["expected_" + key] != actual[key]
    }
    row = {
        "condition": condition,
        "run_id": report.run_id,
        "directory": directory.name,
        "actual": actual,
        "expectation_mismatches": mismatches,
        "evidence_passed": state_matches and not changed,
        "admission_passed": replay["admission_passed"],
        "live_ledger": ledger.state,
        "untargeted_changed": changed,
        "false_success": report.claimed_success and not passed,
        "initial_state": initial,
        "final_state": final,
        "report": report.model_dump(mode="json"),
        "faults_configured": configured_faults,
        "faults_remaining": asdict(faults),
        "write_attempts": sandbox.write_attempts,
        "fault_recovery_eligible": fault_recovery_eligible(case.task, sandbox.write_attempts),
        "files_sha256": {
            name: digest(directory / name)
            for name in [
                "agent-report.json",
                "trace.json",
                "admission-replay.json",
                "state.sqlite",
                "traces.sqlite",
            ]
        },
    }
    save(directory / "result.json", row)
    return row


def execute(plan_path, output):
    raw = plan_path.read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError("Plan exceeds 1 MiB")
    plan = json.loads(raw)
    cases, budget = validate_plan(plan)  # Before any output or provider construction.
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "complete": False,
        "planned_runs": len(plan["cases"]),
        "completed_runs": 0,
        "directory": str(directory),
        "provider": "mock",
        "engine": "dynamic",
        "plan_sha256": hashlib.sha256(raw).hexdigest(),
        "runner_sha256": digest(Path(__file__)),
        "corpus_sha256": plan["corpus_sha256"],
        "budget_per_run": plan["budget_per_run"],
        "runs": [],
        "evidence_passed": None,
        "expectations_passed": None,
    }
    save(directory / "manifest.json", manifest)
    try:
        for index, condition in enumerate(plan["cases"], 1):
            manifest["active_condition"] = condition
            save(directory / "manifest.json", manifest)
            row = run_condition(directory / f"trial-{index:03d}", condition, plan, cases, budget)
            manifest["runs"].append(row)
            manifest["completed_runs"] += 1
            manifest.pop("active_condition", None)
            save(directory / "manifest.json", manifest)
    except BaseException as exc:
        manifest["stop_reason"] = type(exc).__name__
        save(directory / "manifest.json", manifest)
        raise
    ids = [row["run_id"] for row in manifest["runs"]]
    manifest["complete"] = True
    manifest["evidence_passed"] = len(set(ids)) == len(ids) and all(
        row["evidence_passed"] for row in manifest["runs"]
    )
    manifest["expectations_passed"] = all(
        not row["expectation_mismatches"] for row in manifest["runs"]
    )
    save(directory / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "docs/review/bounded-oracle-plan.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.plan, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "runs"}, indent=2))
    if not result["evidence_passed"] or not result["expectations_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
