"""Fixed local browser tools; no arbitrary URLs, selectors, scripts or user profiles."""

import os
import re
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn

from veriagent.api import create_app
from veriagent.executor import Executor
from veriagent.models import Action, Issue, Observation, Status
from veriagent.sandbox import Sandbox, TransientError


class BrowserSetupError(Exception):
    """A bounded setup message without browser/environment exception details."""


@contextmanager
def local_browser_app(sandbox: Sandbox):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(sandbox), log_level="error", access_log=False, lifespan="off")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not server.started:
            raise BrowserSetupError("Local browser application did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=3)
        if thread.is_alive():
            server.force_exit = True
            thread.join(timeout=1)
        listener.close()
        if thread.is_alive():
            raise BrowserSetupError("Local application cleanup could not be confirmed")


def permitted_request(origin: str, url: str, method: str) -> bool:
    parsed = urlsplit(url)
    if f"{parsed.scheme}://{parsed.netloc}" != origin or parsed.query or parsed.fragment:
        return False
    if method == "GET":
        return parsed.path == "/ui/app.js" or bool(
            re.fullmatch(r"/(?:ui/)?issues/ISSUE-\d+", parsed.path)
        )
    return method == "PATCH" and bool(re.fullmatch(r"/issues/ISSUE-\d+/status", parsed.path))


class BrowserTools:
    def __init__(self, origin: str):
        if (
            not re.fullmatch(r"http://127\.0\.0\.1:[1-9]\d{0,4}", origin)
            or int(urlsplit(origin).port) > 65535
        ):
            raise ValueError("Browser tools require the owned loopback application origin")
        self.origin = origin
        self.playwright = self.browser = self.context = self.page = None
        self.deadline = 0.0
        self.blocked_requests = 0

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise BrowserSetupError(
                "Install the browser extra and run: python -m playwright install chromium"
            ) from None
        try:
            self.playwright = sync_playwright().start()
            allowed_env = {
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "PATH",
                "COMSPEC",
                "USERPROFILE",
                "LOCALAPPDATA",
                "APPDATA",
            }
            self.browser = self.playwright.chromium.launch(
                headless=True,
                timeout=15000,
                env={k: v for k, v in os.environ.items() if k.upper() in allowed_env},
            )
            self.context = self.browser.new_context(
                service_workers="block",
                accept_downloads=False,
                viewport={"width": 1000, "height": 760},
            )
            self.context.route("**/*", self._route)
            self.page = self.context.new_page()
        except Exception:
            self.close()
            raise BrowserSetupError(
                "Chromium could not start; run: python -m playwright install chromium"
            ) from None
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        try:
            if self.browser is not None:
                self.browser.close()
        finally:
            if self.playwright is not None:
                self.playwright.stop()
            self.playwright = self.browser = self.context = self.page = None

    def _route(self, route):
        if permitted_request(self.origin, route.request.url, route.request.method):
            route.continue_()
        else:
            self.blocked_requests += 1
            route.abort("blockedbyclient")

    def _remaining_ms(self) -> float:
        remaining = (self.deadline - time.monotonic()) * 1000
        if remaining <= 0:
            raise TimeoutError("Browser action deadline exhausted")
        return remaining

    @contextmanager
    def _timeouts(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        try:
            yield
        except PlaywrightTimeout:
            raise TimeoutError(
                "Browser action exceeded its deadline; commit may be ambiguous"
            ) from None

    def _open(self, issue_id: str):
        if not re.fullmatch(r"ISSUE-\d+", issue_id):
            raise ValueError("Invalid issue ID")
        self.page.goto(
            f"{self.origin}/ui/issues/{issue_id}",
            wait_until="domcontentloaded",
            timeout=self._remaining_ms(),
        )
        ready = self.page.locator('[data-testid="result"][data-phase="ready"]')
        ready.wait_for(timeout=self._remaining_ms())
        self._check_code(ready.get_attribute("data-code", timeout=self._remaining_ms()))

    @staticmethod
    def _check_code(code):
        if code == "404":
            raise KeyError("Issue not found")
        if code == "503":
            raise TransientError("Browser application reported a transient failure")
        if code == "504":
            raise TimeoutError("Browser application reported a deadline")
        if code != "200":
            raise RuntimeError("Browser application request failed")

    def read_issue(self, issue_id: str) -> Issue:
        with self._timeouts():
            self._open(issue_id)

            def value(name):
                return self.page.get_by_test_id(name).inner_text(timeout=self._remaining_ms())

            return Issue(
                id=issue_id,
                title=value("title"),
                status=Status(value("status")),
                version=int(value("version")),
            )

    def set_status(self, issue_id: str, status: Status, *, timeout: float) -> dict:
        with self._timeouts():
            self._open(issue_id)
            self.page.get_by_test_id("status-choice").select_option(
                status.value, timeout=self._remaining_ms()
            )
            self.page.get_by_test_id("save").click(timeout=self._remaining_ms())
            done = self.page.locator('[data-testid="result"][data-phase="done"]')
            done.wait_for(timeout=self._remaining_ms())
            self._check_code(done.get_attribute("data-code", timeout=self._remaining_ms()))
            return {"message": "Browser reported status updated", "status": status.value}

    def screenshot(self, path: Path) -> None:
        self.page.screenshot(path=str(path), timeout=5000)


class BrowserExecutor(Executor):
    execution_mode = "browser"

    def execute(self, action: Action, timeout: float) -> Observation:
        self.tools.deadline = time.monotonic() + timeout
        return super().execute(action, timeout)
