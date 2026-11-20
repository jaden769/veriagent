"""Explicit expectations for the fixed dynamic mock browser controls."""

import json
from pathlib import Path
from uuid import uuid4

from veriagent.browser_batch import browser_batch
from veriagent.browser_faults import BROWSER_SCENARIOS

# Independently specified changed-target counts for the packaged initial states.
CHANGED_TARGETS = {
    "single_done": 1,
    "pair_done": 2,
    "mixed_status": 2,
    "reopen": 1,
    "already_satisfied": 0,
    "partial_satisfied": 1,
}


def expected_control(task_id: str, scenario: str, mode: str) -> dict:
    if scenario not in BROWSER_SCENARIOS or mode not in {"baseline", "recover"}:
        raise ValueError("Unknown browser control")
    if mode == "baseline" and task_id != "single_done":
        raise ValueError("Baseline controls cover only single_done")
    changes = CHANGED_TARGETS[task_id]
    exposed = bool(changes and scenario != "clean")
    retry = int(
        exposed and scenario in {"silent_drop", "timeout_before_commit"} and mode == "recover"
    )
    claim = mode == "recover" or scenario in {"clean", "silent_drop", "stale_dom"}
    audit = not (mode == "baseline" and scenario in {"silent_drop", "timeout_before_commit"})
    return {
        "fault_exposed": exposed,
        "claimed_success": claim,
        "audit_passed": audit,
        "execution_passed": claim and audit,
        "recovery_attempts": retry,
        "commits": changes if audit else 0,
        "application_write_attempts": changes + retry,
        "events_dropped": 0,
    }


def compare_control(row: dict) -> dict:
    expected = expected_control(row["task_id"], row["scenario"], row["mode"])
    mismatches = {
        key: {"expected": value, "actual": row.get(key)}
        for key, value in expected.items()
        if row.get(key) != value
    }
    return {
        "task_id": row["task_id"],
        "scenario": row["scenario"],
        "mode": row["mode"],
        "artifacts": row["artifacts"],
        "expected": expected,
        "passed": not mismatches,
        "mismatches": mismatches,
    }


def evaluate_browser_controls(output: Path) -> dict:
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    result = {
        "schema_version": 1,
        "status": "running",
        "passed": False,
        "provider": "mock",
        "engine": "dynamic",
        "artifacts": str(directory),
        "batches": [],
        "controls": [],
        "limitations": "Fixed local mechanism controls; not stochastic reliability.",
    }

    def save():
        temporary = directory / "controls.tmp"
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        temporary.replace(directory / "controls.json")

    save()
    try:
        for tasks, modes in (
            (tuple(CHANGED_TARGETS), ("recover",)),
            (("single_done",), ("baseline",)),
        ):
            batch = browser_batch(
                directory, task_ids=tasks, scenarios=BROWSER_SCENARIOS, modes=modes
            )
            result["batches"].append(batch["artifacts"])
            result["controls"].extend(compare_control(row) for row in batch["trials"])
            save()
    except BaseException:
        result["status"] = "interrupted"
        save()
        raise
    result["status"] = "complete"
    required = {
        (task, scenario, "recover") for task in CHANGED_TARGETS for scenario in BROWSER_SCENARIOS
    } | {("single_done", scenario, "baseline") for scenario in BROWSER_SCENARIOS}
    observed = {(r["task_id"], r["scenario"], r["mode"]) for r in result["controls"]}
    result["coverage_complete"] = observed == required and len(result["controls"]) == len(required)
    result["passed"] = result["coverage_complete"] and all(
        row["passed"] for row in result["controls"]
    )
    save()
    return result
