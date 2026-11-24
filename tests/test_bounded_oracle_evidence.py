import copy
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from research import bounded_oracle_evidence as evidence
from research import run_bounded_oracle as runner


@pytest.fixture
def bundle(tmp_path):
    plan = json.loads((runner.ROOT / "docs/review/bounded-oracle-plan.json").read_text())
    plan["source_sha256"] = {
        p.relative_to(runner.ROOT).as_posix(): runner.digest(p)
        for p in (runner.ROOT / "src/veriagent").rglob("*.py")
    }
    cases, budget = runner.validate_plan(plan)
    condition = plan["cases"][0]
    source = tmp_path / "source"
    source.mkdir()
    row = runner.run_condition(source / "trial-001", condition, plan, cases, budget)
    # A one-condition fixture exercises the same bounded evidence format, not a study.
    reduced = copy.deepcopy(plan)
    for key in ("task_id", "scenario", "mode"):
        reduced[{"task_id": "task_ids", "scenario": "scenarios", "mode": "modes"}[key]] = [
            condition[key]
        ]
    reduced["quota_profiles"] = {
        condition["quota_profile"]: plan["quota_profiles"][condition["quota_profile"]]
    }
    reduced.update(cases=[condition], planned_runs=1, expected_denied_runs=0)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(reduced), encoding="utf-8")
    corpus = runner.ROOT / "src/veriagent/scenarios/benchmark_tasks.json"
    code = Path(runner.__file__)
    manifest = {
        "schema_version": 1,
        "complete": True,
        "planned_runs": 1,
        "completed_runs": 1,
        "provider": "mock",
        "engine": "dynamic",
        "directory": "Z:/unavailable-original",
        "plan_sha256": runner.digest(plan_path),
        "corpus_sha256": plan["corpus_sha256"],
        "runner_sha256": runner.digest(code),
        "budget_per_run": plan["budget_per_run"],
        "runs": [row],
        "evidence_passed": True,
        "expectations_passed": True,
    }
    runner.save(source / "manifest.json", manifest)
    expected = runner.digest(source / "manifest.json")
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"manifest_sha256": expected}), encoding="utf-8")
    archive = tmp_path / "evidence.zip"
    result = evidence.package(
        source, archive, reference=reference, plan=plan_path, corpus=corpus, runner=code
    )
    return source, archive, expected, result, (reference, plan_path, corpus, code)


def test_portable_audit_never_follows_original_source_paths(bundle, tmp_path, monkeypatch):
    source, archive, expected, result, _ = bundle
    assert result["consistency_passed"] and result["files"] == 10
    moved = tmp_path / "other parent" / "renamed.zip"
    moved.parent.mkdir()
    shutil.copyfile(archive, moved)
    before = archive.read_bytes()
    original_read = evidence._read

    def guard(directory, name):
        if directory.resolve().is_relative_to(source.resolve()):
            pytest.fail("Archive audit must not follow original source references")
        return original_read(directory, name)

    monkeypatch.setattr(evidence, "_read", guard)
    audited = evidence.audit_archive(moved, expected)
    assert audited["consistency_passed"] and audited["runs"] == 1
    assert archive.read_bytes() == before == moved.read_bytes()


@pytest.mark.parametrize(
    "member",
    [
        "manifest.json",
        "plan.json",
        "corpus.json",
        "runner-source.py",
        "trial-001/state.sqlite",
        "trial-001/trace.json",
        "trial-001/admission-replay.json",
        "trial-001/result.json",
    ],
)
def test_modified_bound_payloads_are_rejected(bundle, tmp_path, member):
    _, archive, expected, _, _ = bundle
    altered = tmp_path / "altered.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(altered, "w") as target:
        for entry in source.infolist():
            target.writestr(
                entry.filename, b"tampered" if entry.filename == member else source.read(entry)
            )
    with pytest.raises(ValueError):
        evidence.audit_archive(altered, expected)


def test_unbound_extra_files_and_path_escape_are_rejected(bundle, tmp_path):
    _, archive, expected, _, _ = bundle
    for index, name in enumerate(["unbound.txt", "../escape.txt"]):
        altered = tmp_path / f"extra-{index}.zip"
        shutil.copyfile(archive, altered)
        with zipfile.ZipFile(altered, "a") as output:
            output.writestr(name, b"extra")
        with pytest.raises(ValueError):
            evidence.audit_archive(altered, expected)
    assert not (tmp_path / "escape.txt").exists()


def test_wrong_external_binding_is_rejected(bundle):
    _, archive, _, _, _ = bundle
    with pytest.raises(ValueError, match="Manifest differs"):
        evidence.audit_archive(archive, "0" * 64)


def test_tree_preflight_precedes_payload_access(tmp_path, monkeypatch):
    def reject(directory):
        raise ValueError("linked tree")

    def forbidden(*args):
        pytest.fail("Unsafe tree must be rejected before metadata payload reads")

    monkeypatch.setattr(evidence, "inventory", reject)
    monkeypatch.setattr(evidence, "_read", forbidden)
    with pytest.raises(ValueError, match="linked tree"):
        evidence.audit_directory(tmp_path, "0" * 64)


def test_package_failure_does_not_publish_or_modify_source(bundle, tmp_path):
    source, archive, _, _, metadata = bundle
    before = evidence.inventory(source)
    reference, plan, corpus, code = metadata
    with pytest.raises(ValueError):
        evidence.package(
            source, archive, reference=reference, plan=plan, corpus=corpus, runner=code
        )
    assert evidence.inventory(source) == before
    (source / "unbound.txt").write_bytes(b"not included silently")
    destination = tmp_path / "rejected.zip"
    with pytest.raises(ValueError):
        evidence.package(
            source, destination, reference=reference, plan=plan, corpus=corpus, runner=code
        )
    assert not destination.exists()
    assert not list(tmp_path.glob("bo-pack-*"))


@pytest.mark.parametrize("mutation", ["duplicate", "excessive", "wrong_provider", "expected_type"])
def test_plan_dimension_preflight_rejects_rebound_malformed_plan(bundle, tmp_path, mutation):
    _, archive, _, _, _ = bundle
    directory = tmp_path / "extracted"
    directory.mkdir()
    evidence._extract(archive, directory)
    path = directory / "plan.json"
    plan = json.loads(path.read_text())
    if mutation == "duplicate":
        plan["task_ids"] *= 2
    elif mutation == "excessive":
        plan["task_ids"] *= 121
    elif mutation == "wrong_provider":
        plan["provider"] = "openai"
    else:
        plan["cases"][0]["expected_claimed_success"] = 1
    path.write_text(json.dumps(plan), encoding="utf-8")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plan_sha256"] = runner.digest(path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        evidence.audit_directory(directory, runner.digest(manifest_path))
