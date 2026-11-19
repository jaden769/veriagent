# Process-isolated sandbox execution

The optional process executor moves each fixed issue read or status update into a fresh
worker. The parent applies tool permissions, launches the installed worker module with
an argument list (no shell), and exchanges one typed UTF-8 JSON request/observation over
pipes. It waits only until the action deadline, then requests termination and confirms
that the worker exited before allowing recovery.

The in-process executor remains the default. Both static and dynamic agents support the
process adapter through `run`, reviewed `execute`, and `smoke`. The local FastAPI `serve`
endpoint still uses the in-process sandbox directly.

## Commands

```powershell
.\.venv\Scripts\veriagent.exe smoke --isolate-tools --action-timeout 3
.\.venv\Scripts\veriagent.exe smoke --engine dynamic --isolate-tools --action-timeout 3
.\.venv\Scripts\veriagent.exe run "Set ISSUE-1 to done" --isolate-tools --action-timeout 2 --timeout 30 --hang-before-commit 1 --db artifacts/before-hang.sqlite
.\.venv\Scripts\veriagent.exe run "Set ISSUE-1 to done" --isolate-tools --action-timeout 2 --timeout 30 --hang-after-commit 1 --db artifacts/after-hang.sqlite
```

Each example defaults to the offline provider. No API key is required. Use fresh database
paths when repeating the hang examples; an already completed task cannot demonstrate the
same recovery condition. The two smoke commands always create fresh UUID directories.

`--action-timeout` includes worker startup, input transfer, execution and the normal
response wait. It defaults to one second; three seconds gives cold worker startup more
room on this Windows/OneDrive checkout. `--timeout` is still the cooperative overall run
budget. Read actions are counted just like writes in the dynamic engine.

`--hang-before-commit N` and `--hang-after-commit N` deliberately inject a 60-second worker
sleep for the next N writes. That sleep ignores the cooperative tool timeout, so passing
these tests requires actual parent-side termination. Hang injection without
`--isolate-tools` is rejected before provider construction or sandbox initialization.
These options exist only for the local controlled environment, not external systems.

## Outcome verification and retry safety

| Interrupted worker | Persisted state | Verified recovery behavior |
|---|---|---|
| Before commit | Target remains unmet | Confirm worker exit, detect mismatch, retry only an idempotent authorized update within budget |
| After commit | Target already satisfied | Confirm worker exit, independently verify completion, do not repeat the write |
| Cleanup cannot be confirmed | State cannot certify safe continuation | Terminal internal failure, unknown verification, no retry or success claim |

Killing a process does not undo a committed operation. The same separate read-only
verifier checks authoritative SQLite state after a timeout. Recovery never infers that
termination means failure to commit. The existing tool allowlist, authorized targets and
statuses, trusted idempotency policy and bounded retry rules remain in force.

An observation includes worker PID, startup/reaping/termination flags, deadline and elapsed
time. Reports identify `tool_execution=process`; configuration and observations are saved
in the normal trace store. `safe_to_continue=false` is trusted adapter metadata for an
unconfirmed cleanup. Both engines stop on it even if a later read could match the task.
It cannot be supplied as a model action argument. Raw worker stderr is not copied into
traces; malformed, mismatched or oversized observations become internal failures.

## Worker lifecycle and fault schedules

The parent owns mutable fault counters. A write reserves at most one scheduled fault
before dispatch: before-commit hang, then after-commit hang, then transient error, then
silent dropped write. Reads do not consume write faults. A killed worker cannot reset
the counter and reintroduce the same one-shot fault on every retry. Reservation is an
attempt schedule, not proof that the worker reached that fault before termination.

After a timeout the parent kills a still-running worker and gives cleanup up to one
additional second. Failure to confirm exit becomes terminal, rather than authorizing a
second possibly overlapping write. Interrupting the parent also requests cleanup before
propagating the interruption. Tests check actual worker process exit, not just a returned
flag. The worker performs one fixed operation and launches no descendants.

## Boundaries and limitations

This is **deadline isolation, not an OS security sandbox**. The worker runs under the
same user account and can access files that account permits. Only the installed fixed
sandbox tools are supported; arbitrary callables, browser processes, process trees and
remote side effects need separate containment and termination designs.

Workers run Python with `-I`, excluding the current directory/user Python configuration
from import search. The parent passes only the platform variables `SYSTEMROOT`, `WINDIR`,
`TEMP`, `TMP`, `PATH` and `COMSPEC` when present. Ambient model credentials, model settings
and `PYTHONPATH` are not inherited. Windows workers use `CREATE_NO_WINDOW`.

An editable or normal package installation is required so `python -I -m veriagent.worker`
can locate the trusted module. PIDs, paths and raw application observations remain local
trace data. Unicode titles are encoded explicitly as UTF-8 across the pipe.

The deadline bounds the normal worker wait, not every possible OS stall. Process creation,
OS scheduling and termination/reaping can add overhead. Model calls, planning, verification
and trace persistence remain outside this worker boundary. Unconfirmed termination can
leave an uncertain process/state requiring manual investigation; the agent stops rather
than continuing. A process crash cannot compensate external non-idempotent operations.

Validation was performed on Windows. No Linux/macOS portability results, browser process
containment, whole-agent hard deadline or general security-isolation guarantee is claimed.
