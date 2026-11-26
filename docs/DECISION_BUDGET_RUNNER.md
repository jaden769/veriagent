# Pinned mock decision-budget runner

`research/run_decision_budget.py` implements the
[288-condition sensitivity plan](DECISION_BUDGET_COMPARISON.md). The full study is
recorded separately in the [results](DECISION_BUDGET_RESULTS.md). Unit tests exercise
selected conditions and simulated orchestration; those
fixtures are not study results.

The [pretrial execution lock](review/decision-budget-execution-lock.json) binds the exact
published plan and the complete repository-local research Python inventory, including
the runner and reused auditors/support code. Product source and corpus hashes remain in
the plan. The motivating prior result record is also checked. This deliberately broad
research binding rejects added or changed research modules before execution; it does not
silently refresh historical plans or the lock.

Plan bytes, typed budgets, 288-condition ordering, source/corpus/prior-result pins and
the lock are validated before any output or provider is constructed. The runner offers
no live provider option. Each condition uses the existing mock executor with a fresh
state, provider, policy, trace store and applicable dynamic verification ledger. Reflection
receives no trusted verifier. No product CLI mode or product source changed.

Explicit future execution from the repository root:

```powershell
.\.venv\Scripts\python.exe -m research.run_decision_budget --output artifacts/decision-budget-comparison
```

Each native report and trace replay is saved before deriving stopping diagnostics.
The reused portable condition auditor independently reconciles traces/resources and
rereads final SQL state against the original corpus. Added budget, repeat-write/time
fields and stopping diagnostics must agree with the native report and assigned cap.
Missing repeat-write counters in dynamic reports remain null, not fabricated zeroes.

Diagnostics separately flag exhausted action, decision and corrective counters, reported
elapsed time reaching the deadline, terminal failure and achieved-goal budget failure.
Several flags may be true together. These are recorded counter facts, not proof of a
unique causal stopping reason or exact monotonic scheduling. The original agent stopping
semantics remain unchanged: extra decisions do not grant actions or free finishing work.

A fresh UUID output directory saves the plan, lock and manifest. The active assignment
is persisted before every trial. On a harness/audit exception, completed rows and partial
files remain, the active outcome is unknown and execution stops. No retry, resume or
replacement is automatic. Task failures and false claims are retained findings. Completion
requires all 288 assignments, unique run IDs and successful evidence reconciliation.

The tests cover all four arms at each decision cap, reflection single/joint cap examples,
plan/lock drift, counter/resource/assigned-cap corruption, partial evidence retention and
simulated full coverage with duplicate-ID rejection. No statistical, equal-cost or live
model conclusion follows from these software checks. The next increment is explicit
frozen execution and independent condition-level results review.
