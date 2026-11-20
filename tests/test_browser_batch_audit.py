import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from test_browser_evidence import bundle as bundle

from veriagent.benchmark_cases import load_corpus
from veriagent.browser_batch import browser_batch, summarize
from veriagent.browser_batch_audit import audit_browser_batch
from veriagent.browser_evidence import seal_browser_evidence


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def batch(bundle, tmp_path):
    directory = tmp_path / "batch"
    target = directory / "trial-001" / ("1" * 32)
    target.parent.mkdir(parents=True)
    bundle.rename(target)
    saved = json.loads((target / "result.json").read_text())
    for rows in (saved["initial_state"], saved["final_state"]):
        rows.extend(
            dict(id=f"ISSUE-{i}", title="Untouched", status="open", version=0) for i in (2, 3)
        )
    saved["result"]["browser"].update(scenario="clean", pending_application_faults=0)
    write_json(target / "result.json", saved)
    events = json.loads((target / "application-events.json").read_text())
    events[0].update(attempt=1, injected=None)
    write_json(target / "application-events.json", events)
    seal_browser_evidence(target)
    row = dict(
        task_id="single_done",
        scenario="clean",
        mode="recover",
        repeat=0,
        approval_digest=saved["approval_digest"],
        artifacts=str(target),
        bundle_directory="trial-001/" + "1" * 32,
        inventory_sha256=hashlib.sha256((target / "evidence.json").read_bytes()).hexdigest(),
        fault_exposed=False,
        claimed_success=True,
        audit_passed=True,
        execution_passed=True,
        actions=1,
        recovery_attempts=0,
        application_write_attempts=1,
        commits=1,
        events_dropped=0,
        planned_fault_attempt=None,
        injected_attempts=[],
        pending_application_faults=0,
        planned_faults=[],
        max_retries=2,
        target_statuses={"ISSUE-1": "done"},
        target_versions={"ISSUE-1": 1},
        untargeted_issues_unchanged=True,
        target_titles_unchanged=True,
    )
    manifest = dict(
        schema_version=1,
        status="complete",
        provider="mock",
        engine="static",
        corpus_sha256=load_corpus()[1],
        budget=saved["budget"],
        artifacts=str(directory),
        configuration=dict(
            tasks=["single_done"], scenarios=["clean"], modes=["recover"], repeats=1
        ),
        trials=[row],
        summaries=summarize([row]),
    )
    write_json(directory / "manifest.json", manifest)
    return directory


def test_complete_batch_is_read_only_and_supports_moving(batch, tmp_path):
    moved = tmp_path / "moved"
    batch.rename(moved)
    before = {p.relative_to(moved): p.read_bytes() for p in moved.rglob("*") if p.is_file()}
    result = audit_browser_batch(moved)
    assert result["evidence_passed"], result
    assert before == {p.relative_to(moved): p.read_bytes() for p in moved.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "summary",
        "row",
        "interrupted",
        "corpus",
        "external",
        "missing_bundle",
    ],
)
def test_inconsistent_batch_is_rejected(batch, mutation):
    path = batch / "manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "missing":
        manifest["trials"] = []
    elif mutation == "duplicate":
        manifest["trials"].append(manifest["trials"][0])
    elif mutation == "summary":
        manifest["summaries"][0]["execution_passes"] = 9
    elif mutation == "row":
        manifest["trials"][0]["commits"] = 2
        manifest["summaries"] = summarize(manifest["trials"])
    elif mutation == "interrupted":
        manifest["status"] = "interrupted"
    elif mutation == "corpus":
        manifest["corpus_sha256"] = "wrong"
    elif mutation == "external":
        manifest["trials"][0]["bundle_directory"] = "../outside"
    else:
        (batch / manifest["trials"][0]["bundle_directory"] / "evidence.json").unlink()
    write_json(path, manifest)
    assert not audit_browser_batch(batch)["evidence_passed"]


def test_reused_run_cannot_masquerade_as_another_repeat(batch):
    path = batch / "manifest.json"
    manifest = json.loads(path.read_text())
    old = batch / manifest["trials"][0]["bundle_directory"]
    relative = "trial-002/" + "2" * 32
    shutil.copytree(old, batch / relative)
    row = {
        **manifest["trials"][0],
        "repeat": 1,
        "bundle_directory": relative,
        "artifacts": str(batch / relative),
    }
    manifest["trials"].append(row)
    manifest["configuration"]["repeats"] = 2
    manifest["summaries"] = summarize(manifest["trials"])
    write_json(path, manifest)
    result = audit_browser_batch(batch)
    assert not result["evidence_passed"]
    assert {"check": "unique_run:2", "passed": False} in result["checks"]


def test_changed_inventory_is_not_silently_accepted(batch):
    manifest = json.loads((batch / "manifest.json").read_text())
    target = batch / manifest["trials"][0]["bundle_directory"]
    (target / "after-001.png").write_bytes(b"changed capture")
    seal_browser_evidence(target)
    result = audit_browser_batch(batch)
    assert not result["evidence_passed"]
    assert {"check": "inventory_binding:1", "passed": False} in result["checks"]


@pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)
def test_real_batch_reconciles_drop_exposure_and_baseline_false_claim(tmp_path):
    saved = browser_batch(
        tmp_path,
        task_ids=("single_done",),
        scenarios=("silent_drop",),
        modes=("baseline", "recover"),
    )
    result = audit_browser_batch(Path(saved["artifacts"]))
    assert result["evidence_passed"], result
    assert result["summaries"][0]["false_successes"] == 1
    assert result["summaries"][1]["execution_passes"] == 1
