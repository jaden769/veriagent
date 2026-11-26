import copy
import json

import pytest

from research import reflection_results as checker
from research import run_reflection_comparison as runner
from research.run_bounded_oracle import save


@pytest.fixture
def plan():
    return json.loads(runner.PLAN.read_text())


@pytest.mark.parametrize("arm", runner.ARMS)
def test_independent_native_report_replay_and_sql(tmp_path, plan, arm):
    cases, budget = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == "single_done" and c["scenario"] == "silent_drop" and c["arm"] == arm
    )
    row = runner.run_condition(tmp_path / "trial", condition, plan, cases, budget)
    result = checker.audit_condition(tmp_path / "trial", row, cases["single_done"])
    assert result["ground_truth_success"] == row["ground_truth_success"]
    assert result["false_success"] == row["false_success"]
    if arm == "dynamic_baseline":
        assert result["false_success"] and not result["ground_truth_success"]


@pytest.mark.parametrize("mutation", ["hash", "resources", "outcome", "sql", "report", "task"])
def test_reject_corrupted_evidence(tmp_path, plan, mutation):
    cases, budget = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == "single_done"
        and c["scenario"] == "clean"
        and c["arm"] == "mock_self_reflection"
    )
    directory = tmp_path / "trial"
    row = runner.run_condition(directory, condition, plan, cases, budget)
    row = copy.deepcopy(row)
    if mutation == "hash":
        row["files_sha256"]["trace.json"] = "0" * 64
    elif mutation == "resources":
        row["resources"]["actions"] += 1
    elif mutation == "outcome":
        row["ground_truth_success"] = False
    elif mutation == "sql":
        row["final_state"][0][1] = "open"
    elif mutation == "report":
        row["report"]["claimed_success"] = False
    else:
        cases["single_done"] = cases["pair_done"]
    save(directory / "result.json", row)
    with pytest.raises(ValueError):
        checker.audit_condition(directory, row, cases["single_done"])


@pytest.mark.parametrize("mutation", ["incomplete", "duplicate", "coverage", "binding"])
def test_reject_manifest_before_trials(tmp_path, plan, mutation):
    manifest = dict(
        complete=True,
        completed_runs=96,
        planned_runs=96,
        active_condition=None,
        bindings=runner.bindings(runner.PLAN),
        runs=[dict(run_id=str(i), condition=c) for i, c in enumerate(plan["conditions"])],
    )
    if mutation == "incomplete":
        manifest["complete"] = False
    elif mutation == "duplicate":
        manifest["runs"][1]["run_id"] = "0"
    elif mutation == "coverage":
        manifest["runs"].reverse()
    else:
        manifest["bindings"]["runner_sha256"] = "0" * 64
    save(tmp_path / "manifest.json", manifest)
    save(tmp_path / "plan.json", plan)
    save(tmp_path / "execution-lock.json", runner.bindings(runner.PLAN))
    with pytest.raises(ValueError):
        checker.audit(tmp_path, runner.digest(tmp_path / "manifest.json"))
