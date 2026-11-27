# Injected metered controller, report and trace replay

Implemented 2026-11-27 in `analysis/metered_reflection_agent.py` and
`analysis/metered_reflection_trace.py`, using the [injected adapter](METERED_REFLECTION_PROVIDER.md).
No SDK factory, live CLI, new Mode, paid study or historical mock-engine change was added.

## Native execution and reporting

MeteredReflectionAgent requires an explicit injected provider, Executor and TraceStore;
it has no verifier argument. A run resets settled provider accounting and receives a new
run ID. Execute/reflect phases, feedback windows, shared action/decision/time caps and
at most two corrective admissions follow the mock prototype. Writes retain original-task
authorization and fresh-read/idempotent retry guards.

Provider budget failures remain budget failures; unauthorized proposals remain permission
failures; sanitized provider errors remain planning failures. Every provider decision has
a metered_decision_accounting event with detached before/after request state, outcome,
effective dispatch timeout/output allowance and sanitized diagnostic. No SDK response,
private reasoning or credential is included. Both phases share the same request ledger.

MeteredReflectionReport is a distinct type with comparator llm_self_reflection. The mock
report's zero-usage constraints remain unchanged. The new report retains original/final
claims, verified_success null, tool/decision/corrective/write counters, failure/time,
charged attempts, cumulative usage/budget state, detached request state and diagnostic.
Counts/usage must agree; a terminal report cannot contain pending work, and a positive
finish requires accounted usage. Fixture usage is not measured API billing.

Unknown usage stays null. Request denial, overshoot and late replies stop before an action
or finish can be accepted. A provider can still make a false completion claim; final SQL
truth remains separate. A test deliberately retains such a claim with an unsatisfied goal.

Cancellation settles pending work and persists accounting before propagating, leaving a
partial trace without a fabricated report. It cannot pass the complete-run reconciler.
Reused settled controllers reset counters; sequential TraceStore reuse permits a positive
starting sequence followed by consecutive events.

## Offline reconciliation

reconcile_metered_trace(events, expected_run_id=..., policies=...) consumes a bounded
complete native trace without provider, tool or oracle execution. It checks ordering,
strict public configuration/limits/prices, snapshots, at most one dispatch per decision,
effective timeout/output allowance, estimated-cost arithmetic and usage/error/stop balances.
Diagnostic excerpts are rejected. Native failure mapping, report accounting and final
diagnostic must agree. Malformed nested frames produce a bounded generic error.

After native metering checks, a detached mock-format projection lets the existing phase
checker validate contexts, transitions, claims, authorization, retries and tool counters.
Request-level budget/permission errors are normalized only inside this phase projection;
the real native mapping is checked separately and remains in the original report.
Projected zero model usage is never a metered result. Replay returns actual request/token
totals and zero trusted policy checks.

Supply trusted custom executor policies when they differ from the allowed/idempotent
defaults. Replay does not authenticate policies, transport receipt, billing identity,
exact deadlines or final-state truth. Timing/usage are trace assertions, not reenacted
network calls. Interleaved parallel runs in one sequence stream are not supported.

## Checks and remaining work

Fake transports cover clean/drop/persistent/transient tasks, quota exhaustion, transport,
malformed/unknown-usage/permission errors, resets, overshoot, late replies, non-idempotent
repeat denial and cancellation. Corruption tests alter snapshots, usage, claims, counters,
timeouts, contexts, diagnostics, failures and event coverage. Provider/tool/oracle methods
are blocked during replay. No billable calls were made.

Next is a bounded fake-transport evidence smoke workflow exporting native reports/traces
and independently replaying them. Live wiring/study design and external review remain
pending. This establishes no LLM-quality, stochastic, causal, equal-information or dollar-
cost conclusion.
