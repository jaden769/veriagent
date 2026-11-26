# Prospective common-corpus mock comparison

Prepared 2026-11-26 as a prospective specification. Execution is now recorded separately
in the [results](REFLECTION_COMPARISON_RESULTS.md); the original plan bytes are unchanged. The
[plan JSON](review/reflection-comparison-plan.json) pins source/corpus hashes, arm contracts,
budgets, all 24 task/scenario blocks and their 96 ordered conditions. This is a new plan
for the changed source inventory; earlier plans and measured results stay unchanged.

## Arms and assigned conditions

Use all six corpus tasks, the four default scenarios (`clean`, `silent_drop`,
`persistent_drop`, `transient`) and one run per arm in each condition.

| Arm | Provider and report | Information and corrective policy |
| --- | --- | --- |
| Dynamic baseline | MockProvider / RunReport | Ordinary tool observations; existing baseline behavior |
| Dynamic verify | MockProvider / RunReport | Trusted checks; no mismatch-recovery admission |
| Dynamic recover | MockProvider / RunReport | Trusted checks and bounded recovery |
| Mock self-reflection | MockReflectionProvider / ReflectionReport | Ordinary observations, typed corrective phases; no trusted oracle |

The first three arms use explicit unlimited BudgetedStateVerifier ledgers so their
trusted work is traced. Baseline still invokes no trusted checks. Reflection receives
no verifier or quota object; its provider context stays observation-only. It is a fixed
mock rule, not an LLM self-reflection benchmark. Reflection is not added to Mode and must
not be passed through existing benchmark code as an unsupported fourth mode.

There are 6 × 4 × 4 = 96 planned runs. Within each task/scenario block, rotate arm order
by the block index. Each arm occupies each position six times across 24 blocks. This
balances positions, not task-specific confounds, cache conditions or stochastic dependence;
the order is fixed, not randomized. One observation per cell supplies no statistical
reliability or paired significance claim.

## Shared caps, different information

All arms receive eight tool actions, eight dynamic decisions, two retry/corrective
admissions, a 60-second cooperative run timeout and one-second action timeout. Reflection
uses at most two corrective phases within Budget.max_retries; this count is distinct from
the existing recover arm's recovery admissions. Both reflection finish proposals consume
decisions. No free confirmation, finish or tool read is added when a cap is reached.

Unlimited trusted checks are not charged to tool actions. Reflection read-back is an
ordinary tool action. Thus the caps are shared but information and actual resource use
are not equalized. Report a vector: ordinary reads/writes, decisions, trusted calls and
logical target reads, phase/recovery admissions, time and model usage. Do not collapse
them into a scalar total cost or describe this as completing budget-controlled ablations.
Adapter-internal reads and fault instrumentation also prevent interpreting logical action
counts as total SQLite work. All mock model calls/tokens are zero, not live cost estimates.

## Inputs, exposure and measurement

Every run starts with fresh sandbox, provider, executor, policy, TraceStore and, where
applicable, trusted ledger/adapter. Seed the original complete statuses and zero versions
from the pinned corpus. Reuse the unchanged ScheduledSandbox default fault definitions.
Do not force delivery, move an unused event or change the initial task after observing
which arm reaches a write. Neither provider receives hidden fault labels or evaluator data.

Primary outcome is independent final target-status satisfaction, stratified by task,
scenario and arm. Report final claims and target-based false success separately from
untargeted status/version changes. The final SQL audit runs after execution, outside all
arm allowances, and never returns feedback to a policy. Target title preservation is not
part of this sandbox status/version oracle and must not be claimed.

Preserve actual attempts/targets, pre-fault status, configured/remaining faults, injections,
unused schedules and fault-recovery eligibility. Already-satisfied success is not recovery;
partial-satisfied and no-op writes can yield different exposure between arms. Eligibility
is affected by policy, so do not select only exposed runs for the primary contrast.
Conditional exposed/recovery summaries are descriptive, not causal estimates.

Use one common post-run audit definition across arms but retain native report contracts.
Reflection.original_claimed_success is a reflection-only diagnostic, not a replacement
for other arms' final claims. A final satisfied goal can coexist with an honest budget
failure; preserve both. No predeclared policy ranking or success threshold is imposed.
Unexpected outcomes and false claims are findings, not runs to delete or rerun silently.

## Evidence gates before execution

An explicit mock-only runner must validate the plan before constructing providers or
output directories. It must reject source/corpus drift rather than rewrite the published
plan. Bind the eventual runner and reflection-auditor source hashes to this plan before
the first trial. Record exact assigned coverage, run identity, position, actual budgets and raw
reports, states, SQLite/JSON traces and hashes. Preserve incomplete attempts and active
conditions; no automatic resume or replacement is planned. Incomplete/harness-failed
conditions keep their assigned identity with unknown outcomes; do not impute task success
or failure solely from missing evidence or publish a complete-coverage result.

Dynamic traces must pass admission replay and agree with live ledger counters.
Reflection needs its own trace reconciler before this study runs: verify typed phases,
shared counters, admissions and finish claims without expecting RunReport or inventing
trusted verification. The existing verification-work ledger is not a reflection audit.
The [reflection reconciler](REFLECTION_TRACE.md) and
[mock runner with execution lock](REFLECTION_RUNNER.md) now implement those gates.
The published machine-readable plan is unchanged; no study outcomes are added here.
Both report families must reconcile with observed action/read/write counts and the same
independent final-state audit. No new comparative outcomes are collected by this document.

After implementation, run all assigned cells and retain outcomes by condition. Do not
reinterpret implementation-generated nominal intervals from older benchmark summaries as
stochastic confidence for this fixed mock study. Latency remains descriptive.

## Remaining research boundary

External corpus/fault review, a metered LLM reflection provider, actual equal-resource
ablations and a prospective live study remain pending. These four fixed mock policies
can test mechanism behavior under the specified envelope; they cannot establish general
reflection quality, causal verification benefits or broad autonomous-agent reliability.
