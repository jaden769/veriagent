# Offline metered reflection boundary and request ledger

Implemented 2026-11-27 as experiment-only primitives in `analysis/metered_reflection.py`.
They implement the first stage of the [provider contract](METERED_REFLECTION_CONTRACT.md),
without transport, provider adapter, engine, metered report, CLI or live activation.
Historical product/research execution sources and their bindings are unchanged.

## Strict payload and limits

ReflectionInput and reflection_payload accept the original Task and ReflectionState,
revalidating nested JSON strictly before producing a detached dictionary. Extra fields,
coercible counters/booleans, excessive feedback and counters beyond shared caps are
rejected. The payload contains only task and the existing observation-only state.
This is a field boundary, not redaction of user-provided goal text or an authorization
decision. The future engine must still authorize every action and enforce retry safety.

MeteredRequestLimits requires explicit max_requests, per-request output allowance,
request timeout and ModelLimits. Request counts/output allowances reject bool/string/
float coercion; nested limits are strict and timeouts finite. Zero requests denies all
dispatches. The 128-token minimum remains existing local policy, not an API minimum.
The ledger requires an explicit model identity and constructs no SDK client.

## Sequential dispatch accounting

MeteredRequestLedger has no network or tool code. The future adapter validates its
payload, then calls admit at the dispatch boundary before invoking transport. admit
checks remaining time, request cap and existing observed-usage limits, returning an
opaque DispatchTicket with bounded timeout/output allowance. The attempt is charged
immediately and is not refunded on failure.

Only one ticket may be pending. Complete or fail it exactly once; stale, forged and
foreign tickets are rejected. Pending work has unknown cumulative usage and charged
calls, while separate known input/output/cost counters preserve settled contributions.
Invalid settlement data leaves the pending attempt intact for explicit failure handling.
No run reset is allowed while a dispatch remains pending.

Complete records available usage once before checking per-request output and cumulative
limits. Missing token usage, overshoot or unknown cost under an active cost limit stops
further admission. Missing cost without a cost limit remains null. Unknown totals do not
become zero; known contributions remain available separately. These are observed-usage
guards and do not guarantee a hard total-token or dollar ceiling.

Fail records one attempted request, using null token/cost values if unavailable. It
retains accounting stop state without raising a secondary budget error over the caller's
provider failure. A known-usage provider failure also latches admission closed. The
caller remains responsible for handling transport exceptions/cancellation and settling
the ticket; these primitives execute no transport automatically.
The injected adapter can now reclassify the latest settled ticket as a provider failure
exactly once, preserving accounting stops without charging usage twice. Bounded caller
stop codes also latch shared-cap and after-response deadline termination.

usage is the current decision snapshot. begin_decision clears it before payload work;
admit also clears it before admission checks. budget_state.usage is cumulative and its
calls equal charged attempts, including pending work. Do not add snapshots to cumulative
totals again. begin_run resets a settled ledger for a fresh run. Returned state snapshots
are detached and cannot mutate ledger accounting.

## Offline checks and remaining gates

Tests cover private-field rejection, strict nested task/budget/feedback fields, detached
state, request/model limits, deadlines, quota/output denial, dispatch charging, ticket
identity and reset guards, unknown/partial usage, failed requests, output/token/cost
overshoot, unknown cost and provider-error precedence. Network socket construction is
blocked in the primitive smoke check. Existing mock provider/report behavior is retained.

This does not complete the eighteen-gate contract. The
[injected adapter](METERED_REFLECTION_PROVIDER.md) now implements the next stage with
fake-transport tests, structured decisions, response validity, canary diagnostics and
after-call/usage checks. A separate
engine/report and saved-trace reconciler follow later. No billable study or live CLI is
enabled by these types.
