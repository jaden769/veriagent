"""Read-only reconciliation of bounded local browser batch evidence."""

import hashlib
import json
import re
from itertools import product
from pathlib import Path

from veriagent.benchmark_cases import select_cases
from veriagent.browser_batch import summarize
from veriagent.browser_evidence import _read, audit_browser_evidence
from veriagent.browser_faults import (
    ALL_BROWSER_SCENARIOS,
    INDEXED_BROWSER_SCENARIOS,
    browser_schedule,
    validate_browser_deadline,
)
from veriagent.interpretation import proposal_digest
from veriagent.models import Budget, Mode, TaskProposal


def audit_browser_batch(directory: Path) -> dict:
    result = {
        "schema_version": 1,
        "evidence_passed": False,
        "checks": [],
        "trials": [],
        "limitations": "Unsigned saved-evidence reconciliation; not authenticated provenance.",
    }

    def check(name, passed):
        result["checks"].append({"check": name, "passed": bool(passed)})

    try:
        manifest = json.loads(_read(directory, "manifest.json"))
        config = manifest["configuration"]
        cases, digest = select_cases(tuple(config["tasks"]))
        scenarios, modes, repeats = config["scenarios"], config["modes"], config["repeats"]
        if (
            not scenarios
            or len(set(scenarios)) != len(scenarios)
            or any(s not in ALL_BROWSER_SCENARIOS for s in scenarios)
            or not modes
            or len(set(modes)) != len(modes)
            or any(m not in {v.value for v in Mode} for m in modes)
            or type(repeats) is not int
            or not 1 <= repeats <= 20
            or len(cases) * len(scenarios) * len(modes) * repeats > 120
        ):
            raise ValueError("Invalid batch selection")
        budget = Budget.model_validate(manifest["budget"])
        for scenario in scenarios:
            validate_browser_deadline(scenario, budget.action_timeout_seconds)
        check("manifest_version", manifest["schema_version"] == 1)
        check(
            "completed_batch", manifest["status"] == "complete" and "active_trial" not in manifest
        )
        check("corpus_hash", manifest["corpus_sha256"] == digest)
        check(
            "offline_engine",
            manifest["provider"] == "mock" and manifest["engine"] in {"static", "dynamic"},
        )
        rows = manifest["trials"]
        if not isinstance(rows, list) or len(rows) > 120:
            raise ValueError("Invalid trial list")
        if any(type(row["repeat"]) is not int for row in rows):
            raise ValueError("Invalid repeat index")
        keys = [(r["task_id"], r["scenario"], r["mode"], r["repeat"]) for r in rows]
        expected = set(product([c.id for c in cases], scenarios, modes, range(repeats)))
        check("trial_coverage", len(keys) == len(expected) and set(keys) == expected)
        mapping = {c.id: c for c in cases}
        rebuilt = []
        seen = set()
        run_ids = set()
        for ordinal, row in enumerate(rows, 1):
            relative = row["bundle_directory"]
            if (
                not isinstance(relative, str)
                or not re.fullmatch(rf"trial-{ordinal:03d}/[0-9a-f]{{32}}", relative)
                or relative in seen
            ):
                raise ValueError("Invalid trial directory")
            seen.add(relative)
            bundle_path = directory / relative
            if not bundle_path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Trial escapes batch")
            trial_audit = audit_browser_evidence(bundle_path)
            result["trials"].append({"bundle_directory": relative, **trial_audit})
            check(f"trial_evidence:{ordinal}", trial_audit["evidence_passed"])
            check(
                f"inventory_binding:{ordinal}",
                hashlib.sha256(_read(bundle_path, "evidence.json")).hexdigest()
                == row["inventory_sha256"],
            )
            bundle = json.loads(_read(bundle_path, "result.json"))
            events = json.loads(_read(bundle_path, "application-events.json"))
            proposal = TaskProposal.model_validate(bundle["proposal"])
            case, scenario = mapping[row["task_id"]], row["scenario"]
            saved = bundle["result"]
            check(f"unique_run:{ordinal}", saved["run_id"] not in run_ids)
            run_ids.add(saved["run_id"])
            check(f"trial_task:{ordinal}", proposal.task() == case.task)
            check(
                f"initial_state:{ordinal}",
                {r["id"]: r["status"] for r in bundle["initial_state"]}
                == {i: s.value for i, s in case.initial_statuses.items()}
                and all(r["version"] == 0 for r in bundle["initial_state"]),
            )
            check(
                f"trial_configuration:{ordinal}",
                bundle["budget"] == budget.model_dump(mode="json")
                and saved["mode"] == row["mode"]
                and saved["engine"] == manifest["engine"]
                and saved["browser"]["scenario"] == scenario
                and saved["tool_execution"] == "browser"
                and saved["model_usage"]["provider"] == "mock"
                and saved["model_calls"] == 0,
            )
            evidence = saved["browser_audit"]["evidence"]
            injected = [e for e in events if e.get("injected") == scenario]
            schedule = browser_schedule(scenario)
            pending = (
                0
                if scenario in {"clean", "silent_drop"}
                else ((len(schedule) if schedule else 1) - len(injected))
            )
            check(
                f"fault_schedule:{ordinal}",
                pending >= 0
                and all(e.get("injected") in {None, scenario} for e in events)
                and (
                    not schedule
                    or all(schedule.get(e["attempt"]) == e["injected_kind"] for e in injected)
                )
                and saved["browser"]["pending_application_faults"] == pending,
            )
            actual = {
                "task_id": case.id,
                "scenario": scenario,
                "mode": saved["mode"],
                "repeat": row["repeat"],
                "approval_digest": proposal_digest(proposal),
                "bundle_directory": relative,
                "inventory_sha256": row["inventory_sha256"],
                "artifacts": row["artifacts"],
                "fault_exposed": bool(injected) if scenario != "clean" else False,
                "claimed_success": saved["claimed_success"],
                "audit_passed": saved["browser_audit"]["passed"],
                "execution_passed": saved["browser_execution_passed"],
                "actions": saved["actions"],
                "recovery_attempts": saved["recovery_attempts"],
                "application_write_attempts": len(events),
                "commits": sum(e["committed"] for e in events),
                "events_dropped": saved["browser"]["events_dropped"],
                "planned_fault_attempt": 2 if scenario in INDEXED_BROWSER_SCENARIOS else None,
                "injected_attempts": [e["attempt"] for e in injected],
                "pending_application_faults": pending,
                "planned_faults": [
                    {"attempt": i, "kind": k} for i, k in browser_schedule(scenario).items()
                ],
                "max_retries": budget.max_retries,
                "target_statuses": {e["issue_id"]: e["actual"] for e in evidence},
                "target_versions": {e["issue_id"]: e["version"] for e in evidence},
                "untargeted_issues_unchanged": saved["browser_audit"][
                    "untargeted_issues_unchanged"
                ],
                "target_titles_unchanged": saved["browser_audit"]["target_titles_unchanged"],
            }
            for name, value in {
                "max_actions": budget.max_actions,
                "max_decisions": budget.max_decisions,
                "decisions": saved["decisions"],
                "failure": saved["failure"],
            }.items():
                if name in row:
                    actual[name] = value
            check(f"trial_row:{ordinal}", row == actual)
            rebuilt.append(actual)
        recomputed = summarize(rebuilt)
        check("summaries", manifest["summaries"] == recomputed)
        result["summaries"] = recomputed
        result["evidence_passed"] = all(c["passed"] for c in result["checks"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        check("readable_complete_batch", False)
    return result
