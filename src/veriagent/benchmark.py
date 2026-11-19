"""Bounded repeated trials with independent SQLite outcomes and durable evidence."""

import hashlib
import json
import math
import platform
import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from itertools import product
from pathlib import Path
from uuid import uuid4

from veriagent.agent import Agent
from veriagent.benchmark_cases import select_cases
from veriagent.benchmark_faults import (
    ALL_SCENARIOS,
    DEFAULT_SCENARIOS,
    ScheduledSandbox,
    scenario_faults,
)
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget, Mode, Task
from veriagent.planner import MockProvider
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier

SCENARIOS = DEFAULT_SCENARIOS


def proportion(successes: int, count: int) -> dict:
    """Wilson score interval, z=1.95996 (nominal 95%, independent Bernoulli trials)."""
    if count < 1 or not 0 <= successes <= count:
        raise ValueError("Invalid outcome counts")
    rate = successes / count
    z = 1.959963984540054
    denominator = 1 + z * z / count
    center = (rate + z * z / (2 * count)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / count + z * z / (4 * count**2)) / denominator
    return {
        "count": successes,
        "trials": count,
        "rate": rate,
        "wilson_95": [max(0.0, center - half), min(1.0, center + half)],
    }


def summarize(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        groups.setdefault(
            (row.get("task_id", "single_done"), row["scenario"], row["mode"]), []
        ).append(row)
    result = []
    for (task_id, scenario, mode), group in sorted(groups.items()):
        usage_known = all(r["model_tokens"] is not None for r in group)
        claims = sum(r["claimed_success"] for r in group)
        eligible = [r for r in group if r.get("fault_recovery_eligible", False)]
        result.append(
            {
                "task_id": task_id,
                "scenario": scenario,
                "mode": mode,
                "ground_truth_success": proportion(
                    sum(r["ground_truth_success"] for r in group), len(group)
                ),
                "false_success": proportion(sum(r["false_success"] for r in group), len(group)),
                "false_success_given_claim": conditional_proportion(
                    sum(r["false_success"] for r in group), claims
                ),
                "recovered": proportion(sum(r["recovered"] for r in group), len(group)),
                "recovery_given_fault_mismatch": conditional_proportion(
                    sum(r["recovered"] for r in eligible), len(eligible)
                ),
                "untargeted_changes": sum(r["untargeted_changed"] for r in group),
                "runs_with_injected_fault": sum(
                    any(a["injected_fault"] for a in r.get("write_attempts", [])) for r in group
                ),
                "injected_faults": sum(
                    sum(a["injected_fault"] is not None for a in r.get("write_attempts", []))
                    for r in group
                ),
                "unused_indexed_events": sum(
                    len(r.get("unused_write_schedule", [])) for r in group
                ),
                "model_calls": sum(r["model_calls"] for r in group),
                "model_tokens": sum(r["model_tokens"] for r in group) if usage_known else None,
                "unknown_usage_runs": sum(r["model_tokens"] is None for r in group),
                "mean_actions": sum(r["actions"] for r in group) / len(group),
                "mean_elapsed_ms": sum(r["elapsed_ms"] for r in group) / len(group),
            }
        )
    return result


def conditional_proportion(successes: int, count: int) -> dict:
    if count == 0 and successes == 0:
        return {"count": 0, "trials": 0, "rate": None, "wilson_95": None}
    return proportion(successes, count)


def fault_recovery_eligible(task: Task, attempts: list[dict]) -> bool:
    """A delivered pre-commit fault on a write whose authorized target was unmet."""
    targets = {r.issue_id: r.status.value for r in task.requirements}
    return any(
        attempt.get("injected_fault") is not None
        and attempt.get("issue_id") in targets
        and attempt.get("status") == targets[attempt["issue_id"]]
        and attempt.get("status_before_fault") is not None
        and attempt["status_before_fault"] != targets[attempt["issue_id"]]
        for attempt in attempts
    )


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def audit_rows(task: Task, initial: list, final: list) -> tuple[bool, bool]:
    """Check every target and compare all untargeted rows against their starting values."""
    before = {row[0]: tuple(row[1:]) for row in initial}
    after = {row[0]: tuple(row[1:]) for row in final}
    targets = {r.issue_id: r.status.value for r in task.requirements}
    passed = all(after.get(issue, (None,))[0] == status for issue, status in targets.items())
    changed = any(
        before.get(issue) != after.get(issue)
        for issue in (before.keys() | after.keys()) - targets.keys()
    )
    return passed, changed


def repeated_trials(
    output: Path,
    *,
    repeats: int = 3,
    scenarios: tuple[str, ...] = SCENARIOS,
    task_ids: tuple[str, ...] = ("single_done",),
    engine: str = "static",
    budget: Budget | None = None,
    provider_factory: Callable = MockProvider,
    provider_name: str = "mock",
) -> dict:
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError("Repeats must be between 1 and 20")
    if (
        not scenarios
        or len(set(scenarios)) != len(scenarios)
        or any(s not in ALL_SCENARIOS for s in scenarios)
    ):
        raise ValueError("Select unique known scenarios")
    if engine not in {"static", "dynamic"}:
        raise ValueError("Unknown engine")
    cases, corpus_digest = select_cases(task_ids)
    count = repeats * len(scenarios) * len(cases) * len(Mode)
    if count > 120:
        raise ValueError("Benchmark is limited to 120 runs; reduce repeats or scenarios")
    budget = budget or Budget(max_actions=8, max_decisions=8, timeout_seconds=60)
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": 2,
        "directory": str(directory),
        "engine": engine,
        "provider": provider_name,
        "repeats": repeats,
        "scenarios": scenarios,
        "planned_runs": count,
        "completed_runs": 0,
        "complete": False,
        "tasks": [case.model_dump(mode="json") for case in cases],
        "corpus_sha256": corpus_digest,
        "budget_per_run": budget.model_dump(mode="json"),
        "interpretation_calls": 0,
        "order": "task, scenario, repetition, modes rotated by repetition",
        "python": platform.python_version(),
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob("*.py")
        },
        "interval_note": "Nominal Wilson 95% per group; assumes independent Bernoulli trials. "
        "Repeated deterministic mock outcomes do not measure stochastic reliability. "
        "No pooled or paired significance claim is made.",
        "runs": [],
        "summary": [],
    }
    _write(directory / "benchmark.json", manifest)
    modes = list(Mode)
    for case, scenario in product(cases, scenarios):
        task = case.task
        for repetition in range(repeats):
            order = modes[repetition % len(modes) :] + modes[: repetition % len(modes)]
            for mode in order:
                trial = directory / f"{case.id}-{scenario}-{repetition + 1:02d}-{mode.value}"
                trial.mkdir()
                faults, schedule = scenario_faults(scenario, budget.max_actions)
                sandbox = ScheduledSandbox(trial / "state.sqlite", faults, schedule)
                sandbox.seed()
                with sqlite3.connect(sandbox.path) as db:
                    db.executemany(
                        "UPDATE issues SET status=? WHERE id=?",
                        [(status.value, issue) for issue, status in case.initial_statuses.items()],
                    )
                    initial = db.execute(
                        "SELECT id,status,version FROM issues ORDER BY id"
                    ).fetchall()
                configured_faults = asdict(faults)
                traces = TraceStore(trial / "traces.sqlite")
                provider = provider_factory()
                config = getattr(provider, "config", None)
                try:
                    agent_class = DynamicAgent if engine == "dynamic" else Agent
                    report = agent_class(
                        provider, Executor(sandbox), StateVerifier(sandbox.path), traces, budget
                    ).run(task, mode)
                finally:
                    close = getattr(provider, "close", None)
                    if close is not None:
                        close()
                # Read final rows directly, independently of the execution verifier/tool.
                with sqlite3.connect(sandbox.path.as_uri() + "?mode=ro", uri=True) as db:
                    state = db.execute(
                        "SELECT id,status,version FROM issues ORDER BY id"
                    ).fetchall()
                passed, changed = audit_rows(task, initial, state)
                row = {
                    **report.model_dump(mode="json"),
                    "scenario": scenario,
                    "task_id": case.id,
                    "task": task.model_dump(mode="json"),
                    "initial_state": initial,
                    "faults_configured": configured_faults,
                    "faults_remaining": asdict(faults),
                    "write_schedule": [event.model_dump(mode="json") for event in schedule],
                    "write_attempts": sandbox.write_attempts,
                    "unused_write_schedule": sandbox.unused_schedule(),
                    "repetition": repetition + 1,
                    "ground_truth_success": passed,
                    "false_success": report.claimed_success and not passed,
                    "recovered": report.recovery_attempts > 0 and passed,
                    "fault_recovery_eligible": fault_recovery_eligible(
                        task, sandbox.write_attempts
                    ),
                    "untargeted_changed": changed,
                    "final_state": state,
                    "artifact": trial.name,
                    "provider_config": config.model_dump(mode="json")
                    if config is not None
                    else None,
                }
                traces.append(
                    report.run_id,
                    "benchmark_audit",
                    {
                        "ground_truth_success": passed,
                        "untargeted_changed": changed,
                        "final_state": state,
                    },
                )
                traces.export(report.run_id, trial / "trace.json")
                _write(trial / "result.json", row)
                manifest["runs"].append(row)
                manifest["completed_runs"] += 1
                manifest["summary"] = summarize(manifest["runs"])
                _write(directory / "benchmark.json", manifest)
                if report.provider_diagnostic is not None:
                    # A service/authentication error is not a reason to submit the rest
                    # of a paid batch. Preserve partial evidence and stop immediately.
                    manifest["stop_reason"] = "provider_diagnostic"
                    _write(directory / "benchmark.json", manifest)
                    return manifest
    manifest["complete"] = True
    _write(directory / "benchmark.json", manifest)
    return manifest
