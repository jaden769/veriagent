import json
import sqlite3
import subprocess
import time

import pytest
from pydantic import ValidationError

from veriagent.agent import Agent
from veriagent.cli import main
from veriagent.dynamic import DynamicAgent
from veriagent.isolated import IsolatedExecutor, worker_environment
from veriagent.models import Action, Budget, Failure, ToolExecutionConfig
from veriagent.planner import MockProvider
from veriagent.sandbox import Faults, Sandbox
from veriagent.smoke import smoke_test
from veriagent.trace import TraceStore
from veriagent.verification import StateVerifier


@pytest.fixture
def sandbox(tmp_path):
    result = Sandbox(tmp_path / "sandbox with spaces" / "state.sqlite")
    result.seed()
    return result


@pytest.fixture
def workers(monkeypatch):
    original = subprocess.Popen
    launched = []

    def capture(*args, **kwargs):
        assert "-I" in args[0]
        assert kwargs["env"] is not None
        assert not {"OPENAI_API_KEY", "OPENAI_MODEL", "PYTHONPATH"} & kwargs["env"].keys()
        process = original(*args, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr("veriagent.isolated.subprocess.Popen", capture)
    yield launched
    # Independent OS process check, not just the observation's claimed cleanup flag.
    assert all(process.poll() is not None for process in launched)


def update():
    return Action(tool="set_status", issue_id="ISSUE-1", status="done")


def test_worker_reads_and_writes_with_actual_process_cleanup(sandbox, workers):
    executor = IsolatedExecutor(sandbox)
    written = executor.execute(update(), 3)
    read = executor.execute(Action(tool="read_issue", issue_id="ISSUE-1"), 3)
    assert written.reported_success and read.reported_success
    assert read.data["status"] == "done" and read.data["version"] == 1
    assert all(result.data["worker_reaped"] for result in (written, read))
    assert all(not result.data["termination_requested"] for result in (written, read))
    assert len(workers) == 2 and workers[0].pid != workers[1].pid


def test_worker_protocol_preserves_unicode_titles(sandbox, workers):
    with sqlite3.connect(sandbox.path) as db:
        db.execute("UPDATE issues SET title=? WHERE id='ISSUE-1'", ("결제 오류 🧪",))
    result = IsolatedExecutor(sandbox).execute(Action(tool="read_issue", issue_id="ISSUE-1"), 3)
    assert result.reported_success and result.data["title"] == "결제 오류 🧪"


def test_hung_worker_is_killed_before_commit_and_next_write_can_recover(sandbox, workers):
    executor = IsolatedExecutor(sandbox, ToolExecutionConfig(mode="process", hangs_before_commit=1))
    start = time.monotonic()
    failed = executor.execute(update(), 2)
    elapsed = time.monotonic() - start
    assert failed.failure == Failure.TIMEOUT and not failed.reported_success
    assert failed.data["termination_requested"] and failed.data["worker_reaped"]
    assert elapsed < 5  # A real 60-second worker hang must not hold the parent.
    assert workers[0].poll() is not None
    assert sandbox.read_issue("ISSUE-1").status == "open"
    repaired = executor.execute(update(), 3)
    assert repaired.reported_success and sandbox.read_issue("ISSUE-1").version == 1


@pytest.mark.parametrize("engine", [Agent, DynamicAgent], ids=["static", "dynamic"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_agents_resolve_real_killed_workers_from_authoritative_state(
    sandbox, tmp_path, workers, engine, when
):
    config = ToolExecutionConfig(
        mode="process",
        hangs_before_commit=int(when == "before"),
        hangs_after_commit=int(when == "after"),
    )
    traces = TraceStore(tmp_path / "traces.sqlite")
    provider = MockProvider()
    agent = engine(
        provider,
        IsolatedExecutor(sandbox, config),
        StateVerifier(sandbox.path),
        traces,
        Budget(action_timeout_seconds=2, timeout_seconds=30),
    )
    report = agent.run(provider.parse("Set ISSUE-1 to done"))
    assert report.verified_success and report.tool_execution == "process"
    assert report.recovery_attempts == int(when == "before")
    assert sandbox.read_issue("ISSUE-1").version == 1
    observations = [
        e["payload"] for e in traces.events(report.run_id) if e["kind"] == "observation"
    ]
    timeouts = [o for o in observations if o["failure"] == "timeout"]
    assert len(timeouts) == 1 and timeouts[0]["data"]["worker_reaped"]
    # After-commit ambiguity must resolve without repeating the write.
    if when == "after":
        assert len([o for o in observations if o["action"]["tool"] == "set_status"]) == 1


def test_repeated_worker_hangs_exhaust_retry_limit(sandbox, tmp_path, workers):
    provider = MockProvider()
    executor = IsolatedExecutor(
        sandbox, ToolExecutionConfig(mode="process", hangs_before_commit=10)
    )
    report = Agent(
        provider,
        executor,
        StateVerifier(sandbox.path),
        TraceStore(tmp_path / "traces.sqlite"),
        Budget(action_timeout_seconds=2, timeout_seconds=30, max_retries=1),
    ).run(provider.parse("Set ISSUE-1 to done"))
    assert report.failure == Failure.TIMEOUT and not report.claimed_success
    assert report.actions == 2 and report.recovery_attempts == 1 and len(workers) == 2
    assert sandbox.read_issue("ISSUE-1").status == "open"


def test_silent_drop_and_transient_fault_counters_survive_worker_boundaries(sandbox, workers):
    sandbox.faults = Faults(silent_drops=1, transient_errors=1)
    executor = IsolatedExecutor(sandbox)
    assert executor.execute(update(), 3).failure == Failure.TRANSIENT
    dropped = executor.execute(update(), 3)
    assert dropped.reported_success and sandbox.read_issue("ISSUE-1").status == "open"
    assert executor.execute(update(), 3).reported_success
    assert sandbox.read_issue("ISSUE-1").status == "done"
    assert sandbox.faults.silent_drops == sandbox.faults.transient_errors == 0


def test_worker_tool_error_is_classified_without_exposing_exception_text(sandbox, workers):
    result = IsolatedExecutor(sandbox).execute(Action(tool="read_issue", issue_id="ISSUE-999"), 3)
    assert result.failure == Failure.NOT_FOUND and result.data["worker_reaped"]


@pytest.mark.parametrize(
    "timeout,allowed,failure", [(0, True, Failure.TIMEOUT), (3, False, Failure.PERMISSION)]
)
def test_rejection_before_launch(sandbox, monkeypatch, timeout, allowed, failure):
    def forbidden(*args, **kwargs):
        pytest.fail("Rejected action must not launch a worker")

    monkeypatch.setattr("veriagent.isolated.subprocess.Popen", forbidden)
    executor = IsolatedExecutor(sandbox, allowed_tools=None if allowed else frozenset())
    result = executor.execute(update(), timeout)
    assert result.failure == failure and not result.data["worker_started"]


@pytest.mark.parametrize("committed", [False, True])
def test_unconfirmed_cleanup_is_terminal_and_cannot_authorize_a_retry(
    sandbox, tmp_path, monkeypatch, committed
):
    class Unreapable:
        pid = 1234
        args = ["fake-worker"]

        def poll(self):
            return None

        def kill(self):
            pass

        def communicate(self, *args, **kwargs):
            raise subprocess.TimeoutExpired(self.args, 1)

    launches = []

    def launch(*args, **kwargs):
        launches.append(1)
        if committed:
            sandbox.set_status("ISSUE-1", update().status, timeout=1)
        return Unreapable()

    monkeypatch.setattr("veriagent.isolated.subprocess.Popen", launch)
    provider = MockProvider()
    traces = TraceStore(tmp_path / "traces.sqlite")
    report = Agent(provider, IsolatedExecutor(sandbox), StateVerifier(sandbox.path), traces).run(
        provider.parse("Set ISSUE-1 to done")
    )
    assert report.failure == Failure.INTERNAL and report.actions == 1
    assert not report.claimed_success and report.verified_success is None
    assert report.recovery_attempts == 0 and len(launches) == 1
    observed = next(
        e["payload"] for e in traces.events(report.run_id) if e["kind"] == "observation"
    )
    assert observed["data"]["worker_reaped"] is False
    assert observed["safe_to_continue"] is False


def test_keyboard_interrupt_requests_worker_cleanup_before_propagating(sandbox, monkeypatch):
    class Interrupted:
        pid = 1234
        args = ["fake-worker"]
        returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def communicate(self, *args, **kwargs):
            if self.returncode is None:
                raise KeyboardInterrupt()
            return b"", b""

    worker = Interrupted()
    monkeypatch.setattr("veriagent.isolated.subprocess.Popen", lambda *args, **kwargs: worker)
    with pytest.raises(KeyboardInterrupt):
        IsolatedExecutor(sandbox).execute(update(), 3)
    assert worker.poll() is not None


def test_failed_worker_start_is_sanitized(sandbox, monkeypatch):
    def failed(*args, **kwargs):
        raise OSError("SECRET-STARTUP-ERROR")

    monkeypatch.setattr("veriagent.isolated.subprocess.Popen", failed)
    observation = IsolatedExecutor(sandbox).execute(update(), 3)
    assert observation.failure == Failure.INTERNAL
    assert "SECRET-STARTUP-ERROR" not in observation.model_dump_json()


def test_worker_environment_does_not_include_model_credentials_or_python_injection(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "SECRET-KEY")
    monkeypatch.setenv("OPENAI_MODEL", "secret-model")
    monkeypatch.setenv("PYTHONPATH", "untrusted-code")
    filtered = worker_environment()
    assert not {"OPENAI_API_KEY", "OPENAI_MODEL", "PYTHONPATH"} & filtered.keys()
    assert "SECRET-KEY" not in json.dumps(filtered)


def test_process_smoke_preserves_dropped_write_evidence(tmp_path, workers):
    result = smoke_test(
        tmp_path,
        MockProvider(),
        Budget(action_timeout_seconds=3, timeout_seconds=30),
        tool_config=ToolExecutionConfig(mode="process"),
    )
    assert result["smoke_passed"] and result["report"]["tool_execution"] == "process"
    assert result["report"]["recovery_attempts"] == 1


def test_hang_configuration_is_rejected_without_isolation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "run",
            "Set ISSUE-1 to done",
            "--hang-before-commit",
            "1",
            "--db",
            str(tmp_path / "new.sqlite"),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2 and "requires --isolate-tools" in capsys.readouterr().err
    assert not (tmp_path / "new.sqlite").exists()
    with pytest.raises(ValidationError):
        ToolExecutionConfig(mode="process", hangs_before_commit=-1)
