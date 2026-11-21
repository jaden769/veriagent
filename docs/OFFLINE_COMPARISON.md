# Prospective offline comparison specification

Prepared 2026-11-21. Status: specified, **not run**. This is a deterministic mechanism
check over the [review snapshot](review/offline-baseline.json), not a stochastic study
or external approval. The [machine-readable plan](review/offline-comparison-plan.json)
contains exact CLI arguments, source-snapshot binding, selections, budgets and metrics.

## Question and scope

For each fixed task/fault condition, how do baseline, verify and recover differ in final
target satisfaction, false claims, observed recovery and resource use? Analyze static
and dynamic engines separately. Neither language interpretation nor general browser
behavior is measured: these are fixed requirements executed against the SQLite sandbox.

Select all six pinned tasks and the four default scenarios: `clean`, `silent_drop`,
`persistent_drop` and `transient`. Include all three implemented modes. Run one repetition
per condition. This yields 72 runs per engine, in two batches below the 120-run per-batch
limit, and 144 planned runs overall. Do not pool the resulting task/scenario/mode strata.
There is one observation per stratum and no stochastic effect-size estimate is planned.

Per run: eight action admissions, eight decision admissions, two recovery attempts,
60-second cooperative timeout and one-second action timeout. The CLI exposes action,
decision and run-time limits; recovery and action-time limits use the pinned Budget
defaults. Identical caps do not imply identical realized work. Verification reads, policy
timing and model-decision behavior differ between modes and engines.

## Planned commands

These commands are examples for the later offline check; they were not executed when
this specification was prepared. The plan JSON spells out each scenario explicitly.

```powershell
.\.venv\Scripts\veriagent.exe benchmark --provider mock --all-tasks --repeats 1 --engine static --max-actions 8 --max-decisions 8 --timeout 60 --scenario clean --scenario silent_drop --scenario persistent_drop --scenario transient --output artifacts/comparison-spec-static
.\.venv\Scripts\veriagent.exe benchmark --provider mock --all-tasks --repeats 1 --engine dynamic --max-actions 8 --max-decisions 8 --timeout 60 --scenario clean --scenario silent_drop --scenario persistent_drop --scenario transient --output artifacts/comparison-spec-dynamic
```

The mock provider is explicit even if credentials exist. No live batch is included in
this plan. Repeating these deterministic conditions would exercise reproducibility,
not add independent samples for reliability estimation.

## Outcomes and analysis rules

Primary outcome: `ground_truth_success`, the benchmark's independent post-run target
status audit, by engine/task/scenario/mode. Untargeted status/version changes are reported
separately, so target satisfaction alone must not be called collateral-safe completion.
The sandbox benchmark oracle does not assess natural-language interpretation or target
title preservation; browser-audit capabilities must not be attributed to this oracle.

Secondary outcomes use the implemented summary fields in the plan. Report false-success
counts over all runs and conditional on success claims. Report recovery both over all
runs and over the realized pre-commit fault/mismatch-eligible subset. Zero-denominator
conditional rates remain null. Already-satisfied success without repair is not recovery.
Compare realized injected/unused events as well as scenario labels: a policy can avoid
or fail to reach a scheduled write.

Record action counts, agent-loop latency, model calls, tokens and unknown usage. Mock
usage does not estimate live cost. The implementation includes trace/instrumentation
overhead in latency and excludes setup and the final benchmark audit. Nominal Wilson
intervals may appear in generated summaries; do not interpret them as stochastic
confidence for these deterministic observations or infer independence from their presence.

Mode order rotates by repetition within each task/scenario; with one repetition it stays
baseline/verify/recover. This specification does not randomize ordering or balance thermal,
cache or service effects. It supports descriptive mechanism checks, not causal latency claims.

## Completion and failure handling

Require both manifests to be complete, with 72 planned/completed rows each, the pinned
corpus digest, expected engine/provider/budget, unique run identities, exact selected
task/scenario/mode coverage and no silently discarded rows. Retain raw state, trace,
configured/realized faults and per-run outcomes. Benchmark exit 0 means batch completion,
not that every agent succeeds; honest failures and baseline false-success controls remain
in the analysis. Investigate incomplete batches and provider diagnostics separately.
Never replace a failed run with an unrecorded retry.

Before running, verify the snapshot and plan hashes against the checkout. Source drift
requires an explicit plan revision; a matching hash is a reproducibility check, not review
approval. After running, record actual artifact paths and validation results separately
from this prospective file. Do not convert planned numbers into measured results.

## Missing comparator work and live-study gate

Self-reflection is not an implemented Mode. Define its observations, action authority,
stopping rule and budget accounting before claiming comparison against it. Budget-controlled
ablations must distinguish policy effects from extra actions, verifier reads, decisions,
tokens and elapsed time. Running the three modes under shared caps does not complete
these ablations.

External corpus/fault review, comparator implementation and a study-specific prospective
analysis plan remain prerequisites for a broader live comparison. Any live design needs
its own model configuration, sample-size rationale, failure/exclusion rules, uncertainty
method and spending plan. This offline specification supplies none of those live results.
