"""Deadline isolation for fixed sandbox tools, not a general OS security sandbox."""

import os
import subprocess
import sys
import time

from pydantic import Field

from veriagent.executor import Executor
from veriagent.models import Action, Failure, Observation, Schema, ToolExecutionConfig
from veriagent.sandbox import Sandbox


class WorkerRequest(Schema):
    database: str
    action: Action
    timeout_seconds: float = Field(gt=0, le=3600, allow_inf_nan=False)
    silent_drop: bool = False
    transient_error: bool = False
    delay_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    hang_before_commit: bool = False
    hang_after_commit: bool = False


def worker_environment() -> dict[str, str]:
    allowed = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "COMSPEC"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


class IsolatedExecutor(Executor):
    execution_mode = "process"
    cleanup_timeout_seconds = 1.0

    def __init__(
        self,
        sandbox: Sandbox,
        config: ToolExecutionConfig | None = None,
        allowed_tools: frozenset[str] | None = None,
    ):
        super().__init__(sandbox, allowed_tools)
        self.sandbox = sandbox
        self.config = config or ToolExecutionConfig(mode="process")
        if self.config.mode != "process":
            raise ValueError("IsolatedExecutor requires process mode")
        self.hangs_before_commit = self.config.hangs_before_commit
        self.hangs_after_commit = self.config.hangs_after_commit

    def _request(self, action: Action, timeout: float) -> WorkerRequest:
        options = {}
        if action.tool == "set_status":
            # Reserve a single fault in the parent before dispatch. A killed worker
            # cannot reset a fault counter and cause an unbounded retry schedule.
            if self.hangs_before_commit:
                self.hangs_before_commit -= 1
                options["hang_before_commit"] = True
            elif self.hangs_after_commit:
                self.hangs_after_commit -= 1
                options["hang_after_commit"] = True
            elif self.sandbox.faults.transient_errors:
                self.sandbox.faults.transient_errors -= 1
                options["transient_error"] = True
            elif self.sandbox.faults.silent_drops:
                self.sandbox.faults.silent_drops -= 1
                options["silent_drop"] = True
            options["delay_seconds"] = self.sandbox.faults.delay_seconds
        return WorkerRequest(
            database=str(self.sandbox.path), action=action, timeout_seconds=timeout, **options
        )

    def _stop_and_reap(self, worker: subprocess.Popen) -> bool:
        if worker.poll() is None:
            try:
                worker.kill()
            except OSError:
                pass
        try:
            worker.communicate(timeout=self.cleanup_timeout_seconds)
        except (subprocess.TimeoutExpired, OSError):
            return False
        return worker.poll() is not None

    def execute(self, action: Action, timeout: float) -> Observation:
        start = time.monotonic()
        deadline = start + timeout
        data = {
            "execution": "process",
            "worker_started": False,
            "worker_reaped": False,
            "termination_requested": False,
            "deadline_seconds": timeout,
        }
        failure = None
        worker = None
        try:
            if timeout <= 0:
                raise TimeoutError("No execution time remaining")
            policy = self.policies.get(action.tool)
            if not policy or not policy.allowed:
                raise PermissionError(action.tool)
            worker = subprocess.Popen(
                [sys.executable, "-I", "-m", "veriagent.worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=str(self.sandbox.path.parent),
                env=worker_environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            data.update(worker_started=True, worker_pid=worker.pid)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(worker.args, timeout)
            request = self._request(action, remaining)
            output, _ = worker.communicate(
                request.model_dump_json().encode("utf-8"), timeout=deadline - time.monotonic()
            )
            data["worker_reaped"] = worker.poll() is not None
            if time.monotonic() > deadline:
                raise TimeoutError("Worker returned after its deadline")
            if worker.returncode != 0 or len(output) > 65536:
                raise ValueError("Worker did not return a bounded successful response")
            observation = Observation.model_validate_json(output)
            if observation.action != action:
                raise ValueError("Worker observation does not match requested action")
            failure = observation.failure
            data = {**observation.data, **data}
            if not observation.reported_success and failure is None:
                failure = Failure.INTERNAL
        except PermissionError:
            failure = Failure.PERMISSION
        except (subprocess.TimeoutExpired, TimeoutError):
            failure = Failure.TIMEOUT
            if worker is not None:
                data["termination_requested"] = worker.poll() is None
                data["worker_reaped"] = self._stop_and_reap(worker)
                if not data["worker_reaped"]:
                    failure = Failure.INTERNAL
        except BaseException as exc:
            if worker is not None:
                data["termination_requested"] = worker.poll() is None
                data["worker_reaped"] = self._stop_and_reap(worker)
            if not isinstance(exc, Exception):
                raise
            failure = Failure.INTERNAL
        return Observation(
            action=action,
            reported_success=failure is None,
            data=data,
            failure=failure,
            elapsed_ms=(time.monotonic() - start) * 1000,
            safe_to_continue=worker is None or bool(data["worker_reaped"]),
        )


def sandbox_executor(sandbox: Sandbox, config: ToolExecutionConfig | None = None) -> Executor:
    config = config or ToolExecutionConfig()
    if config.mode == "process":
        return IsolatedExecutor(sandbox, config)
    return Executor(sandbox)
