# Saved-trace verification work ledger

The [comparator design](COMPARATOR_DESIGN.md) requires accounting for trusted verification
separately from executor actions. `verification_work(events, expected_run_id=...)` in
`veriagent.verification_work` derives a descriptive ledger without rerunning an agent,
opening its state database or changing admission budgets. It adds no CLI mode.
Prospective [admission accounting](VERIFICATION_ADMISSION.md) is separate from this
retrospective ledger. [Agent integration](AGENT_VERIFICATION_ADMISSION.md) is explicit
and leaves default execution unchanged.

## Accepted trace and reconciliation

Input is a list of 1–20,000 events exported from a dedicated single-run TraceStore.
Sequence numbers must be positive integers and consecutive. The task and terminal report
must be present; a second task, duplicate report, unmatched action/observation, mismatched
run identity or execution event after the report is rejected. Post-report
`benchmark_audit` events are permitted but excluded from work counts.

Exported events normally omit run IDs, so the terminal report is checked against the
caller's expected run ID. An explicit event run ID, if present, must also match.
Task, actions, observations, verification and report payloads are schema-validated.
Completed verification evidence must cover exactly the requested targets and agree with
their expected statuses; its pass label must agree with its actual/expected values.
Observation counts reconcile with reported actions, decision contexts with decisions,
and recovery events with recovery admissions. Static plan generation is not a dynamic
decision and remains outside the `decisions` count.

This routine deliberately rejects interleaved multi-run stores or truncated/error-before-
report traces. It does not claim to recover every possible interrupted execution. The
checks establish consistency of the supplied unsigned records, not authenticity or proof
that no event was removed and renumbered.

## Ledger fields

| Field | Meaning |
| --- | --- |
| `tool_actions`, `tool_reads`, `tool_writes` | Observed completed executor actions, matched to their admissions and report |
| `decisions` | Admitted dynamic decision contexts, reconciled with report |
| `recovery_admissions` | Recovery events, reconciled with report; not successful repairs |
| `completed_verification_calls` | Schema-valid completed trusted verification events |
| `verification_errors` | Recorded trusted verification errors |
| `observed_verification_attempts` | Completed calls plus recorded errors |
| `known_verified_target_rows` | Evidence entries from completed calls only |
| `verified_target_rows` | Known count if there were no verification errors, otherwise null |
| `verification_work_complete` | Whether recorded verification attempts have no unknown error-path work |

A verification error may occur after partial database work. The known completed count
is retained, but total target-read work is null even when no check completed. No error
is represented as zero work. Completed evidence rows count logical target queries for
the current verifier; they do not measure transactions, internal SQLite operations,
elapsed time or monetary cost. Setup, final evaluator queries and unobserved failed work
are excluded. Do not add these units to action counts and call the sum total cost.

## Recorded derivation — 2026-11-24

The [derived record](review/verification-work-results.json) binds the comparison record,
ledger implementation and each raw trace with SHA-256. It includes one ledger per
completed run, preserving task/scenario/engine/mode strata. The interrupted OneDrive
attempt is explicitly outside this completed-batch derivation.

All 144 traces reconciled with their terminal reports and original benchmark rows.
Inventory totals are 182 completed verification calls and 284 known target-row reads,
with zero verification errors in these particular runs. These totals inventory work;
they are not pooled task outcomes or an equal-budget comparison.

| Recorded condition | Tool actions | Completed checks | Known target rows | Fault recovery eligible |
| --- | --- | --- | --- | --- |
| Static partial_satisfied / silent_drop / recover | 2 | 1 | 2 | False |
| Dynamic partial_satisfied / silent_drop / recover | 4 | 3 | 6 | True |

The differing exposure and verifier timing preclude interpreting these rows as a causal
resource comparison. Baseline runs with no trusted checks can have zero recorded trusted
work while still performing ordinary tool reads. No new policy caps, reflection arm,
live trial or stochastic inference is introduced by this ledger.
