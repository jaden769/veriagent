# Offline reflection trace reconciliation

`research.reflection_trace.reconcile_reflection_trace(events, expected_run_id=...)`
checks saved prototype events without calling a provider, executing tools or opening a
state database. It returns a `reflection_trace_consistency` summary or raises
`ValueError` for inconsistent evidence. This is a research Python API, not a CLI command.

The bounded input must contain the original task, configuration and terminal native
ReflectionReport. The checker replays execution/corrective phases, normalized feedback,
decision/action counts, corrective admissions, ordinary reads/writes, repeated writes,
original/final finish claims and failure reasons. It rejects reordered or missing events,
unexpected oracle events, altered contexts, coercible counters and execution after a
report. Trailing benchmark/experiment audit metadata is excluded from agent accounting.

Every action must match its decision and the original task authorization. Repeated writes
require a corrective phase, a fresh successful read since the preceding write and an
allowed, idempotent tool policy. By default the checker assumes the prototype's allowed,
idempotent `read_issue` and `set_status` policies. For a custom executor, supply its trusted
`policies` mapping explicitly: the trace configuration does not serialize that table.
Policy facts cannot be established from provider assertions or inferred from a denial.

Shared action/decision caps and the corrective admission cap are reconciled separately.
Reported elapsed time can explain a deadline stop, but cannot prove the exact monotonic
deadline or scheduling history. Unknown/incomplete event streams are rejected rather than
treated as successful runs.

Passing establishes unsigned internal consistency, not final-state truth, policy
authenticity or provenance. A success claim based on spoofed ordinary reads can pass this
checker while failing the independent SQL audit. The returned trusted verification calls
and known verified target rows are zero; they do not include a later benchmark oracle.

The 39 focused tests cover real clean/drop/transient traces with admission caps 0/1/2,
counter/context/claim/order corruption, authorization and retry bypasses, custom policy
denials, malformed frames, incomplete traces and elapsed-time limitations. They retain a
spoofed-read false claim and forbid provider/oracle invocation during reconciliation.

The [prospective comparison](REFLECTION_COMPARISON.md) must bind the eventual runner and
this auditor's source hashes before its first trial. The frozen 96-condition execution
is now recorded in the separate [results](REFLECTION_COMPARISON_RESULTS.md).
