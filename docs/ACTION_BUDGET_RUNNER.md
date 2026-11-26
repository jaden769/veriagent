# Pinned mock action-budget runner

`analysis/run_action_budget.py` implements the
[prospective 288-condition action-cap plan](ACTION_BUDGET_COMPARISON.md). The study
remains unexecuted. Selected unit fixtures and simulated full orchestration are software
checks, not comparison observations.

The [pretrial execution lock](review/action-budget-execution-lock.json) binds the published
plan, all eight existing research Python modules and the dedicated action runner.
Product source/corpus and motivating prior-result hashes remain in the plan. The new
runner lives outside historical research execution inventories, preserving their locks.

Before constructing output or providers, execution checks exact plan bytes/order,
288 assignments, typed budgets, input/source hashes, the execution lock and fixed fault
ceiling. Faults come from `scenario_faults(scenario, 12)` at every assigned action cap,
so persistent_drop always starts at thirteen. The assigned Budget varies max_actions
between 8/10/12 while max_decisions stays twelve. Per-run evidence must match both facts.

Explicit future execution from the repository root:

```powershell
.\.venv\Scripts\python.exe -m analysis.run_action_budget --output artifacts/action-budget-comparison
```

No live provider option or product CLI mode was added. Each condition gets fresh state,
provider, executor, policy, trace store and applicable unlimited dynamic ledger. Reflection
gets no trusted verifier. Native reports, normalized provider observations, authorization,
retry/phase caps and agent stopping semantics are unchanged. No fault label or evaluator
result reaches a provider.

The runner saves native reports, SQLite/JSON traces, replay, SQL states, fault exposure
and resource vectors. The existing portable condition auditor independently rereads SQL
and reconciles traces/counters. Additional checks bind the assigned action cap, recorded
Budget, fixed configured faults, repeat-write/time metadata and stopping diagnostics.
Action/decision/corrective/deadline flags may overlap; they are not unique causal diagnoses.

Outputs use a fresh UUID directory with plan, lock and a manifest. Persist the active
condition before execution; retain completed rows and partial files on harness/audit
failure with an unknown active outcome. No retry, resume or condition replacement is
automatic. Task failures and false claims remain findings. Complete evidence requires
all 288 assignments, unique run IDs and successful reconciliation.

Tests cover all arms/caps, persistent-drop configuration across caps, multi-target
reflection, plan/lock/input corruption, fault/resource/stop metadata disagreement,
partial retention and simulated complete/duplicate-ID coverage. These tests do not
establish live model quality, equal information or cost parity. The next increment is
explicit frozen execution and independent results review.
