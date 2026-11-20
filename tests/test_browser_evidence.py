import json
import os
from pathlib import Path

import pytest

from veriagent.browser_evidence import audit_browser_evidence, seal_browser_evidence
from veriagent.browser_execution import audit_browser_state, execute_browser
from veriagent.interpretation import proposal_digest
from veriagent.models import Budget, Interpretation, Mode, Requirement, RunReport, TaskProposal
from veriagent.planner import MockProvider
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def bundle(tmp_path):
    directory = tmp_path / "evidence"
    directory.mkdir()
    proposal = TaskProposal(
        objective="Set ISSUE-1 to done",
        interpretation=Interpretation(
            requirements=(Requirement(issue_id="ISSUE-1", status="done"),)
        ),
    )
    task = proposal.task()
    initial = [dict(id="ISSUE-1", title="Example", status="open", version=0)]
    final = [{**initial[0], "status": "done", "version": 1}]
    audit = audit_browser_state(task, initial, final)
    report = RunReport(
        run_id="example",
        mode=Mode.RECOVER,
        claimed_success=True,
        verified_success=True,
        actions=1,
        recovery_attempts=0,
        elapsed_ms=1,
        tool_execution="browser",
    )
    result = {
        **report.model_dump(mode="json"),
        "browser_audit": audit,
        "browser_execution_passed": True,
        "browser": {
            "cleanup_completed": True,
            "events_dropped": 0,
            "captures": [
                dict(issue_id="ISSUE-1", phase=p, captured=True) for p in ("before", "after")
            ],
        },
    }
    saved = dict(
        schema_version=1,
        task=task.model_dump(mode="json"),
        proposal=proposal.model_dump(mode="json"),
        approval_digest=proposal_digest(proposal),
        budget=Budget().model_dump(mode="json"),
        initial_state=initial,
        final_state=final,
        result=result,
    )
    write_json(directory / "result.json", saved)
    write_json(
        directory / "application-events.json",
        [
            dict(
                issue_id="ISSUE-1",
                before_status="open",
                before_version=0,
                after_status="done",
                after_version=1,
                requested_status="done",
                committed=True,
            )
        ],
    )
    write_json(directory / "browser-events.json", [])
    traces = TraceStore(tmp_path / "trace.sqlite")
    traces.append(report.run_id, "task", task)
    traces.append(
        report.run_id, "requirements_review", {"proposal_digest": proposal_digest(proposal)}
    )
    traces.append(report.run_id, "report", report)
    traces.append(
        report.run_id,
        "browser_execution_audit",
        {**audit, "browser_execution_passed": True, "cleanup_completed": True},
    )
    traces.export(report.run_id, directory / "trace.json")
    (directory / "trace.txt").write_text(traces.render(report.run_id) + "\n", encoding="utf-8")
    for phase in ("before", "after"):
        (directory / f"{phase}-001.png").write_bytes(b"synthetic image fixture")
        (directory / f"{phase}-001.html").write_text("<p>fixture</p>", encoding="utf-8")
    seal_browser_evidence(directory)
    return directory


def test_complete_evidence_passes_without_writing_files(bundle):
    before = {p.name: p.read_bytes() for p in bundle.iterdir()}
    result = audit_browser_evidence(bundle)
    assert result["evidence_passed"] and result["task_passed"]
    assert before == {p.name: p.read_bytes() for p in bundle.iterdir()}


@pytest.mark.parametrize(
    "name", ["result.json", "trace.json", "application-events.json", "before-001.png"]
)
def test_missing_evidence_fails_closed(bundle, name):
    (bundle / name).unlink()
    assert not audit_browser_evidence(bundle)["evidence_passed"]


def test_changed_capture_hash_is_rejected(bundle):
    (bundle / "after-001.png").write_bytes(b"altered")
    result = audit_browser_evidence(bundle)
    assert not result["evidence_passed"]
    assert {"check": "hash:after-001.png", "passed": False} in result["checks"]


@pytest.mark.parametrize("mutation", ["digest", "state", "duplicate", "report", "event"])
def test_semantic_changes_are_rejected_even_with_updated_inventory(bundle, mutation):
    path = bundle / "result.json"
    saved = json.loads(path.read_text())
    if mutation == "digest":
        saved["approval_digest"] = "invalid"
    elif mutation == "state":
        saved["final_state"][0]["status"] = "open"
    elif mutation == "duplicate":
        saved["final_state"].append(saved["final_state"][0])
    elif mutation == "report":
        saved["result"]["actions"] = 2
    else:
        write_json(bundle / "application-events.json", [])
    write_json(path, saved)
    seal_browser_evidence(bundle)
    assert not audit_browser_evidence(bundle)["evidence_passed"]


def test_inventory_cannot_reference_external_file(bundle):
    path = bundle / "evidence.json"
    inventory = json.loads(path.read_text())
    inventory["files"]["../outside"] = {"bytes": 0, "sha256": "unused"}
    write_json(path, inventory)
    assert not audit_browser_evidence(bundle)["evidence_passed"]


def test_oversized_file_is_rejected(bundle, monkeypatch):
    monkeypatch.setattr("veriagent.browser_evidence.MAX_FILE_BYTES", 5)
    assert not audit_browser_evidence(bundle)["evidence_passed"]


@pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)
@pytest.mark.parametrize("retries", [0, 2])
def test_real_success_and_honest_partial_failure_have_valid_evidence(tmp_path, retries):
    proposal = TaskProposal(
        objective="Set ISSUE-1 and ISSUE-2 to done",
        interpretation=Interpretation(
            requirements=tuple(Requirement(issue_id=f"ISSUE-{i}", status="done") for i in (1, 2))
        ),
    )
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    result = execute_browser(
        proposal,
        MockProvider(),
        sandbox,
        TraceStore(tmp_path / "traces.sqlite"),
        Budget(
            max_actions=8,
            max_decisions=8,
            timeout_seconds=30,
            action_timeout_seconds=1,
            max_retries=retries,
        ),
        output=tmp_path / "bundles",
        engine="dynamic",
        browser_scenario="second_two_drops",
    )
    audit = audit_browser_evidence(Path(result["browser_artifacts"]))
    assert audit["evidence_passed"], audit
    assert audit["task_passed"] is bool(retries)
