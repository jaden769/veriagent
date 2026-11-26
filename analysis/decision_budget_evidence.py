"""Portable complete/partial decision-budget evidence with separate manifest bindings."""

import os
import re
import tempfile
import zipfile
from pathlib import Path

from research.bounded_oracle_evidence import inventory, load, sha
from research.reflection_evidence import require, same
from research.run_bounded_oracle import digest
from research.run_decision_budget import budget_for, reconcile_condition
from veriagent.benchmark_cases import BenchmarkCorpus
from veriagent.browser_archive import _extract
from veriagent.browser_evidence import _read

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return load(_read(path.parent, path.name))


def audit_directory(directory, expected_manifest_sha256):
    require(
        isinstance(expected_manifest_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256),
        "Require external manifest SHA-256",
    )
    files = inventory(directory)
    require(files.get("manifest.json") == expected_manifest_sha256, "Manifest binding mismatch")
    manifest = read(directory / "manifest.json")
    plan = read(directory / "plan.json")
    lock = read(directory / "execution-lock.json")
    require(same(manifest["bindings"], lock), "Execution lock mismatch")
    require(files["plan.json"] == lock["plan_sha256"], "Plan hash mismatch")
    sources = lock["research_sha256"]
    require(
        isinstance(sources, dict) and 1 <= len(sources) <= 100,
        "Unexpected execution source inventory",
    )
    bound = {
        "manifest.json",
        "plan.json",
        "execution-lock.json",
        "corpus.json",
        "prior-results.json",
    }
    for name, fingerprint in sources.items():
        require(re.fullmatch(r"research/[a-z_]+\.py", name), "Unsafe source identity")
        member = "execution-sources/" + name.removeprefix("research/")
        require(files.get(member) == fingerprint, "Embedded source hash mismatch")
        bound.add(member)
    corpus_raw = _read(directory, "corpus.json")
    require(sha(corpus_raw) == plan["corpus_sha256"], "Corpus mismatch")
    require(
        files["prior-results.json"] == plan["prior_results_sha256"], "Prior reference hash mismatch"
    )
    cases = {c.id: c for c in BenchmarkCorpus.model_validate_json(corpus_raw, strict=True).cases}
    require(
        type(plan["planned_runs"]) is int
        and plan["planned_runs"] == 288
        and len(plan["conditions"]) == 288,
        "Unexpected plan coverage",
    )
    count = manifest["completed_runs"]
    require(
        type(count) is int
        and 0 <= count <= 288
        and type(manifest["planned_runs"]) is int
        and manifest["planned_runs"] == 288,
        "Invalid completed count",
    )
    complete = manifest["complete"]
    require(type(complete) is bool, "Invalid completion flag")
    if complete:
        require(
            count == 288
            and manifest["active_condition"] is None
            and manifest["evidence_passed"] is True,
            "False complete coverage",
        )
    else:
        require(
            count < 288
            and same(manifest["active_condition"], plan["conditions"][count])
            and manifest["active_outcome"] == "unknown"
            and isinstance(manifest["stop_reason"], str),
            "Partial active identity mismatch",
        )
    rows = manifest["runs"]
    require(
        len(rows) == count and same([r["condition"] for r in rows], plan["conditions"][:count]),
        "Assigned prefix coverage mismatch",
    )
    require(len({r["run_id"] for r in rows}) == count, "Duplicate run identity")
    false_claims = 0
    for index, row in enumerate(rows, 1):
        name = f"trial-{index:03d}"
        require(
            row["directory"] == name and re.fullmatch(r"[0-9a-f]{32}", row["run_id"]),
            "Unsafe trial identity",
        )
        budget = budget_for(plan, row["condition"]["max_decisions"])
        audited = reconcile_condition(
            directory / name, row, cases[row["condition"]["task_id"]], budget
        )
        false_claims += audited["false_success"]
        bound.update(f"{name}/{f}" for f in {*row["files_sha256"], "result.json"})
    require(set(files) == bound, "Unbound or missing evidence files")
    return dict(
        schema_version=1,
        consistency_passed=True,
        study_complete=complete,
        assigned_runs=288,
        completed_runs=count,
        active_outcome=None if complete else "unknown",
        files=len(files),
        manifest_sha256=expected_manifest_sha256,
        false_successes=false_claims,
        limitations=(
            "Unsigned portable consistency. Partial prefix is not complete study coverage. "
            "Embedded sources never executed; fault delivery not reenacted."
        ),
    )


def audit_archive(archive, expected_manifest_sha256):
    with tempfile.TemporaryDirectory(prefix="decision-evidence-") as temporary:
        directory = Path(temporary)
        _extract(archive, directory)
        return audit_directory(directory, expected_manifest_sha256)


def package(source, archive, reference, *, attempt):
    source, archive = source.resolve(), archive.absolute()
    require(
        not archive.exists() and not archive.resolve().is_relative_to(source),
        "Require new archive outside raw tree",
    )
    record = read(reference)
    require(attempt in {"complete", "partial"}, "Select explicit attempt type")
    if attempt == "complete":
        expected = record["manifest_sha256"]
    else:
        require(len(record["retained_partial_attempts"]) == 1, "Select a unique partial attempt")
        expected = record["retained_partial_attempts"][0]["manifest_sha256"]
    members = {name: source / name for name in inventory(source)}
    lock = read(source / "execution-lock.json")
    extras = {
        "corpus.json": ROOT / "src/veriagent/scenarios/benchmark_tasks.json",
        "prior-results.json": ROOT / "docs/review/reflection-comparison-results.json",
    }
    for name in lock["research_sha256"]:
        require(re.fullmatch(r"research/[a-z_]+\.py", name), "Unsafe source identity")
        extras["execution-sources/" + name.removeprefix("research/")] = ROOT / name
    require(not (members.keys() & extras.keys()), "Preexisting package metadata")
    members.update(extras)
    with tempfile.TemporaryDirectory(prefix="decision-pack-", dir=archive.parent) as temporary:
        staged = Path(temporary) / "evidence.zip"
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, path in sorted(members.items()):
                output.writestr(name, _read(path.parent, path.name))
        result = audit_archive(staged, expected)
        require(result["study_complete"] is (attempt == "complete"), "Wrong attempt category")
        os.link(staged, archive)
    return {
        **result,
        "archive": archive.name,
        "archive_sha256": digest(archive),
        "archive_bytes": archive.stat().st_size,
    }
