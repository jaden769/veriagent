# Repeated-trial benchmark

`veriagent benchmark` runs a fixed task (ISSUE-1 to done) on fresh SQLite sandboxes,
comparing baseline, verify and recover modes. Offline mock is the default even when API
credentials exist. Default: 3 repetitions × 4 scenarios × 3 modes = 36 runs. Scenarios
are clean, one silent drop, persistent silent drops, and one transient write error.
Mode order rotates across repetitions; the fault counters reset for every run.

```powershell
.\.venv\Scripts\veriagent.exe benchmark --engine dynamic --repeats 3
```

Each UUID artifact directory contains `benchmark.json` plus per-run state, result,
SQLite trace and JSON trace. The manifest records source hashes, Python version, exact
budgets, task, order and completed runs. Each live run records model configuration
(including caller prices and model limits, without credentials). Summaries update
atomically after each completed run; interruption leaves `complete: false`. There is no
resume or automatic retry of an interrupted batch.

A separate read-only SQL query measures the requested final status and changes to
untargeted status/version fields. The execution verifier is not the benchmark oracle.
False success means an agent claim with an unsatisfied final target. A failed agent run
is retained as an outcome; command exit 0 means the batch completed, not all modes won.
A provider diagnostic stops the batch with exit 1, preserving partial evidence.

Results are grouped by scenario and mode, not pooled across conditions. Each group
reports audited success, false success and recovery counts/rates, nominal Wilson 95%
intervals, untargeted changes, mean actions/latency, model calls and tokens. Unknown token
usage stays null and is counted explicitly. Interpretation calls are zero: this benchmark
uses fixed requirements and meters execution only. It does not benchmark language
interpretation, proposals or human review.

Wilson intervals assume independent Bernoulli observations. Mock repetitions are
identical deterministic checks and provide no evidence of stochastic reliability.
Live calls may also share time, account and service conditions; intervals are descriptive,
not a guarantee of independence. No paired significance test, causal effect, general
prompt-injection claim, or population-wide reliability estimate is asserted. Small trial
counts leave wide intervals, including when every observed trial succeeds.

## Optional live batch

Explicit `--provider openai` and `--max-model-output-tokens` are required for live use.
Limits reset for each run; multiply by the number of runs when deciding a batch budget.
At most 120 runs are accepted; repeats must be 1–20. Actions and decisions are bounded
per run, and timeout is cooperative as elsewhere. There is no global dollar cap.

Example (potentially billable; not run automatically):

```powershell
.\.venv\Scripts\veriagent.exe benchmark --provider openai --engine dynamic --scenario silent_drop --repeats 2 --max-actions 6 --max-decisions 6 --max-model-output-tokens 1024 --timeout 60
```

This schedules 6 runs, at most 36 dynamic generation decisions and a summed output
allowance of 6,144 tokens. Input tokens also cost credits. Total-token/cost thresholds
remain observed guards that can overshoot on the current request; see MODEL_BUDGETS.md.
Use mock for repeatable regression checks before selecting live execution.
