"""Portable common-corpus evidence; embedded source bytes are never executed."""

import json
import os
import re
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

from research.bounded_oracle_evidence import inventory, load, sha
from research.reflection_trace import reconcile_reflection_trace
from research.run_bounded_oracle import digest
from veriagent.benchmark import audit_rows, fault_recovery_eligible
from veriagent.benchmark_cases import BenchmarkCorpus
from veriagent.browser_archive import _extract
from veriagent.browser_evidence import _read
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
    return load(_read(path.parent, path.name))


def query(path, sql):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.set_progress_handler(lambda: 1, 1_000_000)
        return db.execute(sql).fetchall()


def read_state(path):
    return [list(r) for r in query(path, "SELECT id,status,version FROM issues ORDER BY id")]


def audit_condition(directory, row, case, plan):
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
        same(configuration["budget"], plan["budget_per_run"]),
        "Budget differs from plan",
    )
    if reflection:
        require(configuration["max_reflections"] == 2, "Corrective cap differs from plan")
    else:
        require(
            same(configuration["verification_limits"], dict(max_calls=None, max_target_rows=None)),
            "Trusted limits differ from plan",
        )
    records = query(
        directory / "traces.sqlite",
        "SELECT seq,run_id,timestamp,kind,payload FROM events ORDER BY seq",
    )
    require(all(r[1] == typed.run_id for r in records), "Foreign SQLite trace identity")
    sqlite_events = [dict(seq=r[0], timestamp=r[2], kind=r[3], payload=load(r[4])) for r in records]
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


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "runner-source.py": "runner_sha256",
    "reflection-auditor-source.py": "reflection_auditor_sha256",
    "support-source.py": "support_sha256",
}


def audit_directory(directory, expected_manifest_sha256):
    require(
        isinstance(expected_manifest_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256),
        "Require an external manifest SHA-256",
    )
    files = inventory(directory)
    require(files.get("manifest.json") == expected_manifest_sha256, "Manifest binding mismatch")
    manifest = read(directory / "manifest.json")
    plan = read(directory / "plan.json")
    lock = read(directory / "execution-lock.json")
    require(same(manifest["bindings"], lock), "Lock differs from execution")
    require(files["plan.json"] == lock["plan_sha256"], "Plan hash mismatch")
    for name, field in SOURCES.items():
        require(files[name] == lock[field], "Embedded source hash mismatch")
    corpus_raw = _read(directory, "corpus.json")
    require(sha(corpus_raw) == plan["corpus_sha256"], "Corpus hash mismatch")
    corpus = BenchmarkCorpus.model_validate_json(corpus_raw, strict=True)
    cases = {c.id: c for c in corpus.cases}
    conditions = plan["conditions"]
    require(
        type(plan["planned_runs"]) is int and plan["planned_runs"] == 96 and len(conditions) == 96,
        "Unexpected plan size",
    )
    require(
        len({(c["task_id"], c["scenario"], c["arm"]) for c in conditions}) == 96,
        "Duplicate assigned condition",
    )
    require(
        manifest["complete"] is True
        and manifest["active_condition"] is None
        and same([manifest["completed_runs"], manifest["planned_runs"]], [96, 96]),
        "Incomplete execution",
    )
    runs = manifest["runs"]
    require(
        len(runs) == 96 and same([r["condition"] for r in runs], conditions),
        "Assigned coverage mismatch",
    )
    require(len({r["run_id"] for r in runs}) == 96, "Duplicate run identity")
    bound = {"manifest.json", "plan.json", "execution-lock.json", "corpus.json", *SOURCES}
    audited = []
    for index, row in enumerate(runs, 1):
        name = f"trial-{index:03d}"
        require(
            row["directory"] == name and re.fullmatch(r"[0-9a-f]{32}", row["run_id"]),
            "Unexpected trial identity",
        )
        audited.append(
            audit_condition(directory / name, row, cases[row["condition"]["task_id"]], plan)
        )
        bound.update(f"{name}/{f}" for f in {*row["files_sha256"], "result.json"})
    require(set(files) == bound, "Unbound or missing evidence files")
    require(manifest["evidence_passed"] is True, "Manifest evidence flag mismatch")
    return dict(
        schema_version=1,
        consistency_passed=True,
        runs=96,
        files=len(files),
        manifest_sha256=expected_manifest_sha256,
        false_successes=sum(r["false_success"] for r in audited),
        limitations=(
            "Unsigned portable consistency; embedded sources never executed. "
            "Fault delivery not reenacted."
        ),
    )


def audit_archive(archive, expected_manifest_sha256):
    with tempfile.TemporaryDirectory(prefix="reflection-evidence-") as temporary:
        directory = Path(temporary)
        _extract(archive, directory)
        return audit_directory(directory, expected_manifest_sha256)


def package(source, archive, reference):
    source, archive = source.resolve(), archive.absolute()
    require(
        not archive.exists() and not archive.resolve().is_relative_to(source),
        "Require a new archive outside evidence tree",
    )
    expected = read(reference)["manifest_sha256"]
    members = {name: source / name for name in inventory(source)}
    extras = {
        "corpus.json": ROOT / "src/veriagent/scenarios/benchmark_tasks.json",
        "runner-source.py": ROOT / "research/run_reflection_comparison.py",
        "reflection-auditor-source.py": ROOT / "research/reflection_trace.py",
        "support-source.py": ROOT / "research/run_bounded_oracle.py",
    }
    require(not (members.keys() & extras.keys()), "Unexpected preexisting package metadata")
    members.update(extras)
    with tempfile.TemporaryDirectory(prefix="reflection-pack-", dir=archive.parent) as temporary:
        staged = Path(temporary) / "evidence.zip"
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, path in sorted(members.items()):
                output.writestr(name, _read(path.parent, path.name))
        result = audit_archive(staged, expected)
        os.link(staged, archive)
    return {**result, "archive_sha256": digest(archive), "archive_bytes": archive.stat().st_size}
