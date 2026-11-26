import copy
import shutil
import zipfile
from pathlib import Path

import pytest

from analysis import decision_budget_evidence as evidence
from research import reflection_evidence
from research import run_decision_budget as runner

ROOT = Path(__file__).resolve().parents[1]
COMPLETE = ROOT / "docs/evidence/decision-budget-complete-2026-11-26.zip"
PARTIAL = ROOT / "docs/evidence/decision-budget-partial-2026-11-26.zip"
FULL_HASH = "69c8aadd644bf5a6b79aec7d44dde6317f79c40abbd468a63fce2751f16a7d9f"
PART_HASH = "b9969491867c05b606ec14acafa7c3629289918dcfa3359dfc01ca221a1c9a8f"


@pytest.fixture
def bundle(tmp_path):
    plan = evidence.read(runner.PLAN)
    cases = runner.validate_plan(plan)
    source = tmp_path / "raw"
    source.mkdir()
    rows = [
        runner.run_condition(source / f"trial-{i:03d}", c, plan, cases)
        for i, c in enumerate(plan["conditions"][:4], 1)
    ]
    shutil.copyfile(runner.PLAN, source / "plan.json")
    shutil.copyfile(runner.LOCK, source / "execution-lock.json")
    manifest = dict(
        bindings=evidence.read(runner.LOCK),
        complete=False,
        planned_runs=288,
        completed_runs=4,
        active_condition=plan["conditions"][4],
        active_outcome="unknown",
        stop_reason="InjectedFixture",
        runs=rows,
    )
    runner.save(source / "manifest.json", manifest)
    expected = runner.digest(source / "manifest.json")
    reference = tmp_path / "reference.json"
    runner.save(
        reference,
        dict(manifest_sha256=expected, retained_partial_attempts=[dict(manifest_sha256=expected)]),
    )
    archive = tmp_path / "fixture.zip"
    result = evidence.package(source, archive, reference, attempt="partial")
    directory = tmp_path / "relocated"
    directory.mkdir()
    evidence._extract(archive, directory)
    return directory, expected, result, source, reference


def test_both_released_archives_without_original_or_repo_metadata(monkeypatch):
    def guard(original):
        def guarded(directory, name):
            value = str(directory)
            if (
                directory.resolve().is_relative_to(ROOT)
                or "4f378a29036346f999dcc9e479d2a20d" in value
                or "f14a6dd29f2a46b79fb193d3c9c2d839" in value
            ):
                pytest.fail("Followed original or repository metadata")
            return original(directory, name)

        return guarded

    monkeypatch.setattr(evidence, "_read", guard(evidence._read))
    monkeypatch.setattr(reflection_evidence, "_read", guard(reflection_evidence._read))
    full = evidence.audit_archive(COMPLETE, FULL_HASH)
    partial = evidence.audit_archive(PARTIAL, PART_HASH)
    assert full["study_complete"] and full["completed_runs"] == 288 and full["files"] == 1741
    assert (
        not partial["study_complete"]
        and partial["completed_runs"] == 206
        and partial["files"] == 1249
    )
    assert partial["active_outcome"] == "unknown"


def test_partial_fixture_retains_unknown_and_prefix(bundle):
    _, _, result, _, _ = bundle
    assert result["completed_runs"] == 4 and result["assigned_runs"] == 288
    assert not result["study_complete"] and result["files"] == 37


@pytest.mark.parametrize(
    "mutation",
    [
        "complete",
        "count",
        "active",
        "duplicate",
        "path",
        "resource",
        "diagnostic",
        "outcome",
        "source",
        "prior",
        "extra",
        "hash",
    ],
)
def test_reject_corruption(bundle, mutation):
    directory, expected, _, _, _ = bundle
    manifest = evidence.read(directory / "manifest.json")
    if mutation in {"source", "prior", "extra"}:
        name = {
            "source": "execution-sources/run_decision_budget.py",
            "prior": "prior-results.json",
            "extra": "unbound.txt",
        }[mutation]
        with (directory / name).open("ab") as stream:
            stream.write(b"changed")
    elif mutation == "hash":
        expected = "0" * 64
    else:
        if mutation == "complete":
            manifest["complete"] = True
        elif mutation == "count":
            manifest["completed_runs"] = True
        elif mutation == "active":
            manifest["active_condition"] = copy.deepcopy(manifest["runs"][0]["condition"])
        elif mutation == "duplicate":
            manifest["runs"][1]["run_id"] = manifest["runs"][0]["run_id"]
        elif mutation == "path":
            manifest["runs"][0]["directory"] = "../outside"
        else:
            row = manifest["runs"][0]
            if mutation == "resource":
                row["additional_resources"]["elapsed_ms"] += 1
            elif mutation == "diagnostic":
                row["stopping_diagnostics"]["decision_cap_reached"] = not row[
                    "stopping_diagnostics"
                ]["decision_cap_reached"]
            else:
                row["ground_truth_success"] = not row["ground_truth_success"]
            runner.save(directory / "trial-001/result.json", row)
        runner.save(directory / "manifest.json", manifest)
        expected = runner.digest(directory / "manifest.json")
    with pytest.raises(ValueError):
        evidence.audit_directory(directory, expected)


def test_wrong_attempt_category_not_published(bundle, tmp_path):
    _, _, _, source, reference = bundle
    target = tmp_path / "wrong.zip"
    with pytest.raises(ValueError, match="category"):
        evidence.package(source, target, reference, attempt="complete")
    assert not target.exists()


def test_overwrite_refused(tmp_path):
    target = tmp_path / "keep.zip"
    target.write_bytes(b"keep")
    with pytest.raises(ValueError, match="new archive"):
        evidence.package(tmp_path, target, tmp_path / "unused.json", attempt="partial")
    assert target.read_bytes() == b"keep"


def test_unsafe_archive_rejected(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", b"unsafe")
    with pytest.raises(ValueError):
        evidence.audit_archive(archive, FULL_HASH)
    assert not (tmp_path / "outside.txt").exists()
