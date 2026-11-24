import copy
import json
from pathlib import Path

import pytest

from research import run_bounded_oracle as runner


@pytest.fixture
def plan():
    plan = json.loads((runner.ROOT / "docs/review/bounded-oracle-plan.json").read_text())
    # Fixture snapshots follow test code; published historical plans remain immutable.
    plan["source_sha256"] = {
        p.relative_to(runner.ROOT).as_posix(): runner.digest(p)
        for p in (runner.ROOT / "src/veriagent").rglob("*.py")
    }
    return plan


@pytest.mark.parametrize("mutation", ["provider", "source", "duplicate", "quota", "budget"])
def test_invalid_plan_rejected_before_output(tmp_path, plan, mutation):
    if mutation == "provider":
        plan["provider"] = "openai"
    elif mutation == "source":
        key = next(iter(plan["source_sha256"]))
        plan["source_sha256"][key] = "0" * 64
    elif mutation == "duplicate":
        plan["cases"][-1] = plan["cases"][0]
    elif mutation == "quota":
        plan["quota_profiles"]["one_call"]["max_calls"] = True
    else:
        plan["budget_per_run"]["max_actions"] = 9
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        runner.execute(path, output)
    assert not output.exists()


def test_real_condition_retains_unexpected_outcome_and_raw_evidence(tmp_path, plan):
    cases, budget = runner.validate_plan(plan)
    condition = copy.deepcopy(
        next(
            r
            for r in plan["cases"]
            if r["task_id"] == "single_done"
            and r["scenario"] == "clean"
            and r["mode"] == "recover"
            and r["quota_profile"] == "one_call"
        )
    )
    condition["expected_claimed_success"] = True  # Deliberately false prediction.
    row = runner.run_condition(tmp_path / "trial", condition, plan, cases, budget)
    assert row["evidence_passed"] and row["admission_passed"]
    assert row["actual"]["failure"] == "budget" and row["actual"]["ground_truth_success"]
    assert row["expectation_mismatches"]["claimed_success"]["actual"] is False
    assert (tmp_path / "trial/result.json").is_file()
    for name, digest in row["files_sha256"].items():
        assert runner.digest(tmp_path / "trial" / name) == digest


def test_interruption_keeps_completed_and_active_conditions(tmp_path, plan, monkeypatch):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    original = runner.run_condition
    calls = 0

    def stop(directory, condition, *args):
        nonlocal calls
        calls += 1
        if calls == 2:
            directory.mkdir()
            (directory / "partial.txt").write_bytes(b"retained")
            raise RuntimeError("injected")
        return original(directory, condition, *args)

    monkeypatch.setattr(runner, "run_condition", stop)
    output = tmp_path / "output"
    with pytest.raises(RuntimeError):
        runner.execute(path, output)
    directory = next(output.iterdir())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert not manifest["complete"] and manifest["completed_runs"] == 1
    assert manifest["active_condition"] == plan["cases"][1]
    assert manifest["stop_reason"] == "RuntimeError"
    assert (directory / "trial-001/result.json").is_file()
    assert (directory / "trial-002/partial.txt").read_bytes() == b"retained"


def test_plan_and_runner_are_separate_from_pinned_product_sources(plan):
    cases, _ = runner.validate_plan(plan)
    assert len(plan["cases"]) == 72 and len(cases) == 6
    assert not any(Path(name).parts[0] == "research" for name in plan["source_sha256"])
