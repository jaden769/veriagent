"""One isolated verification/recovery check, ready for either mock or live planning."""

import json
import platform
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal
from uuid import uuid4

from veriagent.agent import Agent
from veriagent.browser_faults import (
    BROWSER_SCENARIOS,
    TIMEOUT_SCENARIOS,
    BrowserAppFaults,
    validate_browser_deadline,
)
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
    tool_backend: Literal["sandbox", "browser"] = "sandbox",
    browser_scenario: str = "silent_drop",
) -> dict:
    """Save an honest result even when the model refuses or returns an invalid plan.

    The default dropped-write case requires a detected mismatch and actual recovery.
    Browser post-commit cases instead require anomaly evidence and no replay. The caller owns
    the provider and closes its resources. Dynamic selection can make multiple model calls.
    """
    if engine not in {"static", "dynamic"}:
        raise ValueError("Unknown engine")
    if tool_backend not in {"sandbox", "browser"}:
        raise ValueError("Unknown tool backend")
    if tool_backend == "browser" and tool_config is not None:
        raise ValueError("Browser tools cannot use process-worker configuration")
    if browser_scenario not in BROWSER_SCENARIOS or (
        tool_backend != "browser" and browser_scenario != "silent_drop"
    ):
        raise ValueError("Invalid browser scenario for this backend")
    budget = budget or Budget(timeout_seconds=60)
    validate_browser_deadline(browser_scenario, budget.action_timeout_seconds)
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    faults = Faults(silent_drops=int(browser_scenario == "silent_drop"))
    sandbox = Sandbox(directory / "state.sqlite", faults)
    sandbox.seed()
    traces = TraceStore(directory / "traces.sqlite")
    verifier = StateVerifier(sandbox.path)
    task = MockProvider().parse("Set ISSUE-1 to done")
    initial = [sandbox.read_issue(f"ISSUE-{i}") for i in range(1, 4)]
    agent_class = DynamicAgent if engine == "dynamic" else Agent
    browser_evidence = None
    if tool_backend == "browser":
        from veriagent.browser import BrowserExecutor, BrowserTools, local_browser_app

        app_faults = BrowserAppFaults(browser_scenario)
        with (
            local_browser_app(sandbox, app_faults) as origin,
            BrowserTools(origin, release_pending=app_faults.release_pending) as tools,
        ):
            tools.deadline = time.monotonic() + 5
            tools.read_issue("ISSUE-1")
            tools.screenshot(directory / "browser-before.png")
            report = agent_class(provider, BrowserExecutor(tools), verifier, traces, budget).run(
                task, Mode.RECOVER
            )
            browser_evidence = {
                "version": tools.browser.version,
                "blocked_requests": tools.blocked_requests,
                "capture_complete": False,
                "scenario": browser_scenario,
                "browser_events": tools.events,
                "application_events": app_faults.events,
                "pending_application_faults": app_faults.remaining,
            }
            try:
                tools.deadline = time.monotonic() + 5
                tools.read_issue("ISSUE-1")
                tools.screenshot(directory / "browser-after.png")
                (directory / "browser-after.html").write_text(
                    tools.page.content(), encoding="utf-8"
                )
                browser_evidence["capture_complete"] = True
            except Exception:
                # Preserve the report and independent audit if final browser capture fails.
                pass
            browser_evidence["events_dropped"] = tools.events_dropped + app_faults.events_dropped
        for name, event_log in (
            ("browser-events", tools.events),
            ("application-events", app_faults.events),
        ):
            (directory / f"{name}.json").write_text(
                json.dumps(event_log, indent=2) + "\n", encoding="utf-8"
            )
    else:
        report = agent_class(
            provider, sandbox_executor(sandbox, tool_config), verifier, traces, budget
        ).run(task, Mode.RECOVER)
    audit = verifier.verify(task)
    traces.append(report.run_id, "evaluation_audit", audit)
    events = traces.events(report.run_id)
    # An initially-open target is not an injected failure. Count only mismatches
    # observed after a mutation observation, excluding dynamic initial verification.
    seen_write = detected = False
    for event in events:
        if event["kind"] == "observation" and event["payload"]["action"]["tool"] == "set_status":
            seen_write = True
        if (
            seen_write
            and event["kind"] == "verification"
            and event["payload"]["failure"] == "state_mismatch"
        ):
            detected = True
    final = [sandbox.read_issue(f"ISSUE-{i}") for i in range(1, 4)]
    untouched = initial[1:] == final[1:]
    base_passed = (
        report.claimed_success and report.verified_success is True and audit.passed and untouched
    )
    anomaly_observed = detected
    expectations = detected and report.recovery_attempts > 0 and faults.silent_drops == 0
    if tool_backend == "browser" and browser_scenario != "silent_drop":
        application = browser_evidence["application_events"]
        dom = browser_evidence["browser_events"]
        anomaly_observed = any(e["injected"] == browser_scenario for e in application)
        if browser_scenario == "stale_dom":
            anomaly_observed = anomaly_observed and any(
                e["kind"] == "dom_write_result"
                and e["http_status"] == 200
                and e["displayed_status"] != e["requested_status"]
                for e in dom
            )
        elif browser_scenario == "lost_ack":
            anomaly_observed = anomaly_observed and any(
                e["kind"] == "action_result" and e["failure"] == "transient" for e in dom
            )
        elif browser_scenario in TIMEOUT_SCENARIOS:
            anomaly_observed = (
                anomaly_observed
                and any(e["kind"] == "action_result" and e["failure"] == "timeout" for e in dom)
                and any(e.get("release_reason") == "action_timeout" for e in application)
            )
        expectations = browser_scenario == "clean" or (
            anomaly_observed
            and len(application) == 1
            and application[0]["committed"]
            and report.recovery_attempts == 0
        )
        if browser_scenario == "timeout_before_commit":
            expectations = (
                anomaly_observed
                and detected
                and len(application) == 2
                and not application[0]["committed"]
                and application[1]["committed"]
                and report.recovery_attempts > 0
            )
    if browser_evidence and browser_evidence["events_dropped"]:
        expectations = False
    passed = base_passed and expectations
    packages = {}
    for name in ("veriagent", "pydantic", "openai", "playwright"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    result = {
        "schema_version": 1,
        "scenario": browser_scenario,
        "engine": engine,
        "tool_backend": tool_backend,
        "browser": browser_evidence,
        "directory": str(directory),
        "smoke_passed": passed,
        "fault_detected": detected,
        "anomaly_observed": anomaly_observed,
        "recovery_required": browser_scenario in {"silent_drop", "timeout_before_commit"},
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
            "scenario": browser_scenario,
            "fault_detected": detected,
            "anomaly_observed": anomaly_observed,
            "recovery_required": browser_scenario in {"silent_drop", "timeout_before_commit"},
            "untargeted_issues_unchanged": untouched,
        },
    )
    traces.export(report.run_id, directory / "trace.json")
    (directory / "trace.txt").write_text(traces.render(report.run_id) + "\n", encoding="utf-8")
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
