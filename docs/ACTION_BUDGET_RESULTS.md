# Recorded mock action-budget sensitivity

Recorded 2026-11-26 against the unchanged [prospective plan](ACTION_BUDGET_COMPARISON.md)
and [pretrial execution lock](review/action-budget-execution-lock.json). One attempt
completed all 288 ordered assignments with unique run IDs. All independent native trace,
resource, configured-fault, stopping and final SQL rechecks passed. No partial attempt
was created for this study.

## Assigned outcomes

Counts below are at action caps **8 / 10 / 12**, each out of 24 assigned task/scenario
cells per arm. Decisions stayed at twelve and retry/corrective admissions at two.

| Arm | Final goals met | Final success claims | False success claims | Achieved-goal budget failures |
| --- | --- | --- | --- | --- |
| Dynamic baseline | 9 / 9 / 9 | 19 / 19 / 19 | 10 / 10 / 10 | 0 / 0 / 0 |
| Dynamic verify | 9 / 9 / 9 | 9 / 9 / 9 | 0 / 0 / 0 | 0 / 0 / 0 |
| Dynamic recover | 19 / 19 / 19 | 19 / 19 / 19 | 0 / 0 / 0 | 0 / 0 / 0 |
| Mock self-reflection | 19 / 19 / 19 | 15 / 19 / 19 | 0 / 0 / 0 | 4 / 0 / 0 |

Final goal satisfaction did not change at any action cap in any arm. At ten versus eight
actions, reflection changed its final claim from false to true in pair_done and mixed_status
under silent_drop/transient. These four achieved-goal budget failures disappeared while
their already-satisfied SQL outcomes stayed true. At twelve versus ten actions, no final
claim, goal or achieved-goal budget outcome changed.

Reflection retained five unsatisfied persistent-drop budget failures at every cap.
At cap eight it additionally had the four achieved-goal budget failures above. No
untargeted status/version changes were observed. Target title preservation is outside
this oracle. All mock model calls/tokens were zero.

The [machine-readable record](review/action-budget-results.json) retains all 288 audited
conditions and 288 matched descriptive contrasts: 12-minus-10, 10-minus-8 and 12-minus-8
within each arm/task/scenario. It includes native report-derived outcomes, configured and
unused faults, realized exposure, resources, stop flags and per-file hashes. All assigned
cells remain in the primary denominators; eligibility-conditioned analysis is diagnostic.

## Work and fixed fault configuration

Reflection resource totals across 24 cells:

| Action cap | Ordinary reads | Writes | Actions | Decisions | Corrective admissions |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 | 89 | 48 | 137 | 171 | 24 |
| 10 | 94 | 53 | 147 | 185 | 24 |
| 12 | 97 | 55 | 152 | 190 | 24 |

Reflection made no trusted checks. The dynamic arms' recorded resource vectors were
unchanged across caps: baseline 60 actions/79 decisions, verify 44/44 with 46 trusted
checks and 72 logical target rows, recover 92/92 with 70 checks and 112 rows. The full
vectors remain separate quantities, not a common cost unit. Elapsed time is descriptive.

Every persistent-drop cell started with thirteen drops. The fixed factory ceiling of
twelve was used at all caps; counters were not silently regenerated from each assigned
Budget. Clean, single-drop and transient configurations were fixed across caps as well.
Stop flags retain overlapping action/decision/corrective/deadline information without
claiming a unique causal stopping reason.

All 96 new eight-action cells matched the prior decision-cap-twelve reference in final
truth, claims, false claims, failure and resource vectors. Historical persistent-drop
counters started at nine rather than thirteen. Both exceed every possible eight-action
write count, but configured/unused counters differ. This is a disclosed descriptive
anchor check, not exact-input replication; historical and partial outcomes are not pooled.

## Raw evidence and local audit

The single completed attempt is at
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/action-budget-comparison/b6e14b134cd0487ca797107c94c00165`.
Its manifest SHA-256 is
`94a1e78000d637910db03370ba9f3bf5cb21a67600eb0b3472e15abd36e5ec45`.

`analysis/action_budget_results.py` performs post-execution read-only reconciliation and
matched contrasts. It does not execute a policy/provider and is outside the locked
execution inputs. All 288 rows, exact order, IDs, copied plan/lock, native trace/SQL data,
fixed-fault metadata, stop diagnostics and resource vectors passed. Original product/
execution code, plan, lock and historical artifacts remain unchanged. The raw evidence
is now included in the [portable evidence package](ACTION_BUDGET_PACKAGE.md).

These are unsigned fixed-mock sensitivity findings, not authenticated provenance or an
independent reenactment of fault delivery. One observation per cell supports no stochastic
confidence, significance, causal verification effect, equal-information/dollar parity or
LLM-quality conclusion. External review and broader resource/live studies remain pending.
