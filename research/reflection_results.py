"""Read-only independent checks of a local common-corpus execution directory."""

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from research.reflection_trace import reconcile_reflection_trace
from research.run_bounded_oracle import digest, read_state
from research.run_reflection_comparison import LOCK, PLAN, bindings, validate_plan
from veriagent.benchmark import audit_rows, fault_recovery_eligible
from veriagent.models import RunReport
from veriagent.reflection import ReflectionReport
from veriagent.verification_admission_audit import reconcile_verification_admission


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(
        b, sort_keys=True, allow_nan=False
    )


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    require(path.stat().st_size <= 8 * 1024 * 1024, "Oversized local evidence")
    return json.loads(path.read_text(encoding="utf-8"))


def audit_condition(directory, row, case):
    require(same(read(directory / "result.json"), row), "Result differs from manifest")
    names = {
        "agent-report.json",
        "trace.json",
        "trace-replay.json",
        "state.sqlite",
        "traces.sqlite",
    }
    require(set(row["files_sha256"]) == names, "Unexpected evidence inventory")
    for name in names:
        require(digest(directory / name) == row["files_sha256"][name], "Evidence hash changed")
    report = read(directory / "agent-report.json")
    require(same(report, row["report"]), "Native report differs")
    reflection = row["condition"]["arm"] == "mock_self_reflection"
    typed = (ReflectionReport if reflection else RunReport).model_validate_json(
        json.dumps(report), strict=True
    )
    require(typed.run_id == row["run_id"], "Run identity mismatch")
    events = read(directory / "trace.json")
    configuration = events[1]["payload"]
    require(
        same(configuration["budget"], read(PLAN)["budget_per_run"]),
        "Budget differs from plan",
    )
    if reflection:
        require(configuration["max_reflections"] == 2, "Corrective cap differs from plan")
    else:
        require(
            same(configuration["verification_limits"], dict(max_calls=None, max_target_rows=None)),
            "Trusted limits differ from plan",
        )
    with closing(
        sqlite3.connect((directory / "traces.sqlite").as_uri() + "?mode=ro", uri=True)
    ) as db:
        records = db.execute(
            "SELECT seq,run_id,timestamp,kind,payload FROM events ORDER BY seq"
        ).fetchall()
    require(all(r[1] == typed.run_id for r in records), "Foreign SQLite trace identity")
    sqlite_events = [
        dict(seq=r[0], timestamp=r[2], kind=r[3], payload=json.loads(r[4])) for r in records
    ]
    require(same(events, sqlite_events), "SQLite and JSON traces differ")
    require(
        same(events[0]["payload"], case.task.model_dump(mode="json")), "Task differs from corpus"
    )
    replay = (reconcile_reflection_trace if reflection else reconcile_verification_admission)(
        events, expected_run_id=typed.run_id
    )
    require(same(replay, read(directory / "trace-replay.json")), "Saved replay differs")
    if reflection:
        require(row["live_ledger"] is None, "Reflection received a ledger")
        work, calls, rows, admissions = replay, 0, 0, typed.corrective_admissions
    else:
        require(same(row["live_ledger"], replay["final_state"]), "Live ledger mismatch")
        require(
            typed.mode.value == row["condition"]["arm"].removeprefix("dynamic_"), "Mode mismatch"
        )
        work = replay["verification_work"]
        calls, rows, admissions = (
            work["completed_verification_calls"],
            work["known_verified_target_rows"],
            typed.recovery_attempts,
        )
    resources = dict(
        actions=typed.actions,
        decisions=typed.decisions,
        tool_reads=work["tool_reads"],
        tool_writes=work["tool_writes"],
        trusted_verification_calls=calls,
        known_verified_target_rows=rows,
        policy_admissions=admissions,
        model_calls=typed.model_calls,
        model_tokens=typed.model_tokens,
    )
    require(same(resources, row["resources"]), "Resource vector mismatch")
    initial = [[i, s.value, 0] for i, s in sorted(case.initial_statuses.items())]
    final = read_state(directory / "state.sqlite")
    require(
        same(initial, row["initial_state"]) and same(final, row["final_state"]),
        "SQL snapshot mismatch",
    )
    passed, collateral = audit_rows(case.task, initial, final)
    require(
        same(
            [passed, collateral, typed.claimed_success, typed.claimed_success and not passed, True],
            [
                row["ground_truth_success"],
                row["untargeted_changed"],
                row["claimed_success"],
                row["false_success"],
                row["trace_consistency_passed"],
            ],
        ),
        "Outcome mismatch",
    )
    require(
        same(
            fault_recovery_eligible(case.task, row["realized_faults"]),
            row["fault_recovery_eligible"],
        ),
        "Exposure label mismatch",
    )
    return dict(
        condition=row["condition"],
        run_id=typed.run_id,
        ground_truth_success=passed,
        claimed_success=typed.claimed_success,
        false_success=typed.claimed_success and not passed,
        untargeted_changed=collateral,
        resources=resources,
        failure=typed.failure.value if typed.failure else None,
        fault_recovery_eligible=row["fault_recovery_eligible"],
        original_claimed_success=typed.original_claimed_success if reflection else None,
        verified_success=typed.verified_success,
        elapsed_ms=typed.elapsed_ms,
        realized_faults=row["realized_faults"],
        unused_faults=row["unused_faults"],
        result_sha256=digest(directory / "result.json"),
        files_sha256=row["files_sha256"],
    )


def audit(directory, expected_manifest_sha256):
    directory = Path(directory).resolve()
    require(
        digest(directory / "manifest.json") == expected_manifest_sha256, "Manifest hash mismatch"
    )
    plan = read(directory / "plan.json")
    cases, _ = validate_plan(plan)
    require(same(plan, read(PLAN)), "Copied plan differs")
    manifest = read(directory / "manifest.json")
    require(
        same(manifest["bindings"], bindings(PLAN))
        and same(read(directory / "execution-lock.json"), read(LOCK))
        and same(read(LOCK), bindings(PLAN)),
        "Execution bindings changed",
    )
    require(manifest["active_condition"] is None, "Execution retains an active condition")
    require(
        manifest["complete"] is True
        and manifest["completed_runs"] == 96
        and manifest["planned_runs"] == 96,
        "Incomplete execution",
    )
    runs = manifest["runs"]
    require(
        len(runs) == 96 and same([r["condition"] for r in runs], plan["conditions"]),
        "Assigned coverage mismatch",
    )
    require(len({r["run_id"] for r in runs}) == 96, "Duplicate run IDs")
    results = []
    for index, row in enumerate(runs, 1):
        require(
            row["directory"] == f"trial-{index:03d}"
            and re.fullmatch(r"[0-9a-f]{32}", row["run_id"]),
            "Unsafe or unexpected identity",
        )
        results.append(
            audit_condition(directory / row["directory"], row, cases[row["condition"]["task_id"]])
        )
    return dict(
        schema_version=1,
        consistency_passed=True,
        completed_runs=96,
        manifest_sha256=expected_manifest_sha256,
        conditions=results,
        limitations=(
            "Unsigned local evidence consistency; fault records are not independently reenacted. "
            "Fixed mock outcomes, not causal or stochastic evidence."
        ),
    )
