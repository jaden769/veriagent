# Repeated-trial benchmark

For current evidence gaps, pinned corpus/matrix fingerprints and external-review questions,
see the [research validation review packet](RESEARCH_REVIEW.md).
The [offline comparison specification](OFFLINE_COMPARISON.md) pins a prospective mock
check; planned batches are separate from measured results.

`veriagent benchmark` runs fixed requirements on fresh SQLite sandboxes,
comparing baseline, verify and recover modes. Offline mock is the default even when API
credentials exist. Default: 3 repetitions × 4 scenarios × 3 modes = 36 runs. Scenarios
are clean, one silent drop, persistent silent drops, and one transient write error.
Mode order rotates across repetitions; the fault counters reset for every run.
The default task remains `single_done` (ISSUE-1 to done), preserving the 36-run default.

```powershell
.\.venv\Scripts\veriagent.exe benchmark --engine dynamic --repeats 3
```

Each UUID artifact directory contains `benchmark.json` plus per-run state, result,
SQLite trace and JSON trace. The manifest records source hashes, Python version, exact
budgets, selected task cases, corpus SHA-256, order and completed runs. Each live run records model configuration
(including caller prices and model limits, without credentials). Summaries update
atomically after each completed run; interruption leaves `complete: false`. There is no
resume or automatic retry of an interrupted batch.

A separate read-only SQL query checks every requested final status and compares
untargeted status/version fields against their recorded starting values, including
missing or added rows. The execution verifier is not the benchmark oracle.
False success means an agent claim with an unsatisfied final target. A failed agent run
is retained as an outcome; command exit 0 means the batch completed, not all modes won.
A provider diagnostic stops the batch with exit 1, preserving partial evidence.

Results are grouped by task, scenario and mode, not pooled across conditions. Each group
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

## Fixed varied-task corpus

`src/veriagent/scenarios/benchmark_tasks.json` contains six manually specified tasks
and complete initial statuses, validated before provider construction or artifact writes:

| Task ID | Goal | Starting conditions |
| --- | --- | --- |
| `single_done` | ISSUE-1 done | All open |
| `pair_done` | ISSUE-1 and ISSUE-2 done | All open |
| `mixed_status` | ISSUE-1 done, ISSUE-2 in_progress | Targets open, ISSUE-3 in_progress |
| `reopen` | ISSUE-2 open | ISSUE-1/2 done, ISSUE-3 in_progress |
| `already_satisfied` | ISSUE-1 done | ISSUE-1 done, ISSUE-2 in_progress |
| `partial_satisfied` | ISSUE-1 and ISSUE-2 done | ISSUE-1 done, ISSUE-2 open, ISSUE-3 in_progress |

Initial versions are zero. Trial setup uses trusted fixture data before execution and
records initial rows. Expected requirements are loaded directly, not derived from a
provider parser. This measures execution against fixed goals, not language interpretation.
Task IDs must be unique and known; `--task` can be repeated or use `--all-tasks`.

```powershell
.\.venv\Scripts\veriagent.exe benchmark --all-tasks --repeats 1 --engine dynamic
```

This offline matrix has 6 tasks × 4 scenarios × 3 modes = 72 runs. Task count contributes
to the 120-run ceiling; `--all-tasks` with default 3 repetitions is rejected before any
provider is created. Select fewer tasks/scenarios to repeat each group more often.

Schema version 2 replaces the old singular manifest `task` with `tasks` and adds task IDs
to summaries. Each run includes its requirements, initial state, and configured/remaining
fault counters. A counter is consumed by a write attempt, including a no-op assignment;
it does not prove a mismatch occurred. Dynamic execution can finish an already-satisfied
goal without writing, leaving the entire fault schedule unused. Such success is not
recovery. Static and dynamic engines can expose different numbers of writes to the same
counter schedule; do not treat fault labels as proof of equal realized faults.

## Indexed write-fault schedules

Three additional scenarios are available explicitly through `--scenario`:

| Scenario | Schedule |
| --- | --- |
| `second_drop` | Report success without committing write attempt 2 |
| `second_transient` | Raise a pre-commit transient error on write attempt 2 |
| `two_drops` | Drop write attempts 1 and 2 |

```powershell
.\.venv\Scripts\veriagent.exe benchmark --task pair_done --scenario second_drop --scenario second_transient --scenario two_drops --repeats 2 --engine dynamic
```

This offline command schedules 18 trials. The original four default scenarios and the
36-run default remain unchanged. Indexed injection is a benchmark-only sandbox adapter;
it does not add new production tools, change the agent policy, or alter process workers.

Indices are one-based across calls that reach the sandbox's `set_status`, including
retries and idempotent/no-op assignments. Reads and actions rejected by the engine's
policy do not count. Every fresh trial starts at attempt 1. Deadlines and issue existence
are checked before a scheduled fault is delivered. If a call fails these preconditions,
its index is consumed, the fault is recorded as unused, and it is not moved to a later
attempt. Indexed events and legacy counter faults cannot be combined in one trial.

Per-run `write_schedule`, `write_attempts` and `unused_write_schedule` record planned
faults and actual exposure. Attempts include the target, requested status and injected
fault, if any. Summaries report trials with an injected fault, total injections, and
unused indexed events. These fields are benchmark evidence; they are not supplied to
the planning provider as hidden fault labels.

An index identifies a write position, not an issue: a model can choose a different target
or action order. Use the recorded attempts to compare realized exposure. For example,
a single-target task can finish after one write, never reaching a second-write fault.
An already-satisfied dynamic task may perform no writes. Such successes are not evidence
of recovery, and unused events are not counted as injections. The fixed schedules test
selected positions only; they are not an exhaustive or randomized fault distribution.

## Denominators and review notes

The original `false_success` and `recovered` fields retain their denominator of all
trials in a task/scenario/mode group. Two conditional measures make their meaning explicit:

- `false_success_given_claim`: audited false successes divided by agent success claims.
- `recovery_given_fault_mismatch`: successful runs with at least one recovery attempt,
  divided by runs where a delivered pre-commit fault affected an authorized write whose
  required status was still unmet immediately before injection.

Both expose count, denominator (`trials`), rate and nominal Wilson interval. A zero
denominator has null rate and interval, never 0% or 100%. The recovery subset is measured
from delivered faults and a local status checkpoint, not inferred solely from a scenario
name or the agent's verifier. It excludes undelivered schedules, no-op writes to already
satisfied targets, and failures unrelated to injected writes. It is not a general
recovery rate over every possible initial failure or a causal estimate.

`fault_recovery_eligible` records that subset at run level. `status_before_fault` records
the pre-commit status for delivered counter/indexed faults. Capturing it adds a local
read to some write attempts; this instrumentation overhead is included in agent-loop
latency. Both injected fault types leave the status unchanged before returning/raising,
so an unmet pre-fault status identifies an unmet post-fault write in this adapter.
This assumption does not apply automatically to ambiguous commits or external systems.

A local implementation review checked fixture goals against initial states, all-target
and untargeted-row audit behavior, indexed/counter fault delivery, unused events, and
metric denominators. Regression checks cover these mechanisms. This review was performed
by the implementing assistant; it is not an independent external review or corpus
validation. External corpus review and a preregistered live comparison remain pending.
