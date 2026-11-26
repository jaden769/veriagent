import json

import pytest

from research import run_decision_budget as runner


@pytest.fixture
def plan():
    return json.loads(runner.PLAN.read_text(encoding="utf-8"))


def pick(plan, arm, cap, task="single_done", scenario="clean"):
    return next(
        c
        for c in plan["conditions"]
        if c["arm"] == arm
        and c["max_decisions"] == cap
        and c["task_id"] == task
        and c["scenario"] == scenario
    )


@pytest.mark.parametrize("arm", runner.ARMS)
@pytest.mark.parametrize("cap", [4, 8, 12])
def test_native_arms_and_cap_accounting(tmp_path, plan, arm, cap):
    cases = runner.validate_plan(plan)
    row = runner.run_condition(tmp_path / "trial", pick(plan, arm, cap), plan, cases)
    assert row["trace_consistency_passed"]
    assert row["budget"]["max_decisions"] == cap
    assert row["resources"]["decisions"] <= cap
    assert row["resources"]["actions"] <= 8
    assert row["resources"]["model_calls"] == 0


@pytest.mark.parametrize("cap", [4, 8, 12])
@pytest.mark.parametrize("scenario", ["silent_drop", "transient"])
def test_reflection_single_and_joint_cap_flags(tmp_path, plan, cap, scenario):
    row = runner.run_condition(
        tmp_path / "trial",
        pick(plan, "mock_self_reflection", cap, "pair_done", scenario),
        plan,
        runner.validate_plan(plan),
    )
    d = row["stopping_diagnostics"]
    assert d["action_cap_reached"] == (row["report"]["actions"] == 8)
    assert d["decision_cap_reached"] == (row["report"]["decisions"] == cap)
    if cap == 8:
        assert d["achieved_goal_with_budget_failure"]
        assert d["decision_cap_reached"]
        assert d["action_cap_reached"] == (scenario == "transient")


@pytest.mark.parametrize("mutation", ["provider", "order", "budget", "source"])
def test_plan_drift_before_output(tmp_path, plan, mutation):
    if mutation == "provider":
        plan["arms"][0]["provider"] = "openai"
    elif mutation == "order":
        plan["conditions"].reverse()
    elif mutation == "budget":
        plan["fixed_budget"]["max_actions"] = 9
    else:
        plan["source_sha256"][next(iter(plan["source_sha256"]))] = "0" * 64
    path = tmp_path / "plan.json"
    runner.save(path, plan)
    with pytest.raises(ValueError):
        runner.execute(path, runner.LOCK, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mutation", ["plan", "runner", "auditor", "boolean"])
def test_lock_drift_before_output(tmp_path, mutation):
    lock = runner.bindings(runner.PLAN)
    if mutation == "plan":
        lock["plan_sha256"] = "0" * 64
    elif mutation == "boolean":
        lock["schema_version"] = True
    else:
        key = (
            "research/run_decision_budget.py"
            if mutation == "runner"
            else "research/reflection_trace.py"
        )
        lock["research_sha256"][key] = "0" * 64
    path = tmp_path / "lock.json"
    runner.save(path, lock)
    with pytest.raises(ValueError, match="lock"):
        runner.execute(runner.PLAN, path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mutation", ["diagnostics", "resources", "budget", "condition"])
def test_saved_condition_drift_rejected(tmp_path, plan, mutation):
    cases = runner.validate_plan(plan)
    condition = pick(plan, "mock_self_reflection", 8)
    row = runner.run_condition(tmp_path / "trial", condition, plan, cases)
    if mutation == "diagnostics":
        row["stopping_diagnostics"]["decision_cap_reached"] = True
    elif mutation == "resources":
        row["additional_resources"]["repeat_write_attempts"] = 99
    elif mutation == "budget":
        row["budget"]["max_decisions"] = 12
    else:
        row["condition"]["max_decisions"] = 12
    runner.save(tmp_path / "trial/result.json", row)
    with pytest.raises(ValueError):
        runner.reconcile_condition(
            tmp_path / "trial", row, cases["single_done"], runner.budget_for(plan, 8)
        )


@pytest.mark.parametrize("duplicate", [False, True])
def test_orchestration_all_cells_without_study(tmp_path, monkeypatch, plan, duplicate):
    lock = tmp_path / "lock.json"
    runner.save(lock, runner.bindings(runner.PLAN))
    seen = []

    def fake(directory, condition, *args):
        seen.append(condition)
        return dict(run_id="same" if duplicate else str(len(seen)), trace_consistency_passed=True)

    monkeypatch.setattr(runner, "run_condition", fake)
    result = runner.execute(runner.PLAN, lock, tmp_path / "output")
    assert seen == plan["conditions"] and result["completed_runs"] == 288
    assert result["complete"] is (not duplicate)
    assert result["evidence_passed"] is (not duplicate)


def test_interruption_keeps_partial_unknown(tmp_path, monkeypatch):
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
