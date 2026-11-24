# Prospective bounded-oracle mechanism check

Prepared 2026-11-24. Status at preparation: **specified, not run**. The
[plan JSON](review/bounded-oracle-plan.json) pins current Python source hashes, corpus,
selections, budgets and all 72 expected condition outcomes. It is a new specification;
historical baseline hashes and earlier comparison plans remain unchanged.

Subsequent execution is recorded in [the outcome report](BOUNDED_ORACLE_RESULTS.md).
The prospective plan JSON remains unchanged; predictions and observations are separate.

## Selection and purpose

Use only DynamicAgent with MockProvider and fixed corpus tasks `single_done`,
`already_satisfied` and `partial_satisfied`. Cross clean/one silent-drop scenarios with
baseline/verify/recover modes and four trusted-verification quota profiles, one repetition
per cell: 3 × 2 × 3 × 4 = 72 planned runs.

| Profile | Call cap | Target-row cap | Intended boundary |
| --- | --- | --- | --- |
| `zero_calls` | 0 | Unlimited | Initial protected check denied before any tool/oracle work |
| `one_call` | 1 | Unlimited | Initial snapshot available; subsequent protected check denied |
| `one_row` | Unlimited | 1 | One-target snapshot available; two-target snapshot denied atomically |
| `unlimited` | Unlimited | Unlimited | Existing verification policy with explicit accounting |

Each run uses fresh sandbox, mock provider, budgeted adapter, ledger and dedicated
TraceStore. Seed complete statuses from the pinned corpus, with initial versions zero.
Use the existing ScheduledSandbox clean/silent-drop definitions so realized fault targets,
pre-fault status and eligibility remain observable. Do not change or shift a fault schedule
because a quota prevents its delivery.

Execution caps are eight tool actions, eight dynamic decisions, two recovery admissions,
a 60-second cooperative run deadline and one-second action timeout. No model/API provider
is selected, and no new CLI flag or browser backend is proposed. The [repository-local runner](../research/run_bounded_oracle.py) implements this
specification; `benchmark` has no verification-quota parameter, so these are not product
benchmark CLI options.

## Expected boundaries, fixed before outcomes

Baseline never requests trusted verification and therefore behaves identically across
quota profiles. Keep its false-claim controls: zero oracle allowance must not be mistaken
for baseline detection or protection.

Protected modes with zero calls deny initially, even for an already-satisfied task.
For the two-target partial-satisfied task, one row cannot admit the initial two-row
snapshot; no partial oracle access is permitted. Those denials precede tool actions.

An already-satisfied one-target task can finish after its first admitted check under all
nonzero profiles. Other protected tasks with only one call, or only one row for a
one-target task, deny the next check after the first write. In clean conditions that
write may already satisfy the final goal; the agent must still report budget failure
without a verified claim. A one-shot dropped write instead leaves the target unmet,
with the same honest denial outcome. Do not label either as a verifier exception.

Unlimited protected runs retain the recorded clean/silent-drop mechanism behavior:
verify detects the unmet dropped write and recover can repair it within the existing
caps. Already-satisfied success is not recovery. Per-cell predicted denial phase, reason,
final target success, claim, failure and verified-success values are stored in the JSON.
The predicted inventory contains 28 denied runs; this is a planned check, not a result.

## Measurements and acceptance

Retain assigned conditions regardless of outcomes. Record requested quota, tool actions,
decisions, recovery admissions, live ledger state, realized write attempts/faults,
independent target satisfaction and untargeted status/version changes. Preserve original
agent claims and failure fields separately from the final SQL audit. Avoid pooled policy
success rates; each cell is one deterministic observation.

After each run, export the trace and run the
[admission reconciler](VERIFICATION_ADMISSION_AUDIT.md). Its replayed final state must equal
the live ledger. A correctly recorded denial is accepted evidence of budget failure, not
a failed audit. Admitted errors must retain unknown partial work and remain visible.

Completion requires exact condition coverage, unique run identities, original source/
corpus/budget matches, expected per-cell boundaries, independent final-state queries,
reconciled admission events and no silently removed runs. Record trace/result hashes and
separate planned values from actual measurements. An unexpected mismatch is a finding:
preserve it and revise any explanation openly rather than changing these expectations.

Use a new UUID artifact tree under the approved writable local artifact root to avoid
the earlier OneDrive replacement failure. Preserve partial attempts, errors and any
output-path amendment. Do not silently restart or replace runs in the analysis.

## Claim boundary and next step

This tests logical quota boundaries and honest reporting. It does not equate verifier
reads with ordinary tool actions, enforce total SQLite cost, guarantee deadline timing,
equalize realized fault exposure or establish causal/stochastic reliability. Self-reflection,
budget-controlled policy ablations and independent external review remain pending.

Execution with raw evidence retention and admission reconciliation is now recorded in
the linked outcome report. No trial was executed when the original plan was prepared.
