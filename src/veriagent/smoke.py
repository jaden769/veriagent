"""One isolated verification/recovery check, ready for either mock or live planning."""

import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal
from uuid import uuid4

from veriagent.agent import Agent
from veriagent.dynamic import DynamicAgent
from veriagent.isolated import sandbox_executor
from veriagent.models import Budget, Mode, ToolExecutionConfig
from veriagent.planner import MockProvider, PlanningProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def smoke_test(
    output: Path,
    provider: PlanningProvider,
    budget: Budget | None = None,
    *,
    engine: Literal["static", "dynamic"] = "static",
    tool_config: ToolExecutionConfig | None = None,
) -> dict:
    """Save an honest result even when the model refuses or returns an invalid plan.

    A completed task alone is insufficient: the trace must show the injected mismatch
    being detected, a recovery attempt, and a successful final audit. The caller owns
    the provider and closes its resources. Dynamic selection can make multiple model calls.
    """
    if engine not in {"static", "dynamic"}:
        raise ValueError("Unknown engine")
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    budget = budget or Budget(timeout_seconds=60)
    faults = Faults(silent_drops=1)
    sandbox = Sandbox(directory / "state.sqlite", faults)
    sandbox.seed()
    traces = TraceStore(directory / "traces.sqlite")
    verifier = StateVerifier(sandbox.path)
    task = MockProvider().parse("Set ISSUE-1 to done")
    initial = [sandbox.read_issue(f"ISSUE-{i}") for i in range(1, 4)]
    agent_class = DynamicAgent if engine == "dynamic" else Agent
    report = agent_class(
        provider, sandbox_executor(sandbox, tool_config), verifier, traces, budget
    ).run(task, Mode.RECOVER)
    audit = verifier.verify(task)
    traces.append(report.run_id, "evaluation_audit", audit)
    events = traces.events(report.run_id)
    detected = any(
        e["kind"] == "verification" and e["payload"]["failure"] == "state_mismatch" for e in events
    )
    final = [sandbox.read_issue(f"ISSUE-{i}") for i in range(1, 4)]
    untouched = initial[1:] == final[1:]
    passed = (
        report.claimed_success
        and report.verified_success is True
        and audit.passed
        and detected
        and report.recovery_attempts > 0
        and untouched
        and faults.silent_drops == 0
    )
    packages = {}
    for name in ("veriagent", "pydantic", "openai"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    result = {
        "schema_version": 1,
        "scenario": "silent_drop",
        "engine": engine,
        "directory": str(directory),
        "smoke_passed": passed,
        "fault_detected": detected,
        "untargeted_issues_unchanged": untouched,
        "task": task.model_dump(mode="json"),
        "budget": budget.model_dump(mode="json"),
        "initial_state": [issue.model_dump(mode="json") for issue in initial],
        "final_state": [issue.model_dump(mode="json") for issue in final],
        "report": report.model_dump(mode="json"),
        "audit": audit.model_dump(mode="json"),
        "environment": {"python": platform.python_version(), "packages": packages},
    }
    traces.append(
        report.run_id,
        "smoke_result",
        {
            "smoke_passed": passed,
            "fault_detected": detected,
            "untargeted_issues_unchanged": untouched,
        },
    )
    traces.export(report.run_id, directory / "trace.json")
    (directory / "trace.txt").write_text(traces.render(report.run_id) + "\n", encoding="utf-8")
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
