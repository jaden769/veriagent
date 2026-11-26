# Prospective mock action-budget sensitivity

Prepared 2026-11-26. Status: **specified, not run**. The
[plan JSON](review/action-budget-plan.json) pins 288 ordered fresh assignments, source/
corpus hashes and the prior results motivating this follow-up. Runner, execution lock
and outcomes remain pending. Historical plans, locks and evidence are unchanged.

The [decision-cap study](DECISION_BUDGET_RESULTS.md) retained four reflection runs with
achieved goals and budget failures at twelve decisions. All four exhausted eight actions;
none exhausted twelve decisions. This motivates varying actions while holding decisions
fixed. It does not establish that increasing actions will fix every case. The follow-up
is informed by observed mock findings, not independent confirmatory evidence.

## Assigned intervention

| Dimension | Selection |
| --- | --- |
| Tasks and scenarios | All six original tasks × clean/silent_drop/persistent_drop/transient |
| Arms | Dynamic baseline, verify, recover; separate mock self-reflection |
| Varied cap | 8, 10 or 12 ordinary actions |
| Fixed budget | 12 decisions, 2 retry/corrective admissions, 60-second run, 1-second action |
| Repetitions | One fresh run per cell; 288 assigned runs |
| Information | Existing mock policies; unlimited dynamic trusted ledgers; no reflection oracle |

Preserve native reports and original phase, retry, authorization and stopping semantics.
Finish decisions and ordinary confirmation reads consume their existing resources. Do
not grant a free finish after an action cap. Each cell gets fresh state, provider, policy,
executor, trace store and applicable dynamic ledger. No previously executed cell is reused.

Each of 24 task/scenario blocks contains all three action caps and four arms. Rotate cap
order by zero-based block index modulo three. Rotate arm order within each cap group by
`(block_index + cap_position - 1) modulo 4`, with one-based cap_position. Every cap occupies
each group position eight times; within each cap, every arm occupies each arm position
six times. Order is fixed and balanced, not randomized.

## Keep fault configuration fixed

The existing `scenario_faults(scenario, max_actions)` factory normally configures
persistent drops as max_actions + 1. Calling it with each varied cap would also vary
the starting fault counter. Instead, this plan calls the unchanged factory with the
fixed argument **12 for every cell**, independently of the assigned action budget.
Thus persistent_drop starts with 13 drops at caps 8, 10 and 12; clean, single drop and
single transient configurations are identical across caps as well. The runner must
verify this invariant before constructing an agent. Do not silently use the ordinary
runner's per-budget fault argument.

Thirteen drops exceed all possible writes within any assigned action cap, so the
persistent scenario remains persistent throughout the allowed run. At the historical
eight-action reference, the prior configuration used nine drops. Both exceed every
possible eight-action write count, but their configured/unused counters differ. Report
that difference; the historical anchor is descriptive rather than an exact-input replay.
Do not move unused faults, change their target after observing exposure or feed fault
labels/counters to a provider. Preserve realized attempts and pre-fault statuses.

## Outcomes, contrasts and stopping evidence

Primary outcomes are independent final target-status satisfaction and achieved-goal
budget failure. Report all 24 assigned task/scenario cells per arm/cap (96 per cap),
keeping final claims, false success, untargeted status/version changes and original
reflection claims separate. Target titles remain outside this SQL oracle.

Record matched 12-minus-10, 10-minus-8 and 12-minus-8 changes within each arm/task/scenario.
Show improved/unchanged/worsened goal and achieved-goal budget outcomes without a policy
ranking or success threshold. The comparisons use only new cells. Compare the new
eight-action/twelve-decision cells descriptively against the prior decision-cap-twelve
reference, disclose the persistent counter difference and retain disagreements. Do not
pool historical or interrupted-attempt observations with this study.

Retain ordinary actions/reads/writes, decisions, trusted calls/known logical target rows,
recovery/corrective admissions, available repeat-write counts, model calls/tokens and
elapsed time. Preserve configured and unused faults, realized exposure and recovery
eligibility. Exposure-conditioned summaries are diagnostics, not primary denominators.

Record exhausted action, decision and corrective counters, reported deadline status,
terminal failure and achieved-goal budget outcome. Multiple flags may overlap; none alone
proves a unique causal stop. Additional actions can leave the decision or corrective
ceiling binding. Do not change those ceilings after observing an outcome.

## Pretrial and evidence gates

Implement a dedicated mock-only runner that validates exact plan bytes/order, typed
budgets, source/corpus/prior-result pins and the fixed fault configuration before outputs
or providers. Bind plan, runner and relevant auditors in a new execution lock before
the first trial. The prior decision-budget runner does not implement this fault invariant
and must not be used unchanged as if it did.

Require unique identities, native trace/report/resource reconciliation, dynamic live
ledger/admission agreement, reflection phase replay and the same independent post-policy
SQL audit across arms. No evaluator data returns to a policy. Retain raw states, traces,
reports, stop diagnostics and hashes. Harness/audit errors stop the attempt with retained
partial evidence and an unknown active outcome. No automatic retry, resume or condition
replacement is planned; task failures and false claims remain findings. Missing outcomes
are unknown and incomplete coverage cannot be labeled complete.

This isolates action-cap sensitivity within the specified policies, not equal information,
total database work, tokens or dollars across arms. One deterministic observation per
cell supplies no stochastic confidence, significance, causal verification benefit or
LLM-quality claim. External review and broader resource/live studies remain pending.
