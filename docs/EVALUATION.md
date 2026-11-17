# Phase 1 evaluation protocol

Research question: does evidence-grounded verification plus adaptive failure recovery
improve verified autonomous completion at acceptable cost and latency?

Phase 1 validates mechanisms, not that general hypothesis. Four deterministic scenarios
are available: clean execution, one silent dropped write, persistent dropped writes,
and one transient pre-commit failure. Each mode gets the identical objective, initial
issues, fault counts and default budgets in a separate fresh database. The same command
can be repeated without contaminating prior runs. UUIDs, timestamps, absolute paths and
wall-clock latency vary; state outcomes and attempt counts are deterministic.

For each run:

- **Verified completion:** post-run audit passes all original status requirements.
- **False success:** agent claims success but post-run audit fails. For a suite, report
  both count / all runs and count / claimed-success runs; the latter is undefined if no claims.
- **Recovery:** at least one retry occurred and the final audit passes. Recovery rate
  should use initially failed recoverable runs as denominator, not all runs.
- **Latency:** measured agent-loop wall-clock milliseconds, including trace overhead,
  excluding fixture setup and the post-run evaluation audit.
- **Model tokens / cost:** zero for this deterministic provider. Remote prices and total
  operating cost are not modeled.
- **Unsafe actions:** zero by the current tool inventory, not a general safety evaluation.

The JSON reports expose run-level measurements, not significance tests. A persistent
fault should exhaust retries and yield an honest failure. Verification-only should detect
a silent drop but not repair it. Baseline reports include null internal verification and
an explicitly separate post-run audit, preventing an evaluator from helping the baseline.

Later evaluation must add independent task oracles, self-reflection, stochastic repeated
trials, paired confidence intervals, verifier false positives / negatives, broader faults,
and ablations controlling for extra action and token budgets. Do not infer verifier
accuracy from comparing this verifier against itself. Published claims must include
raw traces, dependency lock, task definitions, fault schedules and actual measurements.
