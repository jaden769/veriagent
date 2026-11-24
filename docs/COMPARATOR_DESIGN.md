# Prospective comparator and ablation design

Prepared 2026-11-21. Design only: no new comparator, budget guard, fault profile or study
is implemented by this document. It follows the [recorded mock comparison](OFFLINE_COMPARISON_RESULTS.md)
and [research review packet](RESEARCH_REVIEW.md). External review remains pending.

## What the recorded comparison cannot distinguish

Static `partial_satisfied` one-shot faults were consumed by an already-satisfied write;
dynamic execution exposed an unfinished target instead. Thus identical configured fault
labels did not provide identical realized challenges. Separately, trusted verification
uses direct SQLite reads outside `actions`; static verification follows a plan pass,
while dynamic protected modes also verify initially and after actions. Equal action and
decision caps therefore do not establish equal information or resource access.

Retain the existing comparison as descriptive mechanism evidence. Do not relabel its
mode differences as causal policy effects or as a self-reflection comparison.

## Comparator definitions

Use the dynamic engine as the initial design target; keep static results separate.
All arms receive the same fixed requirements, ordinary tool authorization and fresh
initial state. The final evaluator runs only after the arm stops and never returns
feedback to any arm.

| Arm | Trusted verifier feedback | Corrective actions | Status |
| --- | --- | --- | --- |
| Baseline | None | Existing baseline stopping/replay policy | Implemented `baseline` |
| Verify | Initial and subsequent trusted checks | No recovery admission after detected mismatch | Implemented `verify` |
| Recover | Initial and subsequent trusted checks | Existing bounded, authorized recovery policy | Implemented `recover` |
| Self-reflection candidate | None | Proposed bounded reflection and corrective phase using ordinary observations | Missing |

The self-reflection candidate would use typed tool observations and its own earlier
decisions, with the same authorized `read_issue`/`set_status` surface. Ordinary reads
consume action and decision allowances. It receives no StateVerifier result, SQLite
connection, hidden schedule, eligibility label, final evaluator result or private
application-event log. This permits observation-based checking without granting trusted
oracle access; reflection text alone is not independent verification.

Before implementation, define a typed phase transition from ordinary execution to
reflection after a finish proposal or failed tool result. Each reflection generation
must consume a decision and the same model-output ledger as ordinary generation.
Permit at most two corrective-phase admissions under the initial eight-action/eight-
decision envelope, stop at any exhausted limit, and preserve the original claim and
final claim separately. All proposed writes still require task authorization and retry
safety checks. A reflection admission is not automatically a write retry or a successful
repair; report these separately. These proposed semantics require review and tests and
must not be represented as an existing CLI mode.

## Resource accounting before ablations

Record a vector rather than calling action count total cost:

| Quantity | Definition and evidence | Current limit |
| --- | --- | --- |
| Tool actions | Admitted executor actions; distinguish reads/writes from observations | Existing action cap |
| Decisions | Provider decisions, including future reflection calls | Existing dynamic decision cap |
| Verification calls | Completed trusted verification events, separately count errors | Not an independently capped resource |
| Verified target rows | Sum evidence entries in completed verification events | No independent cap; not elapsed time |
| Recovery admissions | Recovery-policy admissions; distinguish writes and repaired outcomes | Existing retry cap |
| Model usage | Known calls/tokens plus unknown usage and configured output allowances | Existing model-budget semantics |
| Time | Agent-loop time, separate from setup and final evaluator | Cooperative run/action deadlines |

A completed StateVerifier call currently reads each required target in one read-only
transaction. Evidence-entry counts describe target-row queries for completed calls;
verification errors can include partial work that cannot be reconstructed from the
completed evidence alone. Never report unknown error-path work as zero. Tool actions and
trusted target-row reads are different units; adding them with arbitrary weights does
not establish dollar or latency parity.

A read-only trace spot-check of the recorded `partial_satisfied/silent_drop/recover`
condition found one completed verification/two evidence rows/two tool actions for static,
and three completed verifications/six evidence rows/four tool actions for dynamic.
The static run was fault-recovery-ineligible and the dynamic run eligible. This example
motivates separate accounting; it is not an equal-exposure cost comparison.

First derive the completed-call ledger from saved traces without changing agent behavior.
The [saved-trace ledger](VERIFICATION_WORK.md) now provides that descriptive derivation;
its error-path work remains unknown rather than assumed zero.
The [standalone admission specification](VERIFICATION_ADMISSION.md) defines reservation
semantics and acceptance tests. The [explicit adapter](BOUNDED_VERIFICATION.md) adds
pre-read admission, and [explicit agent integration](AGENT_VERIFICATION_ADMISSION.md)
provides budget-denial outcomes and durable state. Comparator experiments remain pending.
Then specify and test any new admission caps before using them as experimental controls.
Post-hoc truncation or regression adjustment does not retroactively equalize budgets.

## Planned ablations and their limits

| Contrast | Intended question | Required control or unresolved issue |
| --- | --- | --- |
| Verify versus recover | Does permitted repair improve outcomes after checking? | Match oracle access and report additional actions, decisions and admissions |
| Baseline versus self-reflection | Does an observation-based corrective phase help? | Match total decision/output/action ceilings; define phase admission and stopping |
| Self-reflection versus recover | What changes with trusted external evidence? | Align corrective opportunities and cap/report ordinary reads versus oracle work |
| Shared-cap versus tighter recover caps | Are gains dependent on extra work? | Predeclare cap grid; include all cells and exhausted-budget failures |
| Initial verification on/off | Does early satisfaction detection change work/exposure? | A new policy variant; retain separate identity and full exposure records |

These contrasts are proposals, not implemented ablations. Shared ceilings remain only
one control: different policies can use different fractions and kinds of their budget.
Do not choose a cap grid after seeing which cells favor recovery. Static plan-generation
counts and dynamic decision counts also require separate accounting.

## Exposure and analysis rules

Keep all assigned task/scenario/arm runs in the primary comparison, including unused
faults, already-satisfied goals, timeouts and honest failures. Report target satisfaction,
false claims and collateral changes separately. Compare realized write targets, pre-fault
statuses, injected events, unused schedules and recovery eligibility as diagnostics.
Eligibility is affected by the policy, so restricting analysis to eligible runs is a
post-treatment selection; conditional recovery rates are descriptive, not causal effects.

Preserve current attempt-indexed profiles unchanged. If a later experiment needs a
fault on the first *changing authorized write*, implement it as a separately named and
versioned profile, with tests for no-op writes and no qualifying write. Such a profile
still cannot force equal exposure if an arm never makes a changing write. Do not silently
shift existing scheduled faults or feed hidden exposure labels to a provider.

For any stochastic study, predeclare task/condition blocks, arm ordering, model settings,
sample-size rationale, interruptions, exclusions and uncertainty method. Correlated calls
and one deterministic run per cell do not justify a paired significance or causal claim.
No live study, sample size or billable execution is established by this design.

## Implementation gates

The [prospective bounded-oracle check](BOUNDED_ORACLE_COMPARISON.md) now pins a small
mock-only admission comparison. Its expected outcomes are not measured results.

1. Reconcile the verification-work ledger against saved static and dynamic traces,
   preserving missing/error information explicitly.
2. Review self-reflection observations, typed phase transitions, accounting and admission
   limits; add deterministic tests before implementing an arm.
3. Pin approved comparator/profile identities, exact cap grid and primary analysis before
   collecting new comparison outcomes.
4. Complete external corpus/fault review and a prospective study/spending plan before
   interpreting any future live comparison as reliability evidence.
