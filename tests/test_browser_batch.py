import json
import os

import pytest

from veriagent.browser_batch import browser_batch, summarize


def test_summary_keeps_claim_and_exposure_denominators_separate():
    row = dict(
        task_id="single_done",
        scenario="silent_drop",
        mode="baseline",
        claimed_success=True,
        audit_passed=False,
        execution_passed=False,
        fault_exposed=True,
    )
    summary = summarize([row, {**row, "fault_exposed": False, "audit_passed": True}])[0]
    assert summary["false_success_given_claim"] == 0.5
    assert summary["audited_success_given_exposure"] == 0
    assert summary["fault_exposed_runs"] == summary["unexposed_runs"] == 1
    summary = summarize([{**row, "claimed_success": False, "fault_exposed": False}])[0]
    assert summary["false_success_given_claim"] is None
    assert summary["audited_success_given_exposure"] is None


@pytest.mark.parametrize(
    "options",
    [
        dict(repeats=21),
        dict(scenarios=("clean", "clean")),
        dict(modes=()),
        dict(task_ids=("unknown",)),
        dict(
            task_ids=("single_done",),
            repeats=20,
            scenarios=("clean", "silent_drop", "lost_ack"),
            modes=("baseline", "verify", "recover"),
        ),
    ],
)
def test_invalid_batch_does_not_create_artifacts(tmp_path, options):
    with pytest.raises(ValueError):
        browser_batch(tmp_path / "output", **options)
    assert not (tmp_path / "output").exists()


def test_interruption_preserves_manifest_and_active_trial(tmp_path, monkeypatch):
    def stop(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr("veriagent.browser_batch.execute_browser", stop)
    with pytest.raises(KeyboardInterrupt):
        browser_batch(tmp_path)
    manifest = json.loads(next(tmp_path.glob("*/manifest.json")).read_text())
    assert manifest["status"] == "interrupted"
    assert manifest["active_trial"].endswith("trial-001")
    assert manifest["trials"] == []
    assert "web/app.js" in manifest["source_sha256"]


@pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing Chromium",
)
def test_real_batch_distinguishes_unreached_fault_and_baseline_false_claim(tmp_path):
    result = browser_batch(
        tmp_path,
        task_ids=("single_done", "already_satisfied"),
        scenarios=("silent_drop",),
        modes=("baseline", "recover"),
    )
    assert result["status"] == "complete" and len(result["trials"]) == 4
    rows = {(r["task_id"], r["mode"]): r for r in result["trials"]}
    baseline = rows["single_done", "baseline"]
    assert baseline["claimed_success"] and not baseline["audit_passed"]
    assert baseline["fault_exposed"] and not baseline["execution_passed"]
    recovery = rows["single_done", "recover"]
    assert recovery["execution_passed"] and recovery["recovery_attempts"] == 1
    satisfied = rows["already_satisfied", "recover"]
    assert satisfied["execution_passed"] and not satisfied["fault_exposed"]
    assert satisfied["application_write_attempts"] == 0
    assert json.loads(next(tmp_path.glob("*/manifest.json")).read_text()) == result
