"""Explicit expectations for the fixed dynamic mock browser controls."""

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


def expected_control(task_id: str, scenario: str, mode: str, max_retries: int = 2) -> dict:
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
        row["task_id"], row["scenario"], row["mode"], row.get("max_retries", 2)
    )
    mismatches = {
        key: {"expected": value, "actual": row.get(key)}
        for key, value in expected.items()
        if row.get(key) != value
    }
    return {
        "task_id": row["task_id"],
        "scenario": row["scenario"],
        "mode": row["mode"],
        "max_retries": row.get("max_retries", 2),
        "artifacts": row["artifacts"],
        "expected": expected,
        "passed": not mismatches,
        "mismatches": mismatches,
    }


def evaluate_browser_controls(
    output: Path, *, indexed: bool = False, multi_event: bool = False
) -> dict:
    if indexed and multi_event:
        raise ValueError("Select one browser control matrix")
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
        selections = (
            ((tuple(CHANGED_TARGETS), ("recover",)),)
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
        retry_limits = (0, 1, 2) if multi_event else (2,)
        for retries in retry_limits:
            for tasks, modes in selections:
                options = (
                    {
                        "budget": Budget(
                            max_actions=8,
                            max_decisions=8,
                            timeout_seconds=30,
                            action_timeout_seconds=1,
                            max_retries=retries,
                        )
                    }
                    if multi_event
                    else {}
                )
                batch = browser_batch(
                    directory, task_ids=tasks, scenarios=scenarios, modes=modes, **options
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
        (task, scenario, mode, retries)
        for retries in retry_limits
        for tasks, modes in selections
        for task in tasks
        for mode in modes
        for scenario in scenarios
    }
    observed = {
        (r["task_id"], r["scenario"], r["mode"], r["max_retries"]) for r in result["controls"]
    }
    result["coverage_complete"] = observed == required and len(result["controls"]) == len(required)
    result["passed"] = result["coverage_complete"] and all(
        row["passed"] for row in result["controls"]
    )
    save()
    return result
