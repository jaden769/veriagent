"""Reviewed local-browser execution and a separate final-state/collateral audit."""

import json
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from veriagent.agent import Agent
from veriagent.browser import BrowserExecutor, BrowserSetupError, BrowserTools, local_browser_app
from veriagent.browser_faults import BrowserAppFaults
from veriagent.dynamic import DynamicAgent
from veriagent.interpretation import proposal_digest
from veriagent.models import Budget, Mode, Task, TaskProposal
from veriagent.sandbox import Sandbox
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


def snapshot(path: Path) -> list[dict]:
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in db.execute("SELECT id,title,status,version FROM issues ORDER BY id")
        ]


def audit_browser_state(task: Task, initial: list[dict], final: list[dict]) -> dict:
    before = {row["id"]: row for row in initial}
    after = {row["id"]: row for row in final}
    targets = {requirement.issue_id for requirement in task.requirements}
    evidence = [
        {
            "issue_id": r.issue_id,
            "expected": r.status.value,
            "actual": after.get(r.issue_id, {}).get("status"),
            "version": after.get(r.issue_id, {}).get("version"),
        }
        for r in task.requirements
    ]
    targets_passed = all(e["actual"] == e["expected"] for e in evidence)
    unchanged = all(
        before.get(issue) == after.get(issue) for issue in (before.keys() | after.keys()) - targets
    )
    titles_unchanged = all(
        before.get(issue, {}).get("title") == after.get(issue, {}).get("title") for issue in targets
    )
    return {
        "passed": targets_passed and unchanged and titles_unchanged,
        "targets_passed": targets_passed,
        "untargeted_issues_unchanged": unchanged,
        "target_titles_unchanged": titles_unchanged,
        "evidence": evidence,
        "source": "sqlite_read_only",
    }


def _capture(tools: BrowserTools, task: Task, directory: Path, phase: str) -> list[dict]:
    captures = []
    for index, requirement in enumerate(task.requirements, start=1):
        captured = False
        try:
            tools.deadline = time.monotonic() + 5
            tools.read_issue(requirement.issue_id)
            tools.screenshot(directory / f"{phase}-{index:03d}.png")
            (directory / f"{phase}-{index:03d}.html").write_text(
                tools.page.content(), encoding="utf-8"
            )
            captured = True
        except Exception:
            pass  # Preserve execution/audit evidence without storing raw browser exceptions.
        captures.append({"issue_id": requirement.issue_id, "phase": phase, "captured": captured})
    return captures


def execute_browser(
    proposal: TaskProposal,
    provider,
    sandbox: Sandbox,
    traces: TraceStore,
    budget: Budget,
    *,
    output: Path,
    engine: str = "static",
    mode: Mode = Mode.RECOVER,
    browser_scenario: str = "clean",
) -> dict:
    # The caller verified the digest before constructing state/provider. Retain the exact
    # immutable proposal; never reread its file or reconstruct requirements from the model.
    task = proposal.task()
    app_faults = BrowserAppFaults(browser_scenario)
    if engine not in {"static", "dynamic"}:
        raise ValueError("Unknown engine")
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    initial = snapshot(sandbox.path)
    report = None
    captures = []
    browser_version = None
    blocked_requests = 0
    cleanup_completed = False
    try:
        with local_browser_app(sandbox, app_faults) as origin, BrowserTools(origin) as tools:
            browser_version = tools.browser.version
            captures.extend(_capture(tools, task, directory, "before"))
            agent_class = DynamicAgent if engine == "dynamic" else Agent
            report = agent_class(
                provider, BrowserExecutor(tools), StateVerifier(sandbox.path), traces, budget
            ).run(task, mode, reviewed_proposal=proposal)
            captures.extend(_capture(tools, task, directory, "after"))
            blocked_requests = tools.blocked_requests
            browser_events = tools.events
            events_dropped = tools.events_dropped + app_faults.events_dropped
        cleanup_completed = True
    except BrowserSetupError:
        if report is None:
            (directory / "setup-error.json").write_text(
                json.dumps({"error": "browser_setup_failed", "initial_state": initial}) + "\n",
                encoding="utf-8",
            )
            raise
        # A completed agent claim is retained, but cannot pass with unconfirmed cleanup.
    final = snapshot(sandbox.path)
    audit = audit_browser_state(task, initial, final)
    passed = report.claimed_success and audit["passed"] and cleanup_completed
    result = {
        **report.model_dump(mode="json"),
        "browser_execution_passed": passed,
        "browser_audit": audit,
        "browser_artifacts": str(directory),
        "browser": {
            "version": browser_version,
            "blocked_requests": blocked_requests,
            "cleanup_completed": cleanup_completed,
            "captures": captures,
            "scenario": browser_scenario,
            "pending_application_faults": app_faults.remaining,
            "events_dropped": events_dropped,
        },
    }
    for name, event_log in (
        ("browser-events", browser_events),
        ("application-events", app_faults.events),
    ):
        (directory / f"{name}.json").write_text(
            json.dumps(event_log, indent=2) + "\n", encoding="utf-8"
        )
    traces.append(
        report.run_id,
        "browser_execution_audit",
        {**audit, "browser_execution_passed": passed, "cleanup_completed": cleanup_completed},
    )
    traces.export(report.run_id, directory / "trace.json")
    (directory / "trace.txt").write_text(traces.render(report.run_id) + "\n", encoding="utf-8")
    bundle = {
        "schema_version": 1,
        "task": task.model_dump(mode="json"),
        "proposal": proposal.model_dump(mode="json"),
        "approval_digest": proposal_digest(proposal),
        "budget": budget.model_dump(mode="json"),
        "initial_state": initial,
        "final_state": final,
        "result": result,
    }
    (directory / "result.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    return result
