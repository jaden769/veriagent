# Optional OpenAI planning milestone

The adapter proposes a static plan using the OpenAI Responses API. Requirements are still
parsed using the original constrained objective grammar. Execution, verification and
recovery remain local and use the same trusted policies as the offline demo. This is the
first Phase 2 increment, not a completed general LLM agent.

## Install and configure

```powershell
.\.tools\uv.exe sync --extra dev --extra openai --locked
$env:OPENAI_API_KEY = Read-Host "OpenAI API key" -MaskInput
$env:OPENAI_MODEL = Read-Host "Model ID available to your account"
```

Use a model that supports Responses API Structured Outputs. Do not commit your key or
paste it into a chat. `.env.example` documents variable names; `.env` is not loaded
automatically. There is deliberately no default model or silently substituted provider.

The following command makes one potentially billable API request. Run it only when you
intend to use your account's API quota:

```powershell
.\.tools\uv.exe run --extra openai veriagent smoke --provider openai
```

`--model` overrides `OPENAI_MODEL`. The model receives the objective and authorized
requirements; it does not receive database contents, observations, credentials or traces.
The endpoint is explicitly `https://api.openai.com/v1`, `store=False` is sent, and the SDK
client is closed after execution. This storage flag is not a general retention guarantee.

## Reproducible smoke evidence

`veriagent smoke` uses the offline mock by default, even if API credentials are present.
Only `--provider openai` selects a potentially billable request. Each invocation creates
a new UUID directory under `artifacts/smoke/`; it never reuses a previous database.

The fixed task is `Set ISSUE-1 to done`, with one injected silent dropped write. Passing
requires all of these: a recorded state mismatch, at least one recovery attempt, a verified
final status of done, a passing post-run audit, and unchanged ISSUE-2 and ISSUE-3. Merely
completing the task without detecting and repairing the fault does not pass the smoke check.

The command prints JSON and saves `result.json`, `trace.json`, `trace.txt`, `traces.sqlite`
and `state.sqlite` in the reported directory. Results include the task, budget, initial and
final state, model usage, audit evidence, Python version and relevant package versions.
No credentials are recorded. Exit codes: 0 for a passing smoke check, 1 for a completed
check that failed, and 2 for invalid or missing configuration. Planning errors and refusals
still save a failed result; missing model/key configuration stops before artifact creation.

All files stay local under the Git-ignored `artifacts/` directory. To share a result,
review its JSON/text contents first. The bundle aids reproduction but is not a statistical
benchmark. A model can generate redundant writes that satisfy the task before verification;
the smoke check correctly rejects that as a demonstration of recovery.

Environment variables set in one terminal apply to that terminal and child processes.
Setting them there does not update an already-running Codex process. Run the smoke command
in the same terminal where you configured the variables. Remove the session key afterward
with `Remove-Item Env:OPENAI_API_KEY` if desired.

## Limits and accounting

- Exactly one planning request is attempted per run, with SDK automatic retries disabled.
  Recovery revises the plan deterministically and makes no further model requests.
- `--model-timeout` defaults to 15 seconds, capped by the remaining `--timeout` run budget.
  `--max-output-tokens` defaults to 2048. The output limit bounds generated tokens, not
  total spending. There is no dollar budget guarantee. SDK timeouts are transport limits,
  not a hard wall-clock cancellation guarantee; cold imports can also consume run time.
- `--input-price` and `--output-price` take USD per million tokens and must be supplied
  together. No prices are hardcoded. Without prices, estimated cost is null. Without
  returned usage (for example after a transport failure), token count and cost are null.
- `model_calls` counts attempted planning requests, not proven billed calls. A transport
  error may occur before or after server processing; billing can be unknown.
- Reports and traces include input/output usage and the actual returned model identifier.
  The simple price calculation omits cached-input discounts and service-tier pricing.

The agent validates every plan against original task requirements before executing it.
Wrong targets, wrong statuses, invented tools, extra permission fields, missing coverage,
and invalid dependencies fail with zero actions. Refusals, incomplete output and API errors
produce honest failure reports; there is no automatic fallback to a mock success.

## Offline verification of the integration

```powershell
.\.tools\uv.exe run --extra dev --extra openai pytest
.\.tools\uv.exe run veriagent demo
```

Tests inject both provider-level responses and actual SDK HTTP responses with
`httpx.MockTransport`; no request leaves the process and no real key is used. If the OpenAI
extra is absent, five SDK-specific cases are skipped while all other tests remain offline.
Install the extra to exercise the complete boundary. In the Codex Windows sandbox, asyncio
and SDK imports may block; the recorded complete suite runs outside that sandbox.

No live API call has been made as part of implementation. Model-specific schema acceptance,
real latency, service errors and output quality require a separately authorized smoke test.
Broad natural-language interpretation, interactive tool calling, model-driven recovery,
provider comparisons and general injection resistance remain future work.

Implementation references: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[SDK retry and timeout behavior](https://github.com/openai/openai-python#retries).
