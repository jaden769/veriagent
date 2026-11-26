# Common-corpus mock comparison results

Recorded 2026-11-26 against the unchanged [prospective plan](REFLECTION_COMPARISON.md)
and [pretrial lock](review/reflection-execution-lock.json). All 96 assigned runs completed:
six tasks × four scenarios × four arms, one observation per condition. All run IDs were
unique and all 24 fixed rotating blocks retained their assigned order.

## Observed outcomes

| Arm | Final target state met | Final success claims | False success claims | Terminal failures |
| --- | ---: | ---: | ---: | --- |
| Dynamic baseline | 9/24 | 19/24 | 10/24 | 5 transient |
| Dynamic verify | 9/24 | 9/24 | 0/24 | 10 state mismatch, 5 transient |
| Dynamic recover | 19/24 | 19/24 | 0/24 | 5 state mismatch |
| Mock self-reflection | 19/24 | 14/24 | 0/24 | 10 budget |

No untargeted status/version changes were found. These are target-status outcomes;
title preservation is outside this oracle. An expected fault or budget failure is retained
as a finding and does not mean the evidence audit failed.

| Scenario | Baseline targets met | Verify targets met | Recover targets met | Reflection targets met |
| --- | ---: | ---: | ---: | ---: |
| Clean | 6/6 | 6/6 | 6/6 | 6/6 |
| Silent drop | 1/6 | 1/6 | 6/6 | 6/6 |
| Persistent drop | 1/6 | 1/6 | 1/6 | 1/6 |
| Transient | 1/6 | 1/6 | 6/6 | 6/6 |

Reflection reached five goals without a final success claim: pair_done and mixed_status
under silent_drop/transient, plus partial_satisfied under silent_drop. These ended with
budget failures after reaching the final state, before completing the required confirmation
and finish sequence. The other five reflection budget failures were unsatisfied goals
under persistent drops. Original reflection claims were true in 19 cases and false in five;
they are separate from final claims and independent truth.

## Resource and exposure accounting

Totals across 24 runs per arm:

| Arm | Ordinary reads | Writes | Actions | Decisions | Trusted checks | Known target rows | Policy admissions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dynamic baseline | 34 | 26 | 60 | 79 | 0 | 0 | 0 |
| Dynamic verify | 22 | 22 | 44 | 44 | 46 | 72 | 0 |
| Dynamic recover | 46 | 46 | 92 | 92 | 70 | 112 | 20 |
| Mock self-reflection | 85 | 45 | 130 | 163 | 0 | 0 | 24 |

Admissions mean recovery admissions for dynamic recover and corrective-phase admissions
for reflection. They are distinct mechanisms, not interchangeable units. Trusted checks
and evaluator SQL reads are not ordinary actions. All mock model calls/tokens were zero.
Per-run elapsed milliseconds are retained as descriptive data, not a latency experiment.

Each arm had 15 fault-recovery-eligible runs, five per fault scenario. Already-satisfied
tasks contribute success without recovery; realized targets, pre-fault statuses and unused
fault counters remain in the raw evidence. Equal eligibility counts do not establish equal
exposure or causal comparability. The primary tables include every assigned condition.

## Evidence and independent checks

The [machine-readable record](review/reflection-comparison-results.json) retains every
condition, outcome, resource vector, fault record and per-file checksum. Raw local evidence
is at `C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/reflection-comparison/62feb890e069465bae62ca45a0a3845c`.
Its manifest SHA-256 is
`b15d202a3f160e4f9968b287c7a6f4ce46fdcc1834d3c885ab5fb91fb770660c`.

The separate `research/reflection_results.py` checker reads the saved local evidence,
checks assigned coverage/bindings, matches native reports and SQLite/JSON traces, reruns
the appropriate trace reconciliation, compares live dynamic ledgers and resource counters,
and independently reads final SQL rows against the pinned corpus. It does not execute a
provider, policy or embedded runner. All 96 rechecks passed. Fault records are bound by
hash and eligibility labels are recomputed; fault delivery is not independently reenacted.
This is a local evidence checker, not a hardened untrusted archive importer.

The [portable evidence package](REFLECTION_PACKAGE.md) now includes all raw runs. Hashes and trace
consistency are unsigned and do not prove authenticity. The shared caps do not equalize
information, actual work or cost. One deterministic observation per cell supports no
stochastic confidence, significance, causal benefit, LLM reflection quality or general
agent-reliability claim. External review and metered live comparisons remain pending.
