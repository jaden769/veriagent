"""Full nested audits after moving real, sealed browser evaluation evidence."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from veriagent.browser_archive import archive_browser_controls, restore_browser_controls
from veriagent.browser_controls_audit import audit_browser_controls
from veriagent.browser_suite import review_browser_suite

pytestmark = pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)


def inventory(directory):
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def relocated(tmp_path_factory):
    root = tmp_path_factory.mktemp("portable")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "veriagent.cli",
            "evaluate-browser",
            "--satisfied-budget-boundaries",
            "--output",
            str(root / "original"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["passed"], result
    source = Path(result["artifacts"])
    before = inventory(source)
    destination = root / "different parent" / "renamed evaluation"
    destination.parent.mkdir()
    source.rename(destination)
    assert not source.exists()
    assert inventory(destination) == before
    return destination


def test_relocated_tree_passes_real_nested_audits_and_suite_review(relocated):
    before = inventory(relocated)
    saved = json.loads((relocated / "controls.json").read_text(encoding="utf-8"))
    assert not Path(saved["artifacts"]).exists()
    assert all(not Path(path).exists() for path in saved["batches"])
    audit = audit_browser_controls(relocated, require_contract=True)
    assert audit["evidence_passed"] and audit["controls_passed"], audit
    assert audit["matrix_contract"]["status"] == "matched"
    report = review_browser_suite([relocated], require_contract=True)
    assert report["evidence_passed"] and report["selection_passed"]
    assert report["counts"]["controls"] == 16
    assert report["counts"]["successful_tasks"] == 12
    assert report["counts"]["expected_task_failures"] == 4
    assert report["contract_coverage"]["matched"] == 1
    assert inventory(relocated) == before


def test_archive_roundtrip_passes_real_nested_audits(relocated, tmp_path):
    before = inventory(relocated)
    archive = tmp_path / "evaluation.zip"
    archive_browser_controls(relocated, archive, require_contract=True)
    destination = tmp_path / "restored"
    result = restore_browser_controls(archive, destination, require_contract=True)
    assert result["evidence_passed"] and result["controls_passed"]
    assert inventory(destination) == before == inventory(relocated)
    assert review_browser_suite([destination], require_contract=True)["counts"]["controls"] == 16


def test_legacy_archive_policy_with_real_nested_evidence(relocated, tmp_path):
    source = tmp_path / "legacy"
    shutil.copytree(relocated, source)
    controls = source / "controls.json"
    saved = json.loads(controls.read_text(encoding="utf-8"))
    saved["schema_version"] = 1
    del saved["matrix_contract"]
    controls.write_text(json.dumps(saved), encoding="utf-8")
    before = inventory(source)
    archive = tmp_path / "legacy.zip"
    created = archive_browser_controls(source, archive)
    assert created["matrix_contract"]["status"] == "legacy_missing"
    archive_before = archive.read_bytes()
    destination = tmp_path / "restored"
    restore_browser_controls(archive, destination)
    assert inventory(destination) == before == inventory(source)
    report = review_browser_suite([destination])
    assert report["counts"]["controls"] == 16
    assert report["contract_coverage"]["legacy_missing"] == 1
    strict = review_browser_suite([destination], require_contract=True)
    assert not strict["evidence_passed"] and strict["counts"] is None
    with pytest.raises(ValueError, match="audit failed"):
        archive_browser_controls(source, tmp_path / "strict.zip", require_contract=True)
    with pytest.raises(ValueError, match="audit failed"):
        restore_browser_controls(archive, tmp_path / "strict", require_contract=True)
    assert not (tmp_path / "strict.zip").exists() and not (tmp_path / "strict").exists()
    assert inventory(source) == before and archive.read_bytes() == archive_before
    assert not list(tmp_path.glob("veriagent-*"))


@pytest.mark.parametrize("mutation", ["missing_capture", "changed_manifest", "escaped_binding"])
def test_relocated_corruption_fails_closed_without_rewriting(relocated, tmp_path, mutation):
    destination = tmp_path / "copy"
    shutil.copytree(relocated, destination)
    path = destination / "controls.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    batch = destination / saved["batch_bindings"][0]["directory"]
    if mutation == "missing_capture":
        next(batch.rglob("before-001.png")).unlink()
    elif mutation == "changed_manifest":
        with (batch / "manifest.json").open("ab") as stream:
            stream.write(b"\n")
    else:
        saved["batch_bindings"][0]["directory"] = "../original"
        path.write_text(json.dumps(saved), encoding="utf-8")
    before = inventory(destination)
    report = review_browser_suite([destination], require_contract=True)
    assert not report["evidence_passed"]
    assert report["counts"] is None and report["controls_passed"] is None
    assert inventory(destination) == before
