"""Package and independently recheck bounded-oracle evidence using relative bindings."""

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

from veriagent.benchmark_cases import BenchmarkCorpus
from veriagent.browser_archive import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES, _extract
from veriagent.browser_evidence import _read
from veriagent.models import Task
from veriagent.verification_admission_audit import reconcile_verification_admission

ROOT = Path(__file__).resolve().parents[1]
TRIAL_FILES = {
    "agent-report.json",
    "trace.json",
    "admission-replay.json",
    "state.sqlite",
    "traces.sqlite",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def load(raw):
    return json.loads(raw, object_pairs_hook=unique)


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def inventory(directory):
    files = {}
    total = 0
    for index, path in enumerate(directory.rglob("*"), 1):
        if (
            index > MAX_FILES * 2
            or path.is_symlink()
            or getattr(path, "is_junction", lambda: False)()
        ):
            raise ValueError("Linked or excessive evidence tree")
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Evidence escapes root")
        if path.is_dir():
            continue
        raw = _read(path.parent, path.name)
        files[path.relative_to(directory).as_posix()] = sha(raw)
        total += len(raw)
        if len(files) > MAX_FILES or total > MAX_TOTAL_BYTES:
            raise ValueError("Evidence tree exceeds limits")
    return files


def audit_directory(directory: Path, expected_manifest_sha256: str):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256):
        raise ValueError("Require an external expected manifest SHA-256")
    observed_files = inventory(directory)  # Reject linked/escaping trees before reading metadata.
    raw = _read(directory, "manifest.json")
    if sha(raw) != expected_manifest_sha256:
        raise ValueError("Manifest differs from expected binding")
    manifest = load(raw)
    plan_raw = _read(directory, "plan.json")
    if sha(plan_raw) != manifest["plan_sha256"]:
        raise ValueError("Plan binding mismatch")
    plan = load(plan_raw)
    corpus_raw = _read(directory, "corpus.json")
    if (
        sha(corpus_raw) != plan["corpus_sha256"]
        or manifest["corpus_sha256"] != plan["corpus_sha256"]
    ):
        raise ValueError("Corpus binding mismatch")
    corpus = BenchmarkCorpus.model_validate_json(corpus_raw)
    cases = {case.id: case for case in corpus.cases}
    if sha(_read(directory, "runner-source.py")) != manifest["runner_sha256"]:
        raise ValueError("Runner source binding mismatch")
    count = manifest["planned_runs"]
    if (
        type(count) is not int
        or not 1 <= count <= 120
        or manifest["complete"] is not True
        or (
            type(manifest["completed_runs"]) is not int
            or manifest["completed_runs"] != count
            or manifest["provider"] != "mock"
            or manifest["engine"] != "dynamic"
            or not same(manifest["budget_per_run"], plan["budget_per_run"])
            or count != plan["planned_runs"]
            or len(manifest["runs"]) != count
        )
    ):
        raise ValueError("Incomplete or incompatible manifest")
    dimensions = [plan["task_ids"], plan["scenarios"], plan["modes"], list(plan["quota_profiles"])]
    if (
        any(
            not isinstance(d, list)
            or not 1 <= len(d) <= 120
            or any(not isinstance(value, str) for value in d)
            or len(set(d)) != len(d)
            for d in dimensions
        )
        or math.prod(map(len, dimensions)) != count
        or (
            len(plan["cases"]) != count or plan["provider"] != "mock" or plan["engine"] != "dynamic"
        )
    ):
        raise ValueError("Plan dimensions are invalid or excessive")
    for condition in plan["cases"]:
        if any(
            type(condition["expected_" + key]) is not bool
            for key in ("ground_truth_success", "claimed_success")
        ) or (
            condition["expected_verified_success"] is not None
            and type(condition["expected_verified_success"]) is not bool
        ):
            raise ValueError("Invalid expected outcome types")

    def key(row):
        return tuple(row[k] for k in ("task_id", "scenario", "mode", "quota_profile"))

    expected = {key(row): row for row in plan["cases"]}
    product = set(
        itertools.product(
            plan["task_ids"], plan["scenarios"], plan["modes"], plan["quota_profiles"]
        )
    )
    if len(expected) != count or len(plan["cases"]) != count or set(expected) != product:
        raise ValueError("Plan coverage is inconsistent")
    bound = {"manifest.json", "plan.json", "corpus.json", "runner-source.py"}
    ids, conditions, directories = set(), set(), set()
    evidence_passed = expectations_passed = True
    denied = 0
    for row in manifest["runs"]:
        name = row["directory"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"trial-[0-9]{3}", name)
            or name in directories
        ):
            raise ValueError("Invalid or reused trial directory")
        directories.add(name)
        condition = key(row["condition"])
        if (
            condition in conditions
            or condition not in expected
            or not same(row["condition"], expected[condition])
        ):
            raise ValueError("Unexpected or reused condition")
        conditions.add(condition)
        if row["run_id"] in ids:
            raise ValueError("Reused run identity")
        ids.add(row["run_id"])
        trial = directory / name
        case = cases[row["condition"]["task_id"]]
        if set(row["files_sha256"]) != TRIAL_FILES:
            raise ValueError("Incomplete file bindings")
        for filename, expected_hash in row["files_sha256"].items():
            if sha(_read(trial, filename)) != expected_hash:
                raise ValueError("Trial file binding mismatch")
        if not same(load(_read(trial, "result.json")), row) or not same(
            load(_read(trial, "agent-report.json")), row["report"]
        ):
            raise ValueError("Result/report disagreement")
        events = load(_read(trial, "trace.json"))
        if not events or Task.model_validate_json(json.dumps(events[0]["payload"])) != case.task:
            raise ValueError("Trace task differs from bound corpus case")
        configuration = next(e["payload"] for e in events if e["kind"] == "configuration")
        if not same(
            configuration["verification_limits"],
            plan["quota_profiles"][row["condition"]["quota_profile"]],
        ) or not same(configuration["budget"], plan["budget_per_run"]):
            raise ValueError("Trace limits/budget differ from plan")
        with closing(
            sqlite3.connect((trial / "traces.sqlite").as_uri() + "?mode=ro", uri=True)
        ) as db:
            db.set_progress_handler(lambda: 1, 1_000_000)
            stored = [
                {"seq": s, "timestamp": t, "kind": k, "payload": load(p)}
                for s, t, k, p in db.execute(
                    "SELECT seq,timestamp,kind,payload FROM events WHERE run_id=? ORDER BY seq",
                    (row["run_id"],),
                )
            ]
        if not same(events, stored):
            raise ValueError("SQLite/JSON trace disagreement")
        replay = reconcile_verification_admission(events, expected_run_id=row["run_id"])
        if not same(replay, load(_read(trial, "admission-replay.json"))) or not same(
            replay["final_state"], row["live_ledger"]
        ):
            raise ValueError("Admission/live ledger disagreement")
        report = next(e["payload"] for e in events if e["kind"] == "report")
        if (
            not same(report, row["report"])
            or report["mode"] != row["condition"]["mode"]
            or (
                report["engine"] != "dynamic"
                or report["model_usage"]["provider"] != "mock"
                or report["model_calls"] != 0
                or report["model_tokens"] != 0
            )
        ):
            raise ValueError("Terminal report mismatch")
        with closing(
            sqlite3.connect((trial / "state.sqlite").as_uri() + "?mode=ro", uri=True)
        ) as db:
            db.set_progress_handler(lambda: 1, 1_000_000)
            final = [
                list(r) for r in db.execute("SELECT id,status,version FROM issues ORDER BY id")
            ]
        initial = [
            [issue, status.value, 0] for issue, status in sorted(case.initial_statuses.items())
        ]
        if not same(final, row["final_state"]) or not same(initial, row["initial_state"]):
            raise ValueError("Initial/final state mismatch")
        before, after = ({r[0]: r[1:] for r in rows} for rows in (initial, final))
        targets = {r.issue_id: r.status.value for r in case.task.requirements}
        passed = all(after.get(issue, [None])[0] == status for issue, status in targets.items())
        changed = any(
            before.get(issue) != after.get(issue)
            for issue in (before.keys() | after.keys()) - targets.keys()
        )
        denials = [
            e["payload"]
            for e in events
            if e["kind"] == "verification_budget" and e["payload"]["phase"] == "denied"
        ]
        writes = [
            e for e in events if e["kind"] == "action" and e["payload"].get("tool") == "set_status"
        ]
        actual = {
            "denial_phase": ("post_write" if writes else "initial") if denials else "none",
            "denial_reason": denials[0]["reason"] if denials else None,
            "ground_truth_success": passed,
            "claimed_success": report["claimed_success"],
            "failure": report["failure"],
            "verified_success": report["verified_success"],
        }
        mismatches = {
            k: {"expected": row["condition"]["expected_" + k], "actual": v}
            for k, v in actual.items()
            if row["condition"]["expected_" + k] != v
        }
        if (
            not same(actual, row["actual"])
            or not same(mismatches, row["expectation_mismatches"])
            or (
                row["untargeted_changed"] is not changed
                or row["false_success"] is not (report["claimed_success"] and not passed)
                or row["evidence_passed"] is not (not changed)
                or row["admission_passed"] is not True
            )
        ):
            raise ValueError("Recorded outcome labels disagree with evidence")
        evidence_passed &= not changed
        expectations_passed &= not mismatches
        denied += len(denials)
        bound.update(f"{name}/{filename}" for filename in TRIAL_FILES | {"result.json"})
    if conditions != set(expected) or set(observed_files) != bound:
        raise ValueError("Missing coverage or unbound files")
    if manifest["evidence_passed"] is not evidence_passed or (
        manifest["expectations_passed"] is not expectations_passed
    ):
        raise ValueError("Manifest flags disagree with recomputed outcomes")
    return {
        "schema_version": 1,
        "consistency_passed": True,
        "runs": count,
        "files": len(bound),
        "denied_runs": denied,
        "experiment_evidence_passed": evidence_passed,
        "expectations_passed": expectations_passed,
        "manifest_sha256": expected_manifest_sha256,
        "limitations": (
            "Unsigned bound-evidence consistency; embedded runner source is never executed."
        ),
    }


def audit_archive(archive: Path, expected_manifest_sha256: str):
    with tempfile.TemporaryDirectory(prefix="bo-evidence-") as temporary:
        directory = Path(temporary)
        _extract(archive, directory)
        return audit_directory(directory, expected_manifest_sha256)


def package(source, archive, *, reference, plan, corpus, runner):
    if archive.exists() or archive.resolve().is_relative_to(source.resolve()):
        raise ValueError("Require a new archive outside the source tree")
    expected = load(reference.read_bytes())["manifest_sha256"]
    with tempfile.TemporaryDirectory(prefix="bo-pack-", dir=archive.parent) as temporary:
        path = Path(temporary) / "evidence.zip"
        members = {name: source / name for name in inventory(source)}
        for name, provided in [
            ("plan.json", plan),
            ("corpus.json", corpus),
            ("runner-source.py", runner),
        ]:
            if name in members:
                raise ValueError("Unexpected preexisting package metadata")
            members[name] = provided
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, original in sorted(members.items()):
                raw = _read(original.parent, original.name)
                if len(raw) > MAX_FILE_BYTES:
                    raise ValueError("File exceeds limit")
                output.writestr(name, raw)
        result = audit_archive(path, expected)
        os.link(path, archive)
    return {
        **result,
        "archive": str(archive),
        "archive_sha256": sha(archive.read_bytes()),
        "archive_bytes": archive.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack")
    pack.add_argument("source", type=Path)
    pack.add_argument("archive", type=Path)
    pack.add_argument(
        "--reference", type=Path, default=ROOT / "docs/review/bounded-oracle-results.json"
    )
    pack.add_argument("--plan", type=Path, default=ROOT / "docs/review/bounded-oracle-plan.json")
    pack.add_argument(
        "--corpus", type=Path, default=ROOT / "src/veriagent/scenarios/benchmark_tasks.json"
    )
    pack.add_argument("--runner", type=Path, default=ROOT / "research/run_bounded_oracle.py")
    audit = commands.add_parser("audit")
    audit.add_argument("archive", type=Path)
    audit.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    if args.command == "pack":
        result = package(
            args.source,
            args.archive,
            reference=args.reference,
            plan=args.plan,
            corpus=args.corpus,
            runner=args.runner,
        )
    else:
        result = audit_archive(args.archive, args.manifest_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
