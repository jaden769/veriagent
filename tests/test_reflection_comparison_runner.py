import copy
import json

import pytest

from research import run_reflection_comparison as runner


@pytest.fixture
def plan():
    return json.loads(runner.PLAN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mutation", ["provider", "order", "budget", "counter", "source"])
def test_reject_plan_changes_before_output(tmp_path, plan, mutation):
    if mutation == "provider":
        plan["arms"][0]["provider"] = "openai"
    elif mutation == "order":
        plan["conditions"].reverse()
    elif mutation == "budget":
        plan["budget_per_run"]["max_actions"] = 9
    elif mutation == "counter":
        plan["repeats"] = True
    else:
        plan["source_sha256"][next(iter(plan["source_sha256"]))] = "0" * 64
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        runner.execute(path, runner.LOCK, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("arm", runner.ARMS)
@pytest.mark.parametrize("scenario", ["clean", "silent_drop", "persistent_drop", "transient"])
def test_native_reports_and_independent_evidence(tmp_path, plan, arm, scenario):
    cases, budget = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == "single_done" and c["scenario"] == scenario and c["arm"] == arm
    )
    row = runner.run_condition(tmp_path / "trial", condition, plan, cases, budget)
    assert row["trace_consistency_passed"]
    resources = row["resources"]
    assert resources["actions"] == resources["tool_reads"] + resources["tool_writes"]
    assert resources["model_calls"] == resources["model_tokens"] == 0
    assert row["condition"] == condition
    for name, sha in row["files_sha256"].items():
        assert runner.digest(tmp_path / "trial" / name) == sha
    if arm == "mock_self_reflection":
        assert row["live_ledger"] is None
        assert resources["trusted_verification_calls"] == 0
        assert row["report"]["comparator"] == "mock_self_reflection"
    else:
        assert row["live_ledger"] is not None
        assert row["report"]["mode"] == arm.removeprefix("dynamic_")


@pytest.mark.parametrize(
    "key", ["plan_sha256", "runner_sha256", "reflection_auditor_sha256", "support_sha256"]
)
def test_lock_drift_rejected_before_output(tmp_path, key):
    lock = runner.bindings(runner.PLAN)
    lock[key] = "0" * 64
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock))
    with pytest.raises(ValueError, match="lock"):
        runner.execute(runner.PLAN, path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_interruption_retains_completed_and_partial_unknown(tmp_path, monkeypatch):
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps(runner.bindings(runner.PLAN)))
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
    assert manifest["active_condition"]["position"] == 2
    assert manifest["active_outcome"] == "unknown"
    assert manifest["stop_reason"] == "RuntimeError"
    assert (directory / "trial-002/partial.txt").read_text() == "retained"


def test_complete_coverage_and_unique_ids_without_running_study(tmp_path, monkeypatch, plan):
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps(runner.bindings(runner.PLAN)))
    observed = []

    def fake(directory, condition, *args):
        observed.append(copy.deepcopy(condition))
        return dict(run_id=str(len(observed)), trace_consistency_passed=True)

    monkeypatch.setattr(runner, "run_condition", fake)
    manifest = runner.execute(runner.PLAN, lock, tmp_path / "output")
    assert observed == plan["conditions"]
    assert manifest["complete"] and manifest["evidence_passed"]
    assert manifest["completed_runs"] == 96


def test_source_inventory_drift_rejected(plan, monkeypatch):
    original = runner.digest

    def altered(path):
        return "0" * 64 if path.name == "reflection.py" else original(path)

    monkeypatch.setattr(runner, "digest", altered)
    with pytest.raises(ValueError, match="Source"):
        runner.validate_plan(plan)


def test_published_plan_drift_rejected(tmp_path, plan, monkeypatch):
    path = tmp_path / "published.json"
    path.write_text(json.dumps(plan))
    monkeypatch.setattr(runner, "PLAN", path)
    with pytest.raises(ValueError, match="Published"):
        runner.validate_plan(plan)


def test_duplicate_ids_do_not_pass_completion(tmp_path, monkeypatch):
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps(runner.bindings(runner.PLAN)))
    monkeypatch.setattr(
        runner, "run_condition", lambda *a: dict(run_id="duplicate", trace_consistency_passed=True)
    )
    result = runner.execute(runner.PLAN, lock, tmp_path / "output")
    assert result["completed_runs"] == 96
    assert not result["complete"] and not result["evidence_passed"]


@pytest.mark.parametrize(
    "task", ["pair_done", "mixed_status", "reopen", "already_satisfied", "partial_satisfied"]
)
@pytest.mark.parametrize("scenario", ["clean", "silent_drop"])
def test_reflection_multitarget_and_satisfied_cases(tmp_path, plan, task, scenario):
    cases, budget = runner.validate_plan(plan)
    condition = next(
        c
        for c in plan["conditions"]
        if c["task_id"] == task and c["scenario"] == scenario and c["arm"] == "mock_self_reflection"
    )
    row = runner.run_condition(tmp_path / "trial", condition, plan, cases, budget)
    assert row["trace_consistency_passed"]
    assert row["resources"]["actions"] <= 8 and row["resources"]["decisions"] <= 8
    assert row["untargeted_changed"] is False
