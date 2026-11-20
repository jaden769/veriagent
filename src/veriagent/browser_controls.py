"""Explicit expectations for the fixed dynamic mock browser controls."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from veriagent.browser_batch import browser_batch
from veriagent.browser_faults import (
    BROWSER_SCENARIOS,
    INDEXED_BROWSER_SCENARIOS,
    MULTI_BROWSER_SCENARIOS,
)
from veriagent.models import Budget

# Independently specified changed-target counts for the packaged initial states.
CHANGED_TARGETS = {
    "single_done": 1,
    "pair_done": 2,
    "mixed_status": 2,
    "reopen": 1,
    "already_satisfied": 0,
    "partial_satisfied": 1,
}


def expected_control(
    task_id: str,
    scenario: str,
    mode: str,
    max_retries: int = 2,
    max_actions: int = 8,
    max_decisions: int = 8,
) -> dict:
    if (max_actions, max_decisions) != (8, 8):
        if (
            task_id not in {"pair_done", "mixed_status"}
            or scenario != "clean"
            or mode != "recover"
            or max_retries != 2
            or (max_actions, max_decisions) not in {(2, 8), (3, 8), (4, 8), (8, 2), (8, 3), (8, 4)}
        ):
            raise ValueError("Unknown budget-boundary control")
        steps = min(max_actions, max_decisions)
        passed = steps == 4
        return {
            "claimed_success": passed,
            "audit_passed": passed,
            "execution_passed": passed,
            "failure": None if passed else "budget",
            "actions": steps,
            "decisions": steps,
            "max_actions": max_actions,
            "max_decisions": max_decisions,
            "fault_exposed": False,
            "recovery_attempts": 0,
            "application_write_attempts": 2 if passed else 1,
            "commits": 2 if passed else 1,
            "pending_application_faults": 0,
            "injected_attempts": [],
            "events_dropped": 0,
            "untargeted_issues_unchanged": True,
            "target_titles_unchanged": True,
            "target_statuses": {
                "ISSUE-1": "done",
                "ISSUE-2": ("done" if task_id == "pair_done" else "in_progress")
                if passed
                else "open",
            },
            "target_versions": {"ISSUE-1": 1, "ISSUE-2": int(passed)},
        }
    if scenario in MULTI_BROWSER_SCENARIOS:
        if (
            task_id not in {"pair_done", "mixed_status"}
            or mode != "recover"
            or max_retries not in {0, 1, 2}
        ):
            raise ValueError("Unknown multi-event control")
        passed = max_retries >= (2 if scenario == "second_two_drops" else 1)
        retries = min(max_retries, 2 if scenario == "second_two_drops" else 1)
        attempts = 2 + retries
        injected = [2] if max_retries == 0 else [2, 3]
        return {
            "claimed_success": passed,
            "audit_passed": passed,
            "execution_passed": passed,
            "fault_exposed": True,
            "recovery_attempts": retries,
            "application_write_attempts": attempts,
            "commits": 2 if passed else 1,
            "pending_application_faults": 2 - len(injected),
            "injected_attempts": injected,
            "events_dropped": 0,
            "untargeted_issues_unchanged": True,
            "target_titles_unchanged": True,
            "target_statuses": {
                "ISSUE-1": "done",
                "ISSUE-2": ("done" if task_id == "pair_done" else "in_progress")
                if passed
                else "open",
            },
            "target_versions": {"ISSUE-1": 1, "ISSUE-2": int(passed)},
        }
    if scenario in INDEXED_BROWSER_SCENARIOS:
        if mode != "recover":
            raise ValueError("Indexed controls require recover mode")
        changes = CHANGED_TARGETS[task_id]
        exposed = changes >= 2
        retry = int(exposed and scenario in {"second_drop", "second_timeout_before_commit"})
        return {
            "fault_exposed": exposed,
            "claimed_success": True,
            "audit_passed": True,
            "execution_passed": True,
            "recovery_attempts": retry,
            "commits": changes,
            "application_write_attempts": changes + retry,
            "events_dropped": 0,
            "planned_fault_attempt": 2,
            "injected_attempts": [2] if exposed else [],
            "pending_application_faults": int(not exposed),
        }
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
    expected = expected_control(
        row["task_id"],
        row["scenario"],
        row["mode"],
        row.get("max_retries", 2),
        row.get("max_actions", 8),
        row.get("max_decisions", 8),
    )
    mismatches = {
        key: {"expected": value, "actual": row.get(key)}
        for key, value in expected.items()
        if row.get(key) != value
    }
    result = {
        "task_id": row["task_id"],
        "scenario": row["scenario"],
        "mode": row["mode"],
        "max_retries": row.get("max_retries", 2),
        "artifacts": row["artifacts"],
        "bundle_directory": row.get("bundle_directory"),
        "expected": expected,
        "passed": not mismatches,
        "mismatches": mismatches,
    }
    if (row.get("max_actions", 8), row.get("max_decisions", 8)) != (8, 8):
        result.update(max_actions=row["max_actions"], max_decisions=row["max_decisions"])
    return result


def control_batch_specs(
    *, indexed: bool = False, multi_event: bool = False, budget_boundaries: bool = False
) -> list[dict]:
    if sum((indexed, multi_event, budget_boundaries)) > 1:
        raise ValueError("Select one browser control matrix")
    if budget_boundaries:
        return [
            {
                "tasks": ("pair_done", "mixed_status"),
                "modes": ("recover",),
                "scenarios": ("clean",),
                "max_retries": 2,
                "max_actions": actions,
                "max_decisions": decisions,
            }
            for actions, decisions in ((2, 8), (3, 8), (4, 8), (8, 2), (8, 3), (8, 4))
        ]
    selections = (
        (((tuple(CHANGED_TARGETS)), ("recover",)),)
        if indexed
        else ((tuple(CHANGED_TARGETS), ("recover",)), (("single_done",), ("baseline",)))
    )
    if multi_event:
        selections = ((("pair_done", "mixed_status"), ("recover",)),)
    scenarios = (
        MULTI_BROWSER_SCENARIOS
        if multi_event
        else INDEXED_BROWSER_SCENARIOS
        if indexed
        else BROWSER_SCENARIOS
    )
    return [
        {"tasks": tasks, "modes": modes, "scenarios": scenarios, "max_retries": retries}
        for retries in ((0, 1, 2) if multi_event else (2,))
        for tasks, modes in selections
    ]


def control_budget(spec: dict) -> Budget:
    return Budget(
        max_actions=spec.get("max_actions", 8),
        max_decisions=spec.get("max_decisions", 8),
        timeout_seconds=30,
        action_timeout_seconds=1,
        max_retries=spec["max_retries"],
    )


def control_key(row: dict) -> tuple:
    return (
        row["task_id"],
        row["scenario"],
        row["mode"],
        row["max_retries"],
        row.get("max_actions", 8),
        row.get("max_decisions", 8),
    )


def evaluate_browser_controls(
    output: Path,
    *,
    indexed: bool = False,
    multi_event: bool = False,
    budget_boundaries: bool = False,
) -> dict:
    specs = control_batch_specs(
        indexed=indexed, multi_event=multi_event, budget_boundaries=budget_boundaries
    )
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    result = {
        "schema_version": 1,
        "status": "running",
        "passed": False,
        "provider": "mock",
        "engine": "dynamic",
        "indexed": indexed,
        "multi_event": multi_event,
        "budget_boundaries": budget_boundaries,
        "artifacts": str(directory),
        "batches": [],
        "batch_bindings": [],
        "controls": [],
        "limitations": "Fixed local mechanism controls; not stochastic reliability.",
    }

    def save():
        temporary = directory / "controls.tmp"
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        temporary.replace(directory / "controls.json")

    save()
    try:
        for spec in specs:
            batch = browser_batch(
                directory,
                task_ids=spec["tasks"],
                scenarios=spec["scenarios"],
                modes=spec["modes"],
                budget=control_budget(spec),
            )
            path = Path(batch["artifacts"])
            relative = path.relative_to(directory).as_posix()
            result["batches"].append(batch["artifacts"])
            result["batch_bindings"].append(
                {
                    "directory": relative,
                    "manifest_sha256": hashlib.sha256(
                        (path / "manifest.json").read_bytes()
                    ).hexdigest(),
                }
            )
            result["controls"].extend(
                {**compare_control(row), "batch_directory": relative} for row in batch["trials"]
            )
            save()
    except BaseException:
        result["status"] = "interrupted"
        save()
        raise
    result["status"] = "complete"
    required = {
        (
            task,
            scenario,
            mode,
            spec["max_retries"],
            spec.get("max_actions", 8),
            spec.get("max_decisions", 8),
        )
        for spec in specs
        for task in spec["tasks"]
        for mode in spec["modes"]
        for scenario in spec["scenarios"]
    }
    observed = {control_key(row) for row in result["controls"]}
    result["coverage_complete"] = observed == required and len(result["controls"]) == len(required)
    result["passed"] = result["coverage_complete"] and all(
        row["passed"] for row in result["controls"]
    )
    save()
    return result
