import json

import pytest

from analysis import run_action_budget as runner


@pytest.fixture
def plan():
    return json.loads(runner.PLAN.read_text(encoding="utf-8"))


def pick(plan, arm, cap, task="single_done", scenario="clean"):
    return next(
        c
        for c in plan["conditions"]
        if c["arm"] == arm
        and c["max_actions"] == cap
        and c["task_id"] == task
        and c["scenario"] == scenario
    )


def run(tmp_path, plan, condition):
    return runner.run_condition(
        tmp_path / "trial",
        condition,
        plan,
        runner.validate_plan(plan),
        runner.budget_for(plan, condition["max_actions"]),
    )


@pytest.mark.parametrize("arm", runner.ARMS)
@pytest.mark.parametrize("cap", [8, 10, 12])
def test_native_arms_and_allocated_action_caps(tmp_path, plan, arm, cap):
    row = run(tmp_path, plan, pick(plan, arm, cap))
    assert row["trace_consistency_passed"]
    assert row["budget"]["max_actions"] == cap and row["budget"]["max_decisions"] == 12
    assert row["resources"]["actions"] <= cap and row["resources"]["decisions"] <= 12
    assert row["resources"]["model_calls"] == row["resources"]["model_tokens"] == 0


@pytest.mark.parametrize("cap", [8, 10, 12])
def test_persistent_fault_counter_is_thirteen_at_every_cap(tmp_path, plan, cap):
    row = run(tmp_path, plan, pick(plan, "mock_self_reflection", cap, scenario="persistent_drop"))
    assert row["faults_configured"]["silent_drops"] == 13
    assert not row["ground_truth_success"]
    drops = sum(r["injected_fault"] == "silent_drop" for r in row["realized_faults"])
    assert row["unused_faults"]["silent_drops"] == 13 - drops


@pytest.mark.parametrize("cap", [8, 10, 12])
@pytest.mark.parametrize("scenario", ["silent_drop", "transient"])
def test_multitarget_reflection_diagnostics(tmp_path, plan, cap, scenario):
    row = run(tmp_path, plan, pick(plan, "mock_self_reflection", cap, "pair_done", scenario))
    assert row["stopping_diagnostics"]["action_cap_reached"] == (row["report"]["actions"] == cap)
    assert row["stopping_diagnostics"]["decision_cap_reached"] == (row["report"]["decisions"] == 12)
    if cap == 8:
        assert row["stopping_diagnostics"]["achieved_goal_with_budget_failure"]


@pytest.mark.parametrize("mutation", ["provider", "order", "budget", "faults", "source"])
def test_plan_drift_precedes_outputs(tmp_path, plan, mutation):
    if mutation == "provider":
        plan["arms"][0]["provider"] = "openai"
    elif mutation == "order":
        plan["conditions"].reverse()
    elif mutation == "budget":
        plan["fixed_budget"]["max_decisions"] = 16
    elif mutation == "faults":
        plan["fault_configuration"]["max_actions_argument"] = 8
    else:
        plan["source_sha256"][next(iter(plan["source_sha256"]))] = "0" * 64
    path = tmp_path / "plan.json"
    runner.save(path, plan)
    with pytest.raises(ValueError):
        runner.execute(path, runner.LOCK, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mutation", ["plan", "runner", "auditor", "boolean"])
def test_lock_drift_precedes_outputs(tmp_path, mutation):
    lock = runner.bindings(runner.PLAN)
    if mutation == "plan":
        lock["plan_sha256"] = "0" * 64
    elif mutation == "boolean":
        lock["schema_version"] = True
    else:
        key = (
            "analysis/run_action_budget.py"
            if mutation == "runner"
            else "research/reflection_trace.py"
        )
        lock["execution_sha256"][key] = "0" * 64
    path = tmp_path / "lock.json"
    runner.save(path, lock)
    with pytest.raises(ValueError, match="lock"):
        runner.execute(runner.PLAN, path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mutation", ["faults", "diagnostics", "resources", "budget", "condition"])
def test_recorded_condition_corruption_rejected(tmp_path, plan, mutation):
    cases = runner.validate_plan(plan)
    row = run(tmp_path, plan, pick(plan, "mock_self_reflection", 8))
    if mutation == "faults":
        row["faults_configured"]["silent_drops"] = 9
    elif mutation == "diagnostics":
        row["stopping_diagnostics"]["action_cap_reached"] = True
    elif mutation == "resources":
        row["additional_resources"]["elapsed_ms"] += 1
    elif mutation == "budget":
        row["budget"]["max_actions"] = 10
    else:
        row["condition"]["max_actions"] = 10
    runner.save(tmp_path / "trial/result.json", row)
    with pytest.raises(ValueError):
        runner.reconcile_condition(
            tmp_path / "trial", row, cases["single_done"], plan, runner.budget_for(plan, 8)
        )


@pytest.mark.parametrize("duplicate", [False, True])
def test_all_assignments_simulated_without_study(tmp_path, monkeypatch, plan, duplicate):
    lock = tmp_path / "lock.json"
    runner.save(lock, runner.bindings(runner.PLAN))
    seen = []

    def fake(directory, condition, *args):
        seen.append(condition)
        return dict(run_id="same" if duplicate else str(len(seen)), trace_consistency_passed=True)

    monkeypatch.setattr(runner, "run_condition", fake)
    result = runner.execute(runner.PLAN, lock, tmp_path / "output")
    assert seen == plan["conditions"] and result["completed_runs"] == 288
    assert result["complete"] is (not duplicate) and result["evidence_passed"] is (not duplicate)


def test_partial_evidence_retained_on_interruption(tmp_path, monkeypatch):
    lock = tmp_path / "lock.json"
    runner.save(lock, runner.bindings(runner.PLAN))
    original = runner.run_condition
    calls = 0

    def stop(directory, condition, *args):
        nonlocal calls
        calls += 1
        if calls == 2:
            directory.mkdir()
            (directory / "partial.txt").write_text("retained")
            raise RuntimeError("injected")
        return original(directory, condition, *args)

    monkeypatch.setattr(runner, "run_condition", stop)
    with pytest.raises(RuntimeError):
        runner.execute(runner.PLAN, lock, tmp_path / "output")
    directory = next((tmp_path / "output").iterdir())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["completed_runs"] == 1 and not manifest["complete"]
    assert (
        manifest["active_outcome"] == "unknown"
        and manifest["active_condition"]["arm_position"] == 2
    )
    assert (directory / "trial-002/partial.txt").read_text() == "retained"
