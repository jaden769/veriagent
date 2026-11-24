# Opt-in trusted-verifier admission adapter

`BudgetedStateVerifier` in `veriagent.bounded_verification` wraps the existing trusted
StateVerifier with the [standalone admission ledger](VERIFICATION_ADMISSION.md).
It is an explicit Python adapter, not an enabled agent policy or CLI feature.

```python
from pathlib import Path
from veriagent.bounded_verification import BudgetedStateVerifier
from veriagent.verification_budget import VerificationBudgetLedger, VerificationLimits

ledger = VerificationBudgetLedger(VerificationLimits(max_calls=2, max_target_rows=4))
verifier = BudgetedStateVerifier(Path("state.sqlite"), ledger)
# result = verifier.verify(original_validated_task)
# Inspect ledger.state separately from result.passed.
```

The caller supplies the original validated task. The adapter counts its unique requested
targets and reserves the complete check before delegating to StateVerifier. If either
limit denies admission, `VerificationBudgetExceeded` propagates before any SQLite
connection opens and no allowance is consumed. Construction resolves the path but does
not open the database. Read-only URI behavior and the verifier's single-snapshot semantics
are inherited unchanged.

A returned full snapshot consumes the reservation even when targets mismatch, a target
is missing, or the task was already satisfied. Returned evidence must cover the original
targets and expected statuses, with a consistent pass label. An exception, cancellation
or incomplete/inconsistent return settles the reservation as an error and propagates.
No refund occurs and actual partial target-read work remains unknown. No success result
is invented and denial never becomes an empty verification.

The ledger is sequential, per execution run and not a shared/thread-safe security quota.
It limits logical calls and requested target queries, not SQLite-internal work, latency
or money. Ordinary tool reads are outside it. Use an independent ordinary StateVerifier
or final evaluator for post-run outcomes; consuming an execution allowance must not
prevent measurement of a failed/denied run.

## Evidence and remaining gate

Connection spies confirm no SQLite connection on call/row denial, read-only URIs on
admitted checks and the query count at exact limits. A real two-target database with an
invalid second status exercises an error after target reads: reserved work stays consumed,
known completed rows stay zero and actual total rows stay null. Missing-file, missing-target,
satisfied-target, incomplete-return, exception and cancellation paths are covered separately.
Ordinary final verification remains available after execution denial.

Agents and CLI still use ordinary StateVerifier by default. Explicitly supplying this
adapter to Agent or DynamicAgent now enables run binding, durable admission events and
budget-denial handling. See [opt-in agent integration](AGENT_VERIFICATION_ADMISSION.md).
No CLI flags or reflection arm are added.
