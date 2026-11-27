# Injected metered reflection adapter

Implemented 2026-11-27 in `analysis/metered_reflection_provider.py`, using the
[strict boundary/request ledger](METERED_REFLECTION_BOUNDARY.md). This is the adapter
stage of the [contract](METERED_REFLECTION_CONTRACT.md). No metered engine/report,
saved-trace integration, SDK factory or live CLI was added. All validation used fakes.

## Injected boundary

MeteredReflectionProvider requires an explicit model, MeteredRequestLimits and callable
transport; it optionally accepts a monotonic clock and paired caller-supplied token
prices. An active estimated-cost limit requires both prices. The adapter reads no
credentials and constructs no client. The transport receives a single request with
bounded timeout/output allowance, no stored conversation and no parallel tool selection.

Injection is not a network sandbox: a supplied callable is invoked. Future live wiring
must provide a single-attempt transport with retries disabled and bounded timeout;
the adapter cannot prove a delegate's internal behavior or server receipt. There is
no automatic retry or fallback in this adapter, and no billable run was performed here.

The request contains only the strictly validated original Task and ReflectionState.
Instructions explicitly deny trusted-verifier access and treat observations as untrusted
data. It reuses the existing function schemas/parser with an observation-only finish
description. It rejects malformed/duplicate argument keys, oversized arguments, multiple
or unknown calls and unsupported/refused output. Optional reasoning items are ignored;
private reasoning and raw response bodies are not persisted.

Authorized reads, writes and finish proposals return a Decision. Original-task target/
status authorization is checked before returning an action. The future engine must still
enforce executor policy, fresh-read/idempotence retry guards and actual tool execution.
This adapter executes no tool or trusted oracle.

## Accounting and failure ordering

Every attempted transport dispatch is charged once. Available response usage is strictly
validated and settled before response/decision validation. Missing usage fields stay null;
malformed numeric metadata cannot become free zero usage. Configured and available served
model identities remain distinct. Cost estimates use explicit prices, not a price lookup
or billing guarantee.

If accounting stops but the response is also refused, incomplete or invalid, preserve the
provider/planning failure with its accounting stop as secondary state. The ledger's new
mark_provider_failure(ticket) reclassifies the latest settled request exactly once without
recording usage again. Unknown, stale or duplicate classifications are rejected. Transport
errors and cancellation settle failed attempts before propagating the primary outcome.

A valid decision with unknown or overshooting usage raises the budget stop before it can
be returned. After-call deadline checks also reject late actions or finish claims and
close admission. Shared action/decision caps are checked before dispatch. No phase receives
free requests; usage/budget state is shared across execute and reflect calls, and begin_run
resets only a settled run.

Public provider errors are generic. Diagnostics retain allowlisted categories/status/
code/parameter fields and discard response excerpts/body-format details. HTTP, timeout
and connection canaries do not appear in emitted errors or diagnostics. No SDK error body,
headers or credentials are saved by this adapter.

## Offline validation and remaining work

Fake transports cover execute/reflect, valid reads/writes/finish, malformed/duplicate/
multiple/unknown output, refusals/incomplete status, missing/invalid usage, known overshoot,
unknown accounting, request errors/cancellation, unauthorized targets/statuses, quota/
deadline/shared-cap denial, late finish, price requirements and sanitized HTTP errors.
Ledger tests cover exactly-once reclassification and bounded caller stop reasons.

The mock-only ReflectionAgent exact-type gate and its zero-usage ReflectionReport are
unchanged: the new provider is not wired into that engine. Next is a separate metered
controller/report and offline saved-trace reconciler, with fake-transport integration
tests. No live study, default model, paid execution or broad LLM-quality result is enabled
or established by this increment.
