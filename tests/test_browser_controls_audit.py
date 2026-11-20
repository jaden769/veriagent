import hashlib
import json

import pytest

from veriagent.browser_controls import compare_control, control_batch_specs, expected_control
from veriagent.browser_controls_audit import audit_browser_controls
from veriagent.models import Budget


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture_evaluation(directory, *, indexed=False, multi_event=True, budget_boundaries=False):
    directory.mkdir()
    saved = dict(
        schema_version=1,
        status="complete",
        provider="mock",
        engine="dynamic",
        indexed=indexed,
        multi_event=multi_event,
        budget_boundaries=budget_boundaries,
        passed=True,
        coverage_complete=True,
        batch_bindings=[],
        controls=[],
    )
    run = 0
    for index, spec in enumerate(
        control_batch_specs(
            indexed=indexed, multi_event=multi_event, budget_boundaries=budget_boundaries
        ),
        1,
    ):
        relative = f"{index:032x}"
        path = directory / relative
        path.mkdir()
        rows = []
        for task in spec["tasks"]:
            for scenario in spec["scenarios"]:
                for mode in spec["modes"]:
                    run += 1
                    bundle_relative = f"trial-{len(rows) + 1:03d}/{run:032x}"
                    bundle = path / bundle_relative
                    bundle.mkdir(parents=True)
                    write_json(bundle / "result.json", {"result": {"run_id": str(run)}})
                    rows.append(
                        dict(
                            task_id=task,
                            scenario=scenario,
                            mode=mode,
                            max_retries=spec["max_retries"],
                            artifacts=str(bundle),
                            bundle_directory=bundle_relative,
                            **expected_control(
                                task,
                                scenario,
                                mode,
                                spec["max_retries"],
                                spec.get("max_actions", 8),
                                spec.get("max_decisions", 8),
                            ),
                        )
                    )
        manifest = dict(
            configuration=dict(
                tasks=list(spec["tasks"]),
                scenarios=list(spec["scenarios"]),
                modes=list(spec["modes"]),
                repeats=1,
            ),
            engine="dynamic",
            trials=rows,
            budget=Budget(
                max_actions=spec.get("max_actions", 8),
                max_decisions=spec.get("max_decisions", 8),
                timeout_seconds=30,
                action_timeout_seconds=1,
                max_retries=spec["max_retries"],
            ).model_dump(mode="json"),
        )
        write_json(path / "manifest.json", manifest)
        saved["batch_bindings"].append(
            dict(
                directory=relative,
                manifest_sha256=hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
            )
        )
        saved["controls"].extend(
            {**compare_control(row), "batch_directory": relative} for row in rows
        )
    write_json(directory / "controls.json", saved)
    return directory


@pytest.fixture
def nested_audit(monkeypatch):
    # These tests isolate evaluation reconciliation; real nested evidence is tested by
    # the batch auditor regressions and the end-to-end CLI control matrix.
    monkeypatch.setattr(
        "veriagent.browser_controls_audit.audit_browser_batch",
        lambda path: {"evidence_passed": True},
    )


@pytest.mark.parametrize(
    "indexed,multi_event,budget_boundaries,count",
    [
        (False, False, False, 42),
        (True, False, False, 24),
        (False, True, False, 12),
        (False, False, True, 12),
    ],
)
def test_all_matrix_shapes_are_read_only_and_movable(
    tmp_path, nested_audit, indexed, multi_event, budget_boundaries, count
):
    directory = fixture_evaluation(
        tmp_path / "saved",
        indexed=indexed,
        multi_event=multi_event,
        budget_boundaries=budget_boundaries,
    )
    moved = tmp_path / "moved"
    directory.rename(moved)
    before = {p.relative_to(moved): p.read_bytes() for p in moved.rglob("*") if p.is_file()}
    result = audit_browser_controls(moved)
    assert result["evidence_passed"] and result["controls_passed"], result
    assert len(result["controls"]) == count
    assert before == {p.relative_to(moved): p.read_bytes() for p in moved.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "mutation",
    ["passed", "expected", "missing", "duplicate", "binding", "escape", "interrupted", "flags"],
)
def test_corrupted_evaluation_fails_closed(tmp_path, nested_audit, mutation):
    directory = fixture_evaluation(tmp_path / "saved")
    path = directory / "controls.json"
    saved = json.loads(path.read_text())
    if mutation == "passed":
        saved["passed"] = False
    elif mutation == "expected":
        saved["controls"][0]["expected"]["commits"] = 99
    elif mutation == "missing":
        saved["controls"].pop()
    elif mutation == "duplicate":
        saved["controls"].append(saved["controls"][0])
    elif mutation == "binding":
        saved["batch_bindings"][0]["manifest_sha256"] = "wrong"
    elif mutation == "escape":
        saved["batch_bindings"][0]["directory"] = "../outside"
    elif mutation == "interrupted":
        saved["status"] = "interrupted"
    else:
        saved["indexed"] = True
    write_json(path, saved)
    assert not audit_browser_controls(directory)["evidence_passed"]


def test_invalid_nested_evidence_cannot_be_overridden_by_passed_flag(
    tmp_path, nested_audit, monkeypatch
):
    directory = fixture_evaluation(tmp_path / "saved")
    monkeypatch.setattr(
        "veriagent.browser_controls_audit.audit_browser_batch",
        lambda path: {"evidence_passed": False},
    )
    assert not audit_browser_controls(directory)["evidence_passed"]


def test_honestly_reported_expectation_mismatch_is_distinct_from_evidence_failure(
    tmp_path, nested_audit
):
    directory = fixture_evaluation(tmp_path / "saved")
    path = directory / "controls.json"
    saved = json.loads(path.read_text())
    binding = saved["batch_bindings"][0]
    manifest_path = directory / binding["directory"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["trials"][0]["commits"] = 99
    write_json(manifest_path, manifest)
    binding["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    saved["controls"][0] = {
        **compare_control(manifest["trials"][0]),
        "batch_directory": binding["directory"],
    }
    saved["passed"] = False
    write_json(path, saved)
    result = audit_browser_controls(directory)
    assert result["evidence_passed"] and result["controls_passed"] is False, result


def test_changed_retry_budget_is_rejected_even_if_manifest_is_rebound(tmp_path, nested_audit):
    directory = fixture_evaluation(tmp_path / "saved")
    path = directory / "controls.json"
    saved = json.loads(path.read_text())
    binding = saved["batch_bindings"][0]
    manifest_path = directory / binding["directory"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["budget"]["max_retries"] = 2
    write_json(manifest_path, manifest)
    binding["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    write_json(path, saved)
    assert not audit_browser_controls(directory)["evidence_passed"]
