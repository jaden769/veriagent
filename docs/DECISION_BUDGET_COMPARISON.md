# Prospective mock decision-budget sensitivity study

Prepared 2026-11-26 as a prospective specification. The subsequent
[results](DECISION_BUDGET_RESULTS.md) record execution separately. The
[machine-readable plan](review/decision-budget-plan.json) pins all 288 ordered conditions,
product source/corpus hashes and the prior results that motivated this follow-up.
The subsequent [mock runner and execution lock](DECISION_BUDGET_RUNNER.md) implement
the pretrial gates; the published plan bytes remain unchanged.

The [96-run study](REFLECTION_COMPARISON_RESULTS.md) observed five reflection runs with
satisfied final goals and budget failures. All used eight decisions; pair_done/transient
and mixed_status/transient also used all eight actions. The other three used seven
actions. This motivates a decision-cap sensitivity check, without assuming that additional
decisions resolve action-cap stops. The new design is informed by those results, not an
independent confirmation of an unobserved hypothesis.

## Assigned conditions and intervention

| Dimension | Selection |
| --- | --- |
| Tasks | All six original corpus tasks |
| Scenarios | clean, silent_drop, persistent_drop, transient |
| Arms | Dynamic baseline, verify, recover; separate mock self-reflection |
| Varied resource | Decision cap: 4, 8, 12 |
| Fixed caps | 8 actions, 2 retry/corrective admissions, 60-second run, 1-second action |
| Repetitions | One fresh run per cell; 288 assigned runs |

Retain existing provider rules and information access. Dynamic arms use fresh unlimited
trusted-verification ledgers; baseline makes no trusted calls. Reflection receives no
trusted verifier or quota object and keeps its two-phase-admission maximum, repeated-write
guard and ordinary-read costs. Preserve native RunReport/ReflectionReport contracts.
Finish decisions, read-back and confirmation consume their existing resources. Do not add
free finishing work after the action cap or change stopping semantics for this study.

Each of the 24 task/scenario blocks contains all three caps and all four arms. Rotate
cap order by zero-based block index modulo three. Within each cap group, rotate arm order
by `(block_index + cap_position - 1) modulo 4`, where cap_position is one-based.
Each cap occupies each group position in eight blocks; within each cap, each arm occupies
each arm position six times. Ordering is balanced and fixed, not randomized.

Every cell gets fresh state, provider, policy, executor, trace store and applicable ledger.
Execute the cap-eight cells anew; do not substitute or pool the previous 96 outcomes.
Use the unchanged default fault profiles, including max_actions-based persistent drops.
Do not shift an unused fault, replace a no-op target or expose evaluator metadata to a policy.

## Outcomes and descriptive contrasts

Primary outcomes are independent final target-status satisfaction and achieved-goal budget
failure (`ground_truth_success` and terminal `failure == budget`). Report these separately,
using all 24 assigned task/scenario cells per arm/cap. A whole-cap denominator is 96.
Retain final claims, false success, untargeted status/version changes and original reflection
claims as separate secondary outcomes. Target titles remain outside this SQL oracle.

Show condition-level cap-12 minus cap-8 and cap-8 minus cap-4 changes within each arm,
task and scenario. Summarize counts of improved, unchanged and worsened goal outcomes and
achieved-goal budget failures without imposing a ranking or pass threshold. Cap-eight
agreement with the earlier study is a descriptive stability check; disagreement is retained.
Missing/partial outcomes remain unknown, never imputed as failure or success. Any incomplete
coverage must be reported against the assigned denominator and cannot be labeled complete.

Keep the resource vector: actions, decisions, ordinary reads/writes, trusted calls/known
logical target rows, recovery/corrective admissions, available repeat-write counters,
model calls/tokens and elapsed time. Preserve realized attempts, pre-fault status, unused
faults and recovery eligibility. Exposure-conditioned summaries remain diagnostic, not
the primary contrast; exposure depends on policy and cap.

For each stop, record whether action, decision or corrective counters reached their caps,
plus terminal failure and reported elapsed/deadline status. Multiple caps can be reached
together. Reconcile counter flags with traces and do not infer a unique causal stop from
an exhausted counter alone. Reported elapsed time does not prove exact scheduling.

## Gates before execution and interpretation

Implement an explicit mock-only runner that validates the complete plan and all input
pins before creating output or providers. Bind its source, the plan and relevant auditors
in a new execution lock before the first trial. Preserve the original plan and historical
locks/results. Retain completed trials and active partial files on interruption; stop
without automatic retry, resume or replacement. Unexpected task outcomes are findings,
while a harness/audit exception stops the attempt and leaves the active outcome unknown.

Require exact 288-cell ordered coverage, unique identities, native report/trace agreement,
dynamic live-ledger/admission replay agreement, reflection phase replay, resource/stop
diagnostics and the same independent post-policy SQL audit across arms. No evaluator
feedback reaches a policy. Preserve raw reports, states, traces and hashes for later review.

This varies only the decision cap. Action/admission ceilings can still bind; trusted
checks remain outside ordinary action counts. It does not equalize information, total
database work, token cost or dollars. One deterministic observation per cell supplies no
stochastic confidence, paired significance, causal verification effect or LLM-quality
claim. External review, metered models and broader resource ablations remain pending.
