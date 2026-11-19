# Observation-driven tool selection

The optional dynamic engine selects one action from the latest feedback instead of
executing an entire static plan. It uses the same approved requirements, sandbox tools,
independent state verifier and trusted tool policies. The default engine remains static.

## Offline commands

```powershell
.\.venv\Scripts\veriagent.exe demo --engine dynamic
.\.venv\Scripts\veriagent.exe demo --engine dynamic --scenario persistent_drop
.\.venv\Scripts\veriagent.exe smoke --engine dynamic
.\.venv\Scripts\veriagent.exe run "Set ISSUE-1 to done" --engine dynamic --silent-drops 1 --db artifacts/dynamic-example.sqlite
```

The demo creates fresh paired databases for the same three modes. The deterministic mock
reads an issue before writing, accepts successful mutation acknowledgments in baseline,
and reads again before repairing a verified mismatch in recovery mode. For one dropped
write, the designed outcomes are:

| Mode | Claim | Post-run audit | Tool actions | Recovery attempts |
|---|---|---|---|---|
| baseline | success | incomplete | 2 | 0 |
| verify | failure | incomplete | 2 | 0 |
| recover | success | complete | 4 | 1 |

Actions count reads and writes. The recovery path is read → dropped write → read → persisted
write. It uses four decisions. Baseline uses a third decision to claim completion, which
does not execute a tool. Verified modes can terminate as soon as all requirements pass
verification, without asking for a redundant finish decision.

The static engine has different read/action counts and verification timing. Compare modes
within an engine using paired fixtures; do not interpret these two implementations as
action-budget-matched statistical evidence of model reliability.

## Execute reviewed requirements

Use the existing `propose` and `review` flow, then select the engine on execution:

```powershell
.\.venv\Scripts\veriagent.exe execute "<proposal-file>" --approve "<reviewed-digest>" --engine dynamic --db artifacts/reviewed-dynamic.sqlite
```

Both engines check the proposal before provider construction or sandbox initialization.
The trace binds its digest and interpretation usage to the execution task. The dynamic
engine authorizes every subsequent action against those exact targets and final statuses.

## Optional OpenAI function calls

After configuring credentials and installing the optional SDK, explicitly select OpenAI:

```powershell
.\.venv\Scripts\veriagent.exe smoke --engine dynamic --provider openai --max-decisions 6 --timeout 60
```

This command can make **multiple billable requests**, up to the decision limit. Each
request exposes exactly `read_issue`, `set_status`, and `finish_task`, with strict schemas,
required tool selection and parallel calls disabled. The adapter still independently
rejects multiple calls, unknown tools, extra arguments, incomplete calls and missing IDs.
Plain-text success claims are not accepted as executable decisions.

Each decision is a fresh Responses request containing the approved task and normalized
state. Function results are projected into that state for the next request, rather than
continuing a remote conversation with `previous_response_id` or replaying reasoning
items. The returned `call_id` is recorded for audit; it is not a deduplication key.
See [OpenAI's function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
for the underlying API tool/schema contract.

No live OpenAI tool call has been made during implementation. Actual SDK parsing and
serialization are tested with an in-memory HTTP transport. Schema acceptance by a real
selected model, latency, task quality and actual billing remain unvalidated.

## Independent verification and bounded recovery

- Baseline performs no independent verification and deliberately treats finish as a claim.
  Its `verified_success` is null. A separate evaluator audits the result after execution.
- Verification and recovery modes read authoritative state before decisions, after writes
  or tool failures, and on finish claims. Already satisfied tasks terminate without a
  model request; missing targets terminate before attempting actions.
- A partial multi-issue task is normal when a particular update persisted. A mismatch
  for the attempted target initiates recovery only in recovery mode and within its limit.
- A repeated write requires an unmet target, trusted executor idempotency and explicit
  engine recovery authorization for that target. Model-supplied arguments cannot grant it.
  Confirmed completed targets cannot be rewritten.
- A timed-out acknowledgment after a committed write is resolved by authoritative state,
  avoiding an unnecessary retry. If evidence becomes unreadable, verification becomes
  unknown and the agent reports failure rather than reusing stale evidence.

Default budgets are 20 tool actions, 20 decisions and 2 recovery attempts. `--max-actions`,
`--max-decisions` and `--max-retries` are configurable on `run` and `execute`. Smoke checks
use the default retry limit. `--timeout` is a cooperative run deadline; every provider
request gets a bounded remaining timeout, and late decisions cannot authorize a write.
Repeated reads and premature finish claims are bounded even if no write occurs.

Decision context includes the configured budgets, counters, latest verification and up
to 16 normalized feedback entries. Only typed IDs, status enums, success flags and failure
codes cross the feedback boundary. Raw issue titles, messages and exception text are not
sent to the provider. Full observations remain in local traces, so avoid secrets in them.
This reduces one injection surface; it does not prove general prompt-injection resistance
or protect against a compromised trusted database, interpreter, SDK or executor.

Reports expose `engine`, `decisions`, tool action count, recovery attempts, aggregate model
calls/tokens/cost and final evidence. Each decision's usage and returned model are retained
in traces. A missing usage/cost value makes that aggregate unknown; known values remain
available per call. Mixed response model identifiers produce a null aggregate model ID.
Usage does not carry over from prior runs. A decision limit is not a dollar spending cap.
Optional [model usage limits](MODEL_BUDGETS.md) additionally cap cumulative output allowance
and stop on observed total-token/cost thresholds. The latter can overshoot in the current
request and do not guarantee exact billed spend.
All tool and model timeouts remain cooperative, not hard process cancellation.

This increment implements dynamic selection and observation-driven repair of approved
status tasks. It does not add browser automation, external tools, learned recovery policy,
arbitrary code execution, or a general reliability claim.
