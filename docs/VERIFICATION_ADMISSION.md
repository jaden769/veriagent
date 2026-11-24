# Standalone trusted-verification admission semantics

This increment defines and tests logical admission in `veriagent.verification_budget`.
It does **not** connect the ledger to StateVerifier, an agent, Budget or the CLI.
Existing comparison results and execution behavior are unchanged. The
[saved-trace ledger](VERIFICATION_WORK.md) remains retrospective; this ledger is a
prospective reservation mechanism for later integration review.

## Units and limits

`VerificationLimits(max_calls=None, max_target_rows=None)` uses exact nonnegative
integers or None. None means no limit in that dimension; zero denies a positive request.
Boolean, floating-point, string and negative limits are rejected. The default is
accounting-only, with both dimensions unlimited.

One call reservation requests one trusted verification and a positive integer number of
target rows. The caller must derive that number from the original authorized requirements
and invoke a verifier that reads at most those target rows. A limit on logical rows does
not cap database-internal operations, wall-clock time, money or another code path's reads.
The ledger is not an authorization boundary or a thread-safe shared quota.

## State transitions

| State and operation | Result |
| --- | --- |
| Idle, `reserve(rows)` within both remaining limits | Reserve one call and all requested rows; return an opaque-in-use reservation object |
| Idle, request exceeds either remaining limit | Raise `VerificationBudgetExceeded` before mutation; reserve nothing |
| Pending, another reservation | Reject; only one check may be in flight |
| Pending, `complete(ticket, observed_target_rows=rows)` with exact matching rows | Count a completed call and known rows, clear pending; no refund |
| Pending, `fail(ticket)` | Count a verification error, clear pending, retain all reserved allowance |
| Stale/foreign ticket or mismatched completion | Reject without state mutation |

Tickets are accepted by object identity within their issuing ledger. Reusing a completed
ticket or constructing an equal-looking ticket cannot settle a different admission.
After an invalid completion, the original ticket remains pending so the caller can
record failure. The ledger is per run; create a fresh instance rather than resetting
accounting during a run.

Completion means the verifier returned a complete target snapshot, not that the task
passed verification. A complete mismatch consumes the same reserved work as a complete
match. An exception may follow partial work, so failed admissions are never refunded.

## Accounting and unknown work

`reserved_calls` and `reserved_target_rows` determine remaining allowances immediately,
including pending and failed checks. Completed checks contribute to
`known_verified_target_rows`. While a check is pending, or after any error, total
`verified_target_rows` is null and `verification_work_complete` is false. A later success
adds known rows without erasing earlier unknown work. A failed check with no completed
checks therefore has zero **known** rows and an unknown total, rather than zero total.

Example: limits of two calls/four rows admit a two-target check. If it raises after an
unknown amount of work, one call/two rows remain. A second successful two-target check
exhausts the allowance, records two known rows, and still leaves total actual work null.
Reserved rows are a conservative admission quantity, not measured actual error-path reads.

State snapshots are detached dictionaries. No verification content, requirement values,
provider data or raw database rows are stored in this resource ledger.

## Acceptance and integration gates

The acceptance suite covers strict limits/request types, zero/exact-boundary limits,
no partial admission, no refund on error, persistent unknown work, stale/foreign/double
settlement, single in-flight admission and detached snapshots. Existing dynamic-engine
and saved-trace tests are also run for regressions.

Before connecting this to execution, an adapter must prove that it reserves **before**
opening a trusted read transaction, counts the original unique targets, settles every
returned/failed attempt and performs no read on denial. It must keep final evaluator
reads outside the execution allowance and expose denial/accounting in durable traces.
Agent integration must separately define how denial maps to an honest terminal outcome,
how initially satisfied tasks behave, and how default unlimited behavior stays compatible.
No bounded-oracle comparator claim should be made until those gates are tested.
