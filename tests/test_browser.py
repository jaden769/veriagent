import os
import sqlite3
import time
from pathlib import Path

import pytest

from veriagent.browser import BrowserExecutor, BrowserTools, local_browser_app, permitted_request
from veriagent.models import Action, Budget, Failure, Status
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.smoke import smoke_test

browser_test = pytest.mark.skipif(
    os.environ.get("VERIAGENT_BROWSER_TESTS") != "1",
    reason="Set VERIAGENT_BROWSER_TESTS=1 after installing browser extra and Chromium",
)


@pytest.mark.parametrize(
    "url,method,allowed",
    [
        ("http://127.0.0.1:8100/ui/issues/ISSUE-1", "GET", True),
        ("http://127.0.0.1:8100/issues/ISSUE-2/status", "PATCH", True),
        ("http://127.0.0.1:8100/ui/app.js", "GET", True),
        ("https://example.com/issues/ISSUE-1", "GET", False),
        ("http://127.0.0.1:8101/issues/ISSUE-1", "GET", False),
        ("http://127.0.0.1:8100/issues/ISSUE-1?redirect=elsewhere", "GET", False),
        ("http://127.0.0.1:8100/docs", "GET", False),
        ("file:///etc/passwd", "GET", False),
        ("http://127.0.0.1:8100/issues/ISSUE-1/status", "DELETE", False),
    ],
)
def test_requests_are_scoped_to_owned_application(url, method, allowed):
    assert permitted_request("http://127.0.0.1:8100", url, method) is allowed


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000/path",
        "http://127.0.0.1:99999",
    ],
)
def test_reject_arbitrary_browser_origins(origin):
    with pytest.raises(ValueError):
        BrowserTools(origin)


@browser_test
@pytest.mark.parametrize("engine", ["static", "dynamic"])
def test_real_browser_recovery_smoke(tmp_path, engine):
    result = smoke_test(
        tmp_path,
        MockProvider(),
        Budget(timeout_seconds=60, action_timeout_seconds=5),
        engine=engine,
        tool_backend="browser",
    )
    assert result["smoke_passed"] and result["fault_detected"]
    assert result["report"]["tool_execution"] == "browser"
    assert result["report"]["recovery_attempts"] == 1
    assert result["report"]["model_calls"] == 0
    assert result["browser"]["capture_complete"]
    assert result["final_state"][0]["version"] == 1
    assert result["untargeted_issues_unchanged"]
    folder = Path(result["directory"])
    assert (folder / "browser-before.png").stat().st_size > 1000
    assert (folder / "browser-after.png").stat().st_size > 1000
    assert 'data-testid="version">1<' in (folder / "browser-after.html").read_text(encoding="utf-8")


@browser_test
def test_dom_ack_is_not_proof_of_commit_and_title_is_text(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite", Faults(silent_drops=1))
    sandbox.seed()
    title = '<img src="https://example.com/private" onerror="alert(1)">'
    with sqlite3.connect(sandbox.path) as db:
        db.execute("UPDATE issues SET title=? WHERE id='ISSUE-1'", (title,))
    with local_browser_app(sandbox) as origin, BrowserTools(origin) as tools:
        executor = BrowserExecutor(tools)
        result = executor.execute(
            Action(tool="set_status", issue_id="ISSUE-1", status=Status.DONE), 5
        )
        assert result.reported_success
        assert tools.page.get_by_test_id("status").inner_text() == "done"
        assert sandbox.read_issue("ISSUE-1").status == Status.OPEN
        assert tools.page.get_by_test_id("title").inner_text() == title
        assert tools.page.locator("img").count() == 0
        assert tools.blocked_requests == 0
        read = executor.execute(Action(tool="read_issue", issue_id="ISSUE-1"), 5)
        assert read.data["status"] == "open"
        missing = executor.execute(Action(tool="read_issue", issue_id="ISSUE-999"), 5)
        assert missing.failure == Failure.NOT_FOUND
        expired = executor.execute(Action(tool="read_issue", issue_id="ISSUE-1"), 0)
        assert expired.failure == Failure.TIMEOUT
    assert tools.page is None and tools.browser is None


@browser_test
def test_real_transient_status_maps_to_retryable_failure(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite", Faults(transient_errors=1))
    sandbox.seed()
    with local_browser_app(sandbox) as origin, BrowserTools(origin) as tools:
        executor = BrowserExecutor(tools)
        action = Action(tool="set_status", issue_id="ISSUE-1", status=Status.DONE)
        assert executor.execute(action, 5).failure == Failure.TRANSIENT
        assert sandbox.read_issue("ISSUE-1").version == 0
        assert executor.execute(action, 5).reported_success
        assert sandbox.read_issue("ISSUE-1").version == 1


@browser_test
def test_context_blocks_external_navigation(tmp_path):
    from playwright.sync_api import Error

    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    with local_browser_app(sandbox) as origin, BrowserTools(origin) as tools:
        tools.deadline = time.monotonic() + 5
        tools.read_issue("ISSUE-1")
        with pytest.raises(Error):
            tools.page.goto("https://example.com/blocked", timeout=2000)
        assert tools.blocked_requests >= 1


@browser_test
def test_unresponsive_ui_deadline_is_normalized(tmp_path):
    sandbox = Sandbox(tmp_path / "state.sqlite")
    sandbox.seed()
    with local_browser_app(sandbox) as origin, BrowserTools(origin) as tools:
        tools.context.route(
            "**/ui/app.js",
            lambda route: route.fulfill(
                status=200, content_type="application/javascript", body="/* stalled UI */"
            ),
        )
        started = time.monotonic()
        observation = BrowserExecutor(tools).execute(
            Action(tool="read_issue", issue_id="ISSUE-1"), 0.2
        )
        assert observation.failure == Failure.TIMEOUT
        assert time.monotonic() - started < 2


@browser_test
def test_browser_smoke_without_recovery_is_honest(tmp_path):
    result = smoke_test(
        tmp_path,
        MockProvider(),
        Budget(max_retries=0, timeout_seconds=60, action_timeout_seconds=5),
        tool_backend="browser",
    )
    assert not result["smoke_passed"]
    assert result["fault_detected"] and not result["audit"]["passed"]
    assert result["final_state"][0]["status"] == "open"
    assert result["browser"]["capture_complete"]
