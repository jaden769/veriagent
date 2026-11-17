"""Paired deterministic scenarios; evaluation audit never feeds baseline execution."""

import json
from pathlib import Path
from uuid import uuid4

from veriagent.agent import Agent
from veriagent.executor import Executor
from veriagent.models import Mode
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def compare(output: Path, scenario: str = "silent_drop") -> dict:
    if scenario not in {"clean", "silent_drop", "persistent_drop", "transient"}:
        raise ValueError("Unknown scenario")
    directory = output / uuid4().hex
    directory.mkdir(parents=True)
    traces = TraceStore(directory / "traces.sqlite")
    provider = MockProvider()
    task = provider.parse("Set ISSUE-1 to done")
    rows = []
    for mode in Mode:
        faults = Faults(
            silent_drops={"silent_drop": 1, "persistent_drop": 100}.get(scenario, 0),
            transient_errors=int(scenario == "transient"),
        )
        sandbox = Sandbox(directory / f"{mode.value}.sqlite", faults)
        sandbox.seed()
        verifier = StateVerifier(sandbox.path)
        report = Agent(provider, Executor(sandbox), verifier, traces).run(task, mode)
        audit = verifier.verify(task)
        traces.append(report.run_id, "evaluation_audit", audit)
        traces.export(report.run_id, directory / f"{mode.value}.json")
        (directory / f"{mode.value}.txt").write_text(
            traces.render(report.run_id) + "\n", encoding="utf-8"
        )
        rows.append(
            {
                **report.model_dump(mode="json"),
                "ground_truth_success": audit.passed,
                "false_success": report.claimed_success and not audit.passed,
                "recovered": report.recovery_attempts > 0 and audit.passed,
                "unsafe_actions": 0,
            }
        )
    result = {
        "scenario": scenario,
        "task": task.model_dump(mode="json"),
        "directory": str(directory.resolve()),
        "runs": rows,
    }
    (directory / "comparison.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
