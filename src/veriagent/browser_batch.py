"""Bounded offline browser corpus runs with realized exposure and durable manifests."""

import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from veriagent.benchmark_cases import select_cases
from veriagent.browser_execution import execute_browser
from veriagent.browser_faults import (
    ALL_BROWSER_SCENARIOS,
    INDEXED_BROWSER_SCENARIOS,
    validate_browser_deadline,
)
from veriagent.interpretation import proposal_digest
from veriagent.models import Budget, Interpretation, Mode, TaskProposal
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.trace import TraceStore


def summarize(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        key = (row["task_id"], row["scenario"], row["mode"])
        groups.setdefault(key, []).append(row)
    output = []
    for (task, scenario, mode), trials in groups.items():
        claims = sum(r["claimed_success"] for r in trials)
        exposed = [r for r in trials if r["fault_exposed"]]
        false_claims = sum(r["claimed_success"] and not r["audit_passed"] for r in trials)
        output.append(
            {
                "task_id": task,
                "scenario": scenario,
                "mode": mode,
                "runs": len(trials),
                "fault_exposed_runs": len(exposed),
                "unexposed_runs": len(trials) - len(exposed),
                "audited_successes": sum(r["audit_passed"] for r in trials),
                "execution_passes": sum(r["execution_passed"] for r in trials),
                "claimed_successes": claims,
                "false_successes": false_claims,
                "false_success_given_claim": false_claims / claims if claims else None,
                "audited_success_given_exposure": (
                    sum(r["audit_passed"] for r in exposed) / len(exposed) if exposed else None
                ),
            }
        )
    return output


def browser_batch(
    output: Path,
    *,
    task_ids=("single_done",),
    scenarios=("clean", "silent_drop"),
    modes=(Mode.RECOVER,),
    repeats=1,
    engine="dynamic",
    budget=None,
) -> dict:
    cases, corpus_hash = select_cases(tuple(task_ids))
    budget = budget or Budget(
        max_actions=8, max_decisions=8, timeout_seconds=30, action_timeout_seconds=1
    )
    if engine not in {"static", "dynamic"}:
        raise ValueError("Unknown engine")
    if (
        not scenarios
        or len(set(scenarios)) != len(scenarios)
        or any(s not in ALL_BROWSER_SCENARIOS for s in scenarios)
    ):
        raise ValueError("Select unique browser scenarios")
    modes = tuple(Mode(m) for m in modes)
    if not modes or len(set(modes)) != len(modes):
        raise ValueError("Select unique modes")
    if not 1 <= repeats <= 20 or repeats * len(cases) * len(scenarios) * len(modes) > 120:
        raise ValueError("Select 1 to 20 repeats and at most 120 runs")
    for scenario in scenarios:
        validate_browser_deadline(scenario, budget.action_timeout_seconds)
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "status": "running",
        "provider": "mock",
        "engine": engine,
        "corpus_sha256": corpus_hash,
        "budget": budget.model_dump(mode="json"),
        "configuration": {
            "tasks": list(task_ids),
            "scenarios": list(scenarios),
            "modes": [m.value for m in modes],
            "repeats": repeats,
        },
        "source_sha256": {
            p.relative_to(Path(__file__).parent).as_posix(): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sorted(Path(__file__).parent.rglob("*"))
            if p.is_file() and p.suffix in {".py", ".js", ".html", ".json"}
        },
        "limitations": "Deterministic local fixture runs; no stochastic reliability estimate.",
        "artifacts": str(directory),
        "trials": [],
        "summaries": [],
    }

    def save():
        manifest["summaries"] = summarize(manifest["trials"])
        temporary = directory / "manifest.tmp"
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.replace(directory / "manifest.json")

    save()
    try:
        for case in cases:
            for scenario in scenarios:
                for mode in modes:
                    for repeat in range(repeats):
                        trial = directory / f"trial-{len(manifest['trials']) + 1:03d}"
                        trial.mkdir()
                        manifest["active_trial"] = str(trial)
                        save()
                        sandbox = Sandbox(
                            trial / "state.sqlite",
                            Faults(silent_drops=int(scenario == "silent_drop")),
                        )
                        sandbox.seed()
                        with sqlite3.connect(sandbox.path) as db:
                            db.executemany(
                                "UPDATE issues SET status=? WHERE id=?",
                                [(s.value, i) for i, s in case.initial_statuses.items()],
                            )
                        proposal = TaskProposal(
                            objective=case.task.objective,
                            interpretation=Interpretation(requirements=case.task.requirements),
                        )
                        result = execute_browser(
                            proposal,
                            MockProvider(),
                            sandbox,
                            TraceStore(trial / "traces.sqlite"),
                            budget,
                            output=trial,
                            engine=engine,
                            mode=mode,
                            browser_scenario=scenario,
                        )
                        evidence = Path(result["browser_artifacts"])
                        events = json.loads((evidence / "application-events.json").read_text())
                        exposed = (
                            sandbox.faults.silent_drops == 0
                            if scenario == "silent_drop"
                            else any(e.get("injected") == scenario for e in events)
                            if scenario != "clean"
                            else False
                        )
                        manifest["trials"].append(
                            {
                                "task_id": case.id,
                                "scenario": scenario,
                                "mode": mode.value,
                                "repeat": repeat,
                                "approval_digest": proposal_digest(proposal),
                                "artifacts": str(evidence),
                                "fault_exposed": exposed,
                                "claimed_success": result["claimed_success"],
                                "audit_passed": result["browser_audit"]["passed"],
                                "execution_passed": result["browser_execution_passed"],
                                "actions": result["actions"],
                                "recovery_attempts": result["recovery_attempts"],
                                "application_write_attempts": len(events),
                                "commits": sum(e["committed"] for e in events),
                                "events_dropped": result["browser"]["events_dropped"],
                                "planned_fault_attempt": 2
                                if scenario in INDEXED_BROWSER_SCENARIOS
                                else None,
                                "injected_attempts": [
                                    e["attempt"] for e in events if e.get("injected") == scenario
                                ],
                                "pending_application_faults": result["browser"][
                                    "pending_application_faults"
                                ],
                            }
                        )
                        save()
    except BaseException:
        manifest["status"] = "interrupted"
        save()
        raise
    manifest["status"] = "complete"
    manifest.pop("active_trial", None)
    save()
    return manifest
