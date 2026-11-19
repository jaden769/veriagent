"""Single-request subprocess entry point for the fixed local sandbox tools."""

import sys
import time
from pathlib import Path

from veriagent.executor import Executor
from veriagent.isolated import WorkerRequest
from veriagent.sandbox import Faults, Sandbox


def main() -> None:
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise SystemExit(2)
    request = WorkerRequest.model_validate_json(raw)
    sandbox = Sandbox(
        Path(request.database),
        Faults(
            silent_drops=int(request.silent_drop),
            transient_errors=int(request.transient_error),
            delay_seconds=request.delay_seconds,
        ),
    )
    if request.hang_before_commit:
        time.sleep(60)  # Deliberately ignores the cooperative tool timeout; parent must kill us.
    observation = Executor(sandbox).execute(request.action, request.timeout_seconds)
    if request.hang_after_commit and observation.reported_success:
        time.sleep(60)  # The write may already be durable when the deadline expires.
    sys.stdout.buffer.write(observation.model_dump_json().encode("utf-8"))


if __name__ == "__main__":
    main()
