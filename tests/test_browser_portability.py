"""Full nested audits after moving real, sealed browser evaluation evidence."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
