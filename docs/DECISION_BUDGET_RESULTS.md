# Recorded mock decision-budget sensitivity

Recorded 2026-11-26 from the unchanged [prospective plan](DECISION_BUDGET_COMPARISON.md)
and [execution lock](review/decision-budget-execution-lock.json). The completed attempt
contains all 288 ordered assignments and unique run IDs. Each arm/cap has 24 task/scenario
cells. All independent trace/resource/stop/SQL rechecks passed.

## Assigned outcomes

Entries show counts at decision caps **4 / 8 / 12**, each out of 24 assigned cells.

| Arm | Final goals met | Final success claims | False success claims | Achieved-goal budget failures |
| --- | --- | --- | --- | --- |
| Dynamic baseline | 9 / 9 / 9 | 13 / 19 / 19 | 6 / 10 / 10 | 2 / 0 / 0 |
| Dynamic verify | 9 / 9 / 9 | 9 / 9 / 9 | 0 / 0 / 0 | 0 / 0 / 0 |
| Dynamic recover | 15 / 19 / 19 | 15 / 19 / 19 | 0 / 0 / 0 | 0 / 0 / 0 |
| Mock self-reflection | 11 / 19 / 19 | 4 / 14 / 15 | 0 / 0 / 0 | 7 / 5 / 4 |

No untargeted status/version changes were observed. All model calls/tokens were zero.
The [machine-readable record](review/decision-budget-results.json) retains every assigned
outcome, report-derived diagnostics, resource vector, fault record and file checksum, plus
192 matched descriptive contrasts (two per arm/task/scenario).

Increasing decisions from four to eight coincided with four additional achieved goals for
recover and eight for reflection in this fixed corpus. At twelve versus eight, no arm
changed final goal satisfaction. Only partial_satisfied/silent_drop in reflection changed
its final claim from false to true, eliminating one achieved-goal budget failure.

The four remaining reflection achieved-goal budget failures at cap twelve were pair_done
and mixed_status under silent_drop/transient. Each used eight actions but fewer than
twelve decisions: silent drops used nine decisions and transients used eight. Their
action-cap flags remain distinct from decision-cap flags. The policies retain their
original stopping semantics, including no free finish after reaching the action cap.
The counter evidence does not prove a unique causal stop beyond those recorded facts.

Lower baseline false-claim counts at cap four coexist with fewer total final claims and
two achieved-goal budget failures. They do not establish a generally safer or better policy.
Final truth, claims and stopping outcomes must remain separate.

## Resource sensitivity and prior reference

Reflection totals over 24 cells:

| Decision cap | Ordinary reads | Writes | Actions | Decisions | Corrective admissions |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | 51 | 28 | 79 | 96 | 15 |
| 8 | 85 | 45 | 130 | 163 | 24 |
| 12 | 89 | 48 | 137 | 171 | 24 |

Reflection made no trusted checks. Dynamic recover's cap-four totals were 74 actions,
74 decisions and 61 trusted checks/96 logical target rows; at eight and twelve they were
92 actions, 92 decisions and 70 checks/112 rows. The full per-arm vectors and realized
fault exposure are retained in the record. These quantities do not measure total database
work or establish equal information/cost. Elapsed time is descriptive only.

All 96 newly executed cap-eight cells matched the earlier common-corpus study in final
truth, final claims, false claims, failure and recorded resource vectors. This is a
descriptive stability observation; old outcomes were neither substituted nor pooled.

## Attempt history and raw evidence

The first attempt stopped on a Windows permission error during atomic manifest replacement.
Its 206 completed rows and unknown active assignment remain in
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/decision-budget-comparison/f14a6dd29f2a46b79fb193d3c9c2d839`.
Partial manifest SHA-256:
`b9969491867c05b606ec14acafa7c3629289918dcfa3359dfc01ca221a1c9a8f`.
This operational interruption and explicit fresh attempt are disclosed here; there was
no automatic retry, resume or silent replacement of a condition. Partial outcomes are
not pooled with the completed study, and no complete-coverage claim applies to that attempt.

A separate full attempt ran outside the sandbox with the same frozen inputs. It is at
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/decision-budget-comparison/4f378a29036346f999dcc9e479d2a20d`.
Completed manifest SHA-256:
`69c8aadd644bf5a6b79aec7d44dde6317f79c40abbd468a63fce2751f16a7d9f`.
The recorded attempt history preserves both identities and their separate denominators.

`analysis/decision_budget_results.py` performs the post-run read-only audit using the
existing condition reconciler and final SQL checks. It lives outside the frozen research
execution inventory; no bound runner/auditor/product code or plan/lock was changed.
It does not execute a provider or policy. The raw evidence is now included in
[separate portable complete/partial packages](DECISION_BUDGET_PACKAGE.md).

This is unsigned local consistency and fixed mock decision-cap sensitivity. Fault delivery
is not independently reenacted. One observation per cell supplies no stochastic uncertainty,
significance, causal verification benefit, equal-resource/dollar parity or LLM-quality
claim. External review and broader action/information/resource studies remain pending.
