# Prospective metered reflection-provider contract

Prepared 2026-11-26. Status: **contract specified, not implemented**. The
[machine-readable contract](review/metered-reflection-contract.json) records eighteen
offline gates and baseline source hashes. No provider, report, engine, CLI or live study
is added by this document. No billable call is authorized or executed here.
The subsequent [offline boundary and request ledger](METERED_REFLECTION_BOUNDARY.md)
implement the first stage; the full contract remains pending.
The subsequent [injected adapter](METERED_REFLECTION_PROVIDER.md) is now tested offline;
the separate [controller/report and replay](METERED_REFLECTION_AGENT.md) now provide
initial offline integration. Evidence workflow and live-study gates remain pending.

The [fixed-mock findings](RESEARCH_FINDINGS.md) motivate accounting and stopping contracts,
not a prediction about LLM reflection quality. Current source inspection shows that
ReflectionAgent accepts only the exact MockReflectionProvider and ReflectionReport
requires zero model calls/tokens. Preserve both, existing Mode values and historical
mock runners. Add the metered path as a distinct opt-in implementation.

## Boundary and information access

The proposed MeteredReflectionProvider exposes begin_run(), usage, budget_state,
diagnostic and:

```python
decide(task: Task, state: ReflectionState, *, timeout: float) -> Decision
```

Strictly serialize only the original Task and ReflectionState: phase, up to sixteen
normalized feedback entries, Budget, actions, decisions and corrective_admissions.
Reject extra fields and coercible counters at the boundary. The provider receives no
SQLite path/connection, trusted verification, hidden fault/schedule, eligibility label,
evaluator result, private event log or credentials in its model payload. Ledger/configuration
facts remain local accounting, not hidden oracle feedback.

Each decision is stateless and yields at most one structured Decision, including finish.
Execution and reflection use the same request boundary and shared limits. A phase entry
does not grant a separate free critique request. Preserve phase feedback reset/truncation
and the original-task authorization and fresh-read/idempotent repeated-write guards.
No remote conversation or private reasoning replay is required or stored.

Do not cast ReflectionState into the existing dynamic DecisionState, which can carry
trusted verification. Reuse transport/parsing/accounting helpers only behind the narrower
payload contract. Exactly one permitted action or finish must validate; multiple calls,
unknown tools, malformed output or unauthorized targets/statuses cannot execute.

## Request and usage accounting

Require an explicit model identity, finite exact-integer max_requests (zero denies all),
finite per-request output allowance and bounded request timeout. The existing ledger's
128-token minimum is local admission policy, not an API minimum. No model, fallback,
retry or live activation is selected by this contract.

Before dispatch, validate payload, remaining shared decision/time caps, request allowance
and existing ModelLimits. Timeout is the lesser of configured request timeout and positive
remaining run time. Charge one attempt at the dispatch boundary before calling transport;
a timeout/transport error consumes it and is not refunded. This records attempted dispatch,
not proof of server receipt. No automatic SDK/application retry or fallback is allowed.
One decide call can dispatch at most once; both phases share the same per-run counters.

begin_run resets usage, attempts, diagnostics and budget state. usage is the current
decide-call snapshot: zero calls before dispatch, one after attempted dispatch, including
errors. budget_state.usage is cumulative. Reports consume cumulative totals and do not
re-add snapshots. Record available response usage exactly once before completion/output
validation, including refusals, incomplete responses and malformed decisions. Missing
input/output usage remains null; a failed request is never fabricated as free zero usage.
Preserve configured model identity and available served-model identity without inventing
one when absent or mixed.

Unknown token usage halts further dispatch and tool execution. Unknown estimated cost
also halts when a cost limit is active; without a cost limit it stays null. Preserve
known completed usage alongside unknown work. Known token/output/cost overshoot is charged
and stops before acting on the returned decision. These are observed-usage stop rules:
total tokens/cost can overshoot after a response, input work can be unknown and there is
no hard global dollar cap. Do not advertise exact cost reservation or cost parity.

## Report, failures and traces

Propose a separate MeteredReflectionReport with comparator llm_self_reflection and its
own schema identity; do not relax the mock report's zero-usage constraints. Keep original
and final claims, verified_success null, action/decision/phase/write/repeat counters,
failure/time, request_attempts, cumulative ModelUsage/ModelBudgetState and sanitized
ProviderDiagnostic. Trusted verification calls/rows remain zero for the policy; final
benchmark SQL audit is separate and occurs after termination.
Cumulative ModelUsage.calls must equal charged request_attempts. Derived token totals
remain null if any constituent token usage is unknown.

| Trigger | Terminal behavior |
| --- | --- |
| Preflight request/model/shared cap or elapsed deadline | Budget failure; no dispatch or action after denial |
| Returned usage exceeds a limit, or accounting becomes unknown | Budget failure with retained known/unknown work; no returned action/finish accepted |
| Transport error, refusal, incomplete or invalid output | Planning failure and sanitized diagnostic; preserve request failure as primary even if its usage is unknown |
| Valid response arrives after remaining deadline | Budget failure; no late action or finish accepted |
| Unauthorized or unsafe repeated write | Permission failure; no tool dispatch |
| Valid final finish within all limits | Final success claim only; independent target truth remains separate |

After any terminal error, do not preserve a stale positive final claim. Original claims
remain diagnostic history. Unknown-usage budget-stop state can coexist with a primary
transport/planning failure; record both without replacing the primary failure.
When provider/output validity and accounting both fail, preserve the provider/planning
failure and retain the accounting stop as secondary state. A completed valid reply with
only unknown/overshooting accounting instead ends with budget failure. Test this precedence
explicitly rather than inheriting it accidentally from helper call order.

Trace configuration identifies the metered comparator, public model/limits and prompt/
schema identity. Persist bounded normalized context, phases, decisions, request-attempt
and usage/accounting events, denials and terminal native report. Reconcile request counts,
usage unknowns, counters and claims offline without provider/tool/oracle execution. Keep
stopping flags distinct from exact timing or a unique causal diagnosis.

Use the existing sanitized diagnostic boundary as a baseline. Do not save API keys,
headers, raw SDK exceptions/bodies or private reasoning. Public bounded configuration and
normalized task/feedback are sufficient for this contract; fake secret canaries test the
boundary without reading real credentials.

## Offline gates before any live wiring

All tests inject fake transports and fail if a real client/network dispatch is constructed.
Cover normal execute/reflect/finish, shared phase ledgers, reused-run reset, request cap
zero/exhaustion, deadline/output allowance denial, failed dispatch charging, refusals,
malformed/multiple/unknown decisions, missing/partial usage, known overshoot, unknown cost,
late replies, unauthorized/unsafe writes and sanitized canary errors. Verify that blocked
responses produce no tool action and saved trace/report usage is reconciled exactly once.

Implementation sequence:

1. Strict boundary/request-accounting types and offline tests.
2. Injected adapter using compatible existing helpers, with fake-transport tests.
3. Separate metered engine/report and saved-trace reconciler, preserving historical mocks.
4. Separate prospective live study/configuration and spending/accounting review.

No new live CLI command or paid trial belongs in the first three gates. Historical plan
and evidence fingerprints remain immutable; future studies must pin changed implementation
sources explicitly. External corpus/fault review, stochastic design and broad reliability/
causal/equal-cost claims remain outside this provider contract.
