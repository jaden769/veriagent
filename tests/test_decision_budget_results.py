import copy
import json

import pytest

from analysis import decision_budget_results as results
from research import run_decision_budget as runner


@pytest.fixture
def plan():
    return json.loads(runner.PLAN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("cap", [4, 8, 12])
def test_audit_native_trial_and_diagnostics(tmp_path, plan, cap):
    cases = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == "pair_done"
        and c["scenario"] == "transient"
        and c["arm"] == "mock_self_reflection"
        and c["max_decisions"] == cap
    )
    row = runner.run_condition(tmp_path / "trial", condition, plan, cases)
    audited = results.audit_trial(tmp_path / "trial", row, cases["pair_done"], plan)
    assert audited["budget"]["max_decisions"] == cap
    assert audited["stopping_diagnostics"] == row["stopping_diagnostics"]
    if cap == 8:
        assert audited["stopping_diagnostics"]["achieved_goal_with_budget_failure"]
        assert audited["stopping_diagnostics"]["action_cap_reached"]


def test_contrasts_are_matched_and_directional():
    rows = []
    for task in ["one", "two"]:
        for cap in [4, 8, 12]:
            rows.append(
                dict(
                    condition=dict(arm="mock", task_id=task, scenario="clean", max_decisions=cap),
                    ground_truth_success=cap >= 8,
                    claimed_success=cap == 12,
                    stopping_diagnostics=dict(achieved_goal_with_budget_failure=cap == 8),
                )
            )
    c = results.contrasts(rows)
    assert len(c) == 4
    for row in c:
        if row["contrast"] == "12_minus_8":
            assert (
                row["goal_delta"] == 0
                and row["achieved_goal_budget_delta"] == -1
                and row["claim_delta"] == 1
            )
        else:
            assert row["goal_delta"] == 1 and row["achieved_goal_budget_delta"] == 1


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
