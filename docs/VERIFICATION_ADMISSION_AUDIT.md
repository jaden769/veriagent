# Offline verification-admission trace reconciliation

`reconcile_verification_admission(events, expected_run_id=...)` in
`veriagent.verification_admission_audit` replays the
[opt-in agent trace contract](AGENT_VERIFICATION_ADMISSION.md). It opens no state database,
executes no oracle/tool, changes no ledger used by a live agent and adds no CLI command.
Its replay ledger is private to the reconciliation call.

Use complete events from a dedicated single-run TraceStore, as required by the
[verification-work ledger](VERIFICATION_WORK.md). Ordinary traces without opt-in limits
are rejected by this reconciler; the existing work ledger still supports them.

## Checks

- Require one original task, one early opt-in configuration and a terminal report with
  the expected run ID. Match report engine/mode against configuration.
- First reconcile ordinary action/observation, decision, recovery and verification work.
- Recreate strict call/row limits and replay each reservation, completion, error or denial.
  Requests must count exactly the original targets.
- Require each recorded state to match replay, including remaining allowance, pending,
  known completed rows and null total work after errors. Comparisons distinguish booleans,
  integers and floating-point equivalents rather than using permissive Python equality.
- Pair completion/error/denial immediately with `verification`, `verification_error` or
  `verification_denied`. Reject missing, extra or unsettled phases and mismatched reasons.
- Denial must be inadmissible under the configured limits and must leave no new reservation.
  Execution cannot continue after denial or admitted verifier error.
- Reconcile final call/error/known-row counters with observed verification events.
  Baseline cannot request trusted verification. Protected success requires completed
  positive evidence; report verification and verified-success fields must agree.
- Require denial to end in budget failure without a claim or stale verification. An
  admitted verification error must end in internal failure without a success claim.

The result uses schema version 1 and scope
`opt_in_verification_admission_trace_consistency`, with `admission_passed`,
`denied_verifications`, `final_state` and the descriptive `verification_work` ledger.
Inconsistency raises a validation error rather than producing accepted totals.

`admission_passed: true` means the supplied records are internally consistent. A correctly
recorded budget failure passes reconciliation; it does not mean the task passed or the
quota was sufficient. Unknown partial error work remains null. Setup and final evaluator
queries remain outside these execution counters.

## Coverage and limits

Tests replay actual traces from both engines, all three modes, unlimited limits, zero
call allowance and a one-row allowance, comparing replay against the live ledger.
Admitted errors retain unknown work. Corruption cases alter counters/types, target counts,
limits, phases, reasons, terminal claims and event ordering, including removal followed
by sequence renumbering so rejection does not rely only on sequence gaps.

These are unsigned consistency checks, not authenticated provenance or a fresh task-state
audit. A wholly rewritten, self-consistent trace is not excluded by replay alone. The
reconciler does not establish total SQLite work, cost parity, fault-exposure equality or
causal policy effects. Dedicated bounded-oracle comparison plans and external research
review remain separate gates.
