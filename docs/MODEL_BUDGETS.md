# Per-run model usage limits

The OpenAI adapter optionally enforces cumulative usage policies across all requests in
one interpretation or execution run. The default is no cumulative model limit; existing
action/decision/retry/time limits still apply. Static planning, dynamic selection, smoke
checks and requirement proposals use the same request-admission ledger.

## Options and guarantees

| CLI option | Meaning | Limitation |
|---|---|---|
| `--max-model-output-tokens N` | Cumulative API-reported output allowance; cap the next request's `max_output_tokens` by the known remainder | Depends on provider enforcement and reported usage; unused remainders under 128 tokens stop further requests |
| `--max-model-tokens N` | Stop admitting requests once observed input + output tokens reach N | The current request can overshoot because input usage is known only after it returns |
| `--max-model-cost USD` | Stop once observed estimated cost reaches the threshold | Requires caller prices; the current request can overshoot and actual billing can differ |

All limits are optional and nonnegative; zero disallows the first request. The output
policy also disallows the first request for allowances under 128 tokens. This 128-token
floor is a local policy matching the adapter's minimum configured output allowance, not
a claim about an API-wide minimum. Unused smaller remainders are retained in accounting
but cannot authorize another request.

The existing `--max-output-tokens` is a **per-request** ceiling (default 2048). The new
`--max-model-output-tokens` is **cumulative per run**. The adapter sends the smaller of
the per-request ceiling and the remaining cumulative output allowance to the API.

These are not account-level quotas or a hard dollar spending guarantee. Total tokens and
cost are observed thresholds, not exact preflight estimates. No tokenizer or input-cost
estimator is used. Input tokens, cache discounts, pricing tiers, provider behavior and
failed/ambiguous requests can prevent knowing exact billed spend. A response exceeding
an observed threshold is retained in usage accounting but cannot authorize a tool action.

## Example

After installing the OpenAI extra and configuring credentials/model, explicitly opt in:

```powershell
.\.venv\Scripts\veriagent.exe smoke --provider openai --engine dynamic --max-decisions 6 --max-model-output-tokens 2048 --max-model-tokens 12000
```

This can make multiple billable requests. To add an estimated-cost threshold, supply both
current input/output prices in USD per million tokens:

```powershell
$inputPrice = Read-Host "Verified input price in USD per million tokens"
$outputPrice = Read-Host "Verified output price in USD per million tokens"
.\.venv\Scripts\veriagent.exe smoke --provider openai --engine dynamic --input-price $inputPrice --output-price $outputPrice --max-model-cost 0.05
```

No model prices are hardcoded. A cost threshold without both prices is rejected before
provider construction. Limit flags on the offline mock are rejected rather than implying
that paid usage has been measured. To exercise budget behavior without credentials or
spending quota, run the simulated tests instead:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_budgeting.py tests/test_dynamic_openai.py -q
```

## Admission, responses and unknown usage

Before each request the adapter resets the per-attempt usage record to zero calls and
checks the ledger. A rejected admission makes no API request and does not increment the
model-call count. Once admitted, one attempt is counted. SDK retries remain disabled.
Responses are recorded before parsing their plan, requirements or function call, so
malformed/refused output still consumes any returned usage.

A response exactly at a threshold remains usable; a subsequent request is denied. If it
completes the task, the agent can terminate successfully without another request. A
response over the threshold is unusable, even if its proposed action would have been valid.

When a relevant limit is active and required usage is unavailable, the adapter stops
closed: no action is authorized from that response and no further request is admitted.
Missing total tokens, output tokens or estimated cost yield explicit unknown-usage reasons.
Without cumulative limits, unknown usage remains null and the existing behavior is kept.
Transport errors may leave server processing/billing unknown; zero is never substituted.

The ledger resets at the start of each agent run or proposal operation. Reusing a provider
does not inherit the prior run's spend or stop reason. Separate interpretation and execution
commands have separate budgets; these are not a combined workflow or persistent account
budget. Restarting a run resets its allowance.

## Evidence and failure reporting

Execution reports include `model_budget` with configured limits, observed cumulative
usage and `stop_reason`. Traces include budget snapshots next to model usage. Proposal
results also retain a budget snapshot if interpretation is rejected. A budget stop is
classified as `failure=budget`, or `error=model_budget_exhausted` for a proposal, rather
than an ordinary planning failure. Already completed tasks in verified dynamic mode can
finish with zero model requests.

If an actual API/transport error also leaves usage unknown, the underlying request error
is preserved as the primary planning failure. The ledger remains stopped, and a sanitized
`provider_diagnostic` records the safe category/status/code. Missing-usage fallout does not
replace the original failure. No additional model request or tool action is authorized.

Examples of stop reasons: `total_tokens_exhausted`, `total_tokens_exceeded`,
`output_allowance_insufficient`, `output_tokens_exceeded`, `cost_threshold_reached`,
`cost_threshold_exceeded`, `token_usage_unknown`, `output_usage_unknown`, and
`cost_usage_unknown`. Per-decision usage remains available when a total is unknown.

Custom providers implement `begin_run()` and a `budget_state` property alongside usage.
The mock returns no model-budget state. The OpenAI provider resets its ledger in
`begin_run()`; admission happens inside the provider before the transport call, independently
of which agent engine invoked it.

All validation uses synthetic responses and in-memory SDK transports. No live token/cost
threshold behavior or actual billing has been measured during implementation.
