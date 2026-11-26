import copy
import json

import pytest

from analysis import action_budget_results as results
from analysis import run_action_budget as runner


@pytest.fixture
def plan():
    return json.loads(runner.PLAN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("cap", [8, 10, 12])
def test_audit_native_trial_and_diagnostics(tmp_path, plan, cap):
    cases = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == "pair_done"
        and c["scenario"] == "transient"
        and c["arm"] == "mock_self_reflection"
        and c["max_actions"] == cap
    )
    row = runner.run_condition(
        tmp_path / "trial", condition, plan, cases, runner.budget_for(plan, cap)
    )
    audited = results.audit_trial(tmp_path / "trial", row, cases["pair_done"], plan)
    assert audited["budget"]["max_actions"] == cap
    assert audited["stopping_diagnostics"] == row["stopping_diagnostics"]
    if cap == 8:
        assert audited["stopping_diagnostics"]["achieved_goal_with_budget_failure"]
        assert audited["stopping_diagnostics"]["action_cap_reached"]


def test_contrasts_are_matched_and_directional():
    rows = []
    for task in ["one", "two"]:
        for cap in [8, 10, 12]:
            rows.append(
                dict(
                    condition=dict(arm="mock", task_id=task, scenario="clean", max_actions=cap),
                    ground_truth_success=cap >= 10,
                    claimed_success=cap == 12,
                    stopping_diagnostics=dict(achieved_goal_with_budget_failure=cap == 10),
                )
            )
    contrasts = results.contrasts(rows)
    assert len(contrasts) == 6
    expected = {"12_minus_10": (0, -1, 1), "10_minus_8": (1, 1, 0), "12_minus_8": (1, 0, 1)}
    for c in contrasts:
        assert (c["goal_delta"], c["achieved_goal_budget_delta"], c["claim_delta"]) == expected[
            c["contrast"]
        ]


def test_corrupted_fixed_fault_profile_rejected(tmp_path, plan):
    cases = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == "single_done"
        and c["scenario"] == "persistent_drop"
        and c["arm"] == "mock_self_reflection"
        and c["max_actions"] == 8
    )
    row = runner.run_condition(
        tmp_path / "trial", condition, plan, cases, runner.budget_for(plan, 8)
    )
    row["faults_configured"]["silent_drops"] = 9
    runner.save(tmp_path / "trial/result.json", row)
    with pytest.raises(ValueError, match="fault"):
        results.audit_trial(tmp_path / "trial", row, cases["single_done"], plan)


@pytest.mark.parametrize("mutation", ["partial", "coverage", "duplicate", "lock"])
def test_manifest_rejected_before_trial_reads(tmp_path, plan, mutation):
    m = dict(
        complete=True,
        completed_runs=288,
        planned_runs=288,
        active_condition=None,
        bindings=runner.bindings(runner.PLAN),
        runs=[
            dict(run_id=str(i), condition=copy.deepcopy(c))
            for i, c in enumerate(plan["conditions"])
        ],
    )
    if mutation == "partial":
        m["complete"] = False
    elif mutation == "coverage":
        m["runs"].reverse()
    elif mutation == "duplicate":
        m["runs"][1]["run_id"] = "0"
    else:
        m["bindings"]["plan_sha256"] = "0" * 64
    runner.save(tmp_path / "manifest.json", m)
    runner.save(tmp_path / "plan.json", plan)
    runner.save(tmp_path / "execution-lock.json", runner.bindings(runner.PLAN))
    with pytest.raises(ValueError):
        results.audit(tmp_path, runner.digest(tmp_path / "manifest.json"))


def test_bad_manifest_hash_rejected(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="Manifest"):
        results.audit(tmp_path, "0" * 64)
