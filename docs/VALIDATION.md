# Local validation

Executed on 2026-11-17, Windows, Python 3.12.16. The repository initially contained only
`.git`; no project files or existing instructions were present. The system `python`
alias could not launch and `py -0p` found no Python installation. Setup downloaded uv
to `.tools/uv.exe`, then installed Python and resolved dependencies into `.venv`.
The committed `uv.lock` records the resolved package versions and hashes.

Commands below ran from the repository root in PowerShell. `uv` was invoked using its
workspace-local executable; it was not added to the user's PATH.

| Command | Observed result |
|---|---|
| `$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'; .\.tools\uv.exe python install 3.12` | Installed CPython 3.12.16; transient Windows rename warnings resolved |
| `.\.tools\uv.exe sync --extra dev` | Built editable VeriAgent and installed 25 packages |
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **29 passed**, 1 dependency deprecation warning, 5.49 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed after style fixes |
| `.\.venv\Scripts\ruff.exe format --check .` | 18 files already formatted |
| `.\.venv\Scripts\veriagent.exe demo` | Baseline false success; verification detects mismatch; recovery succeeds with 2 actions / 1 retry |
| `.\.venv\Scripts\veriagent.exe demo --scenario persistent_drop` | Recovery stops with honest failure after 3 actions / 2 retries |
| `.\.venv\Scripts\veriagent.exe demo --scenario transient` | Recovery succeeds with 2 actions / 1 retry; baseline and verification-only fail |
| `.\.venv\Scripts\veriagent.exe run 'Set ISSUE-1, ISSUE-2 to done' --silent-drops 1` | Verified success, 3 actions, 1 retry; both final statuses done with version 1 |
| `.\.tools\uv.exe sync --extra dev --locked --offline` | Resolved and checked 25 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and platform-independent wheel in `dist/` |

Actual default demo output:

```text
mode       claim  audit  false-success  actions  retries
baseline   True   False  True                 1        0
verify     False  False  False                1        0
recover    True   True   False                2        1
```

Generated raw evidence (ignored by Git) is under:

- `artifacts/40955b25310649429a589ca66af2629b/` — silent drop, three modes.
- `artifacts/ca7fc33c519b452c83bedd19a2b82f2a/` — persistent dropped writes.
- `artifacts/75716ad03f004be085dde02ce38fc11b/` — transient transport failure.

Each contains `comparison.json`, per-mode JSON/text traces, three state databases,
and the SQLite trace store. Tests independently exercise all four scenarios, including
clean execution, and the installed CLI in temporary directories.

## Environment-specific issues

The first sandboxed pytest run stopped progressing in the FastAPI test. A focused run
with `faulthandler_timeout=15` showed Windows asyncio blocked in the loopback socket
pair used to create its event loop. Both blocked runs were interrupted. The complete
suite then passed outside the execution sandbox; no test was skipped or weakened.

The initial sandboxed locked sync/build also failed to persist uv's interpreter cache
with Windows error 5. Repeating those exact offline commands outside the execution
sandbox succeeded. Initial downloading required network access; after installation,
the demo, tests, locked sync and build required no paid service or API credential.

The resolved Starlette version warns that its httpx TestClient support is deprecated
in favor of httpx2. The existing httpx path remains functional and all API assertions
passed. The warning is recorded, not suppressed. No live HTTP listener, real-model
provider, browser automation, statistical benchmark or external side effect was tested.

## Optional OpenAI planner milestone — 2026-11-19

The optional OpenAI SDK is now installed (`openai==2.54.0` in `uv.lock`). No live API
request was made. Tests use fake provider responses and an actual SDK client with an
in-memory HTTP transport. The baseline demo remains independent of the optional SDK.

| Command | Observed result |
|---|---|
| `.\.tools\uv.exe sync --extra dev --extra openai --link-mode copy` | Installed optional SDK and repaired editable package after an initial Windows access-denied error |
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **56 passed**, 1 existing Starlette deprecation warning, 16.30 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | 21 files already formatted |
| `.\.venv\Scripts\veriagent.exe demo` | Baseline false success, verification detects mismatch, recovery completes with 2 actions / 1 retry |
| `.\.tools\uv.exe sync --extra dev --extra openai --locked --offline` | Resolved and checked all 30 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and wheel; harmless hardlink-to-copy warning |

Raw demo traces are in `artifacts/c7d7567bc4684ab4b65f584a9d815780/`.

The first dependency update was interrupted by Windows denying replacement of editable
package metadata. This temporarily caused test-collection import errors. Retrying the
sync restored the installation. In the first SDK-boundary test run, a cold SDK start
exhausted the default ten-second agent budget. The boundary test now explicitly supplies
60 seconds; a separate test confirms that expired planning time prevents any writes.
The complete rerun passed. SDK imports, like the existing FastAPI tests, required execution
outside the restricted sandbox on this machine.

New coverage includes unauthorized target/status/tool/permission changes, invalid
dependencies, refusal, incomplete and malformed output, rate limits with no automatic
retry, token usage on rejected plans, unknown usage/cost, caller-provided pricing,
per-run accounting, request deadlines and endpoint pinning. This does not establish
model-specific schema acceptance, live model quality, or general injection resistance.

## Isolated smoke-test command — 2026-11-19

The next live milestone could not be executed: checks of configuration presence found
neither `OPENAI_API_KEY` nor `OPENAI_MODEL` set. No credential values were printed, and
no paid request was attempted. The reproducible command and its evidence capture were
implemented and validated offline instead.

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **66 passed**, 1 existing dependency deprecation warning, 18.00 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | 23 files already formatted |
| `.\.venv\Scripts\veriagent.exe smoke --output artifacts/smoke` | `smoke_passed=true`, mismatch detected, unrelated issues unchanged, 2 actions, 1 retry, 0 model calls |

Actual offline evidence is in `artifacts/smoke/122e1fb6fbbc45b897afab0123522569/`.
Tests cover fresh-state isolation, persisted trace/audit bundles, planning failures,
recovery exhaustion, collateral state changes, and completion without detected recovery.
CLI tests confirm offline defaults even with environment credentials, exit status 1 on
a failed check, and exit status 2 before creating artifacts when live configuration is
missing. The OpenAI adapter is also exercised with a simulated response to confirm one
planning request and retained token usage through the complete smoke path.

## Reviewed interpretation milestone — 2026-11-19

Added no-tool requirement proposals, a normalized review command and content-bound
execution approval. The offline interpreter supports a limited set of natural-language
verbs and mixed-status clauses. Optional OpenAI interpretation uses the same bounded
request and usage-accounting path as planning. Credentials are still absent; no live
model interpretation or paid API request was attempted.

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **115 passed**, 1 existing dependency warning, 18.20 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | Formatting check passed |
| `.\.venv\Scripts\veriagent.exe propose 'Close ISSUE-1 and start ISSUE-2' --output artifacts/reviewed-demo` | Saved an offline proposal for ISSUE-1 done and ISSUE-2 in_progress |
| `.\.venv\Scripts\veriagent.exe review <proposal-file>` | Printed both requirements and their canonical approval digest |
| `.\.venv\Scripts\veriagent.exe execute <proposal-file> --approve <reviewed-digest> --db <fresh-state-path> --traces <fresh-trace-path> --silent-drops 1` | Verified both target statuses, 3 write attempts, 1 recovery retry, no model calls |
| `.\.tools\uv.exe sync --extra dev --extra openai --locked --offline` | Checked all 30 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and wheel; harmless hardlink-to-copy warning |

The three CLI commands were executed sequentially in PowerShell; their actual proposal
and SQLite evidence are in `artifacts/reviewed-demo/a407de820e904d6c8f17173c2967e034/`.
Execution run ID: `d976d1487f3144f586c9d29df8221775`. The observed final state was
ISSUE-1 done/version 1 and ISSUE-2 in_progress/version 1, with ISSUE-3 unchanged.

The suite includes 24 hand-authored varied-instruction cases (12 accepted and 12 requiring
clarification), changed-content approvals, unknown fields, unauthorized targets, oversized
files, no-state/no-provider behavior on wrong approval, interpretation usage on rejected
outputs, and actual SDK interpretation serialization using an in-memory HTTP transport.
These tests establish fixture behavior, not live language accuracy or general injection
resistance. The digest detects changed content; it does not authenticate a reviewer.

## Dynamic tool-selection milestone — 2026-11-19

Added an optional dynamic engine while preserving the static default. OpenAI decisions
use strict function-call schemas; each action is independently checked against authorized
targets, statuses, tool permissions and repeat-write policy. The same paths are available
through the offline mock. No live API calls or actual model billing were used in validation.

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **158 passed**, 1 existing dependency warning, 30.57 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | Formatting check passed |
| `.\.venv\Scripts\veriagent.exe demo --engine dynamic` | Baseline false success with 2 actions; verification-only detects mismatch with 2 actions; recovery completes with 4 actions / 1 retry |
| `.\.venv\Scripts\veriagent.exe demo --engine dynamic --scenario persistent_drop` | Recovery terminates honestly after 6 actions / 2 retries |
| `.\.venv\Scripts\veriagent.exe smoke --engine dynamic` | Passing smoke, fault detected, unrelated issues unchanged, 4 actions / 4 decisions / 1 retry / 0 model calls |
| `.\.tools\uv.exe sync --extra dev --extra openai --locked --offline` | Checked all 30 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and wheel; harmless hardlink-to-copy warning |

Actual evidence is retained under:

- `artifacts/204f61e4ead74e49958d127f317899a8/` — dynamic three-mode dropped-write comparison.
- `artifacts/018b6b1fb28847abbe6636cc573afec6/` — dynamic persistent-fault comparison.
- `artifacts/smoke/88261319bfb34ec49836823fdda94d2e/` — final dynamic smoke result and traces.

New tests exercise paired dynamic scenarios, reviewed multi-status requirements, wrong
targets/statuses, repeated writes, denied/non-idempotent tools, decision/action/retry limits,
premature finish claims, late decisions, unreadable evidence and model-usage aggregation.
A simulated post-commit timeout completes through authoritative verification without
repeating the write. When evidence fails after a write, old verification is cleared and
the task is not claimed successful. Raw issue-title instructions do not enter provider
feedback. Actual SDK tests reject unknown/multiple/incomplete calls, extra permission
fields, missing call IDs and text-only success claims. Synthetic usage values test the
aggregation arithmetic; they are not actual model cost or reliability results.

The known Windows sandbox restriction still requires running the complete suite outside
the sandbox. Static tests continue to pass. No browser tools, hard process timeouts,
live-model quality results or general injection-resistance claims were added.

## Cumulative model-budget milestone — 2026-11-19

Added optional per-run OpenAI usage limits shared by static planning, dynamic decisions
and requirement interpretation. Output allowance is applied to the next request's token
ceiling; total tokens and estimated cost are observed thresholds that can overshoot in
the current request. No live requests or actual model-spend measurements were made.

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **194 passed**, 1 existing dependency warning, 33.30 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | Formatting check passed |
| `.\.venv\Scripts\veriagent.exe demo --engine dynamic` | Same expected three-mode results: baseline false success, verification failure, recovery success with 4 actions / 1 retry |
| `.\.venv\Scripts\veriagent.exe run --help` | Displays total-token, cumulative-output and estimated-cost limit options |
| `.\.tools\uv.exe sync --extra dev --extra openai --locked --offline` | Checked all 30 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and wheel; harmless hardlink-to-copy warning |

Actual default-mock comparison evidence is in
`artifacts/26b7ef8080a042c9a326670fae727067/`.

New tests cover zero-request rejection, a capped next-request output allowance, unusable
remainders, exact-threshold completion, observed-threshold overshoot, unknown usage,
rejected interpretation evidence, provider reuse/reset and price validation before client
construction. Real SDK transport fixtures confirm that the second request is not made
after a reached threshold. They also confirm that a synthetic over-cost response is
metered but cannot execute its proposed write. No-call rejections preserve the previously
returned model identifier and do not increment aggregate model calls. Synthetic token/cost
values validate control flow and arithmetic only; they are not actual billing results.

The existing Windows sandbox execution restriction and Starlette deprecation warning
remain unchanged. Budgets are per-run and local, not persistent account quotas or hard
guarantees of billed dollars. No live-model schema acceptance or quality was validated.

## Process-isolated tool milestone — 2026-11-19

Added an optional per-action worker for the fixed local sandbox tools, with parent-side
wait deadlines and termination/reaping. The default executor remains in-process. This
is deadline isolation rather than an OS security boundary or a whole-agent real-time
guarantee. No model API calls or external state-changing operations were used.

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **213 passed**, 1 existing dependency warning, 58.03 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | Formatting check passed |
| `.\.venv\Scripts\veriagent.exe run 'Set ISSUE-1 to done' --isolate-tools --action-timeout 3 --timeout 30 --db artifacts/isolation-first/state.sqlite --traces artifacts/isolation-first/traces.sqlite` | Verified success, 1 worker action, no retry |
| `veriagent run 'Set ISSUE-1 to done' --isolate-tools --action-timeout 2 --timeout 30 --hang-before-commit 1 --db <fresh-before-db> --traces <trace-db>` | Actual hung worker terminated; verified completion after 2 writes / 1 retry |
| `veriagent run 'Set ISSUE-1 to done' --isolate-tools --action-timeout 2 --timeout 30 --hang-after-commit 1 --db <fresh-after-db> --traces <trace-db>` | Actual hung worker terminated after its write; verified completion with 1 write / 0 retries |
| `.\.venv\Scripts\veriagent.exe smoke --engine dynamic --isolate-tools --action-timeout 3` | Passing smoke, 4 worker actions / 1 retry / 0 model calls; unrelated issues unchanged |
| `.\.tools\uv.exe sync --extra dev --extra openai --locked --offline` | Checked all 30 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and wheel; harmless hardlink-to-copy warning |

The two hang demos used the installed `.venv\Scripts\veriagent.exe` and fresh databases;
their actual stdout reports (`before.json`, `after.json`) and shared trace store are in
`artifacts/isolated-deadlines/685cd4802ad24fb8b929c6fd27240720/`. Final dynamic process-smoke
evidence is in `artifacts/smoke/bddcdf9ab4774ee08fb8ab137c6c1aab/`.

Tests independently poll the actual launched processes to confirm exit. They cover real
60-second injected hangs cut short by a 2-second parent deadline, before/after-commit
ambiguity in both engines, retry exhaustion, reserved fault counters, denied actions
before launch, worker errors, environment filtering, UTF-8 titles and interrupted-parent
cleanup. Simulated unreapable-worker cases confirm a terminal internal failure with no
success or retry, including when persisted status already matches the task.

During implementation that unconfirmed-cleanup case exposed a false-success possibility:
matching state could otherwise override the cleanup failure. A trusted observation safety
flag and early termination checks in both engines fixed it; the final complete suite
includes the regression. No actual unreaped process was left by the worker tests.

The complete suite still runs outside the restricted Windows execution sandbox. Process
creation, OS scheduling and cleanup can exceed the nominal wait deadline; model calls,
verification and trace persistence are not forcibly cancelled by this adapter. Only
Windows was validated, and no arbitrary process-tree containment claim is made.

## Offline adversarial evaluation milestone — 2026-11-19

Added the packaged `phase2-boundaries-v1` corpus and `evaluate-safety` command. All responses
are scripted, application faults are controlled, and the final SQLite oracle bypasses
the injected tool/verifier behavior. No model provider, credential or external operation
was used. Prior process-execution changes remained local and were preserved.

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests/test_safety_evaluation.py -q -o faulthandler_timeout=20` | 41 focused tests passed in 11.08 seconds |
| `.\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=20` | **254 passed**, 1 existing dependency warning, 62.63 seconds |
| `.\.venv\Scripts\ruff.exe check .` | All checks passed |
| `.\.venv\Scripts\ruff.exe format --check .` | Formatting check passed |
| `.\.venv\Scripts\veriagent.exe evaluate-safety` | **24/24 expected outcomes matched**, 0 protected false-success claims, 0 unauthorized dispatches, 0 unrelated status/version changes, 0 context canary leaks, 0 model calls |
| `.\.tools\uv.exe sync --extra dev --extra openai --locked --offline` | Checked all 30 packages successfully |
| `.\.tools\uv.exe build --offline` | Built source distribution and wheel; harmless hardlink-to-copy warning |
| Wheel archive inspection with Python `zipfile` | Confirmed `veriagent/scenarios/safety.json` is packaged with all 24 cases |

The final default run is saved in
`artifacts/safety/84197aa78c2c4aaab376c0b2c2d46414/`. Canonical suite SHA-256:
`50ae908afef917652391acba042b2221d353474c6afea4932350e05d3d1c487c`.
Each case retains normalized fixtures, initial/final status snapshots, traces, captured
provider contexts and the declared-versus-actual comparison. The root result includes
source fingerprint, runtime/dependency metadata and selected case IDs.

Two baseline controls are separately labeled; one intentionally produces a false-success
claim. Reproducing that expected failure is not counted as protected-mode reliability.
Tests deliberately disable authorization, lie through the verifier, leak a marker, skip
attack observation and alter a fixture label. Each manipulation makes the evaluator
report failure. No such regression remains enabled in the production code.

These observations establish behavior only for the finite scripted corpus. They are not
real-model attack resistance, language accuracy, a general safety guarantee, statistical
reliability evidence or actual billing measurements. Existing worker and SDK tests also
passed in the complete run; live-provider acceptance remains pending credentials and
explicit use of the API.

## Request-diagnostic correction — 2026-11-19

Inspected the user's saved smoke result at
`artifacts/smoke/fa4d01715ac945ab973f215fc0692190/result.json`. It reported failure before
any tool action: one OpenAI attempt, unknown usage and `output_usage_unknown` in the
budget ledger. Its model was `gpt-6.1-terra`; elapsed agent time was approximately 1547 ms.
This does not identify the original API cause or establish successful live integration.
The old sanitized trace did not retain a diagnostic, so none is inferred or fabricated.

Corrected error precedence so a real request failure remains the primary planning error
while its budget ledger stays stopped. Added safe diagnostic category, HTTP status and
an allowlisted API error code to reports/traces and interpretation results. Messages,
response bodies, headers, keys and unknown error codes are excluded.

Executed:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provider_diagnostics.py tests/test_openai_provider.py tests/test_budgeting.py tests/test_dynamic_openai.py tests/test_interpretation.py -q -o faulthandler_timeout=20
```

Result: **141 focused tests passed in 12.49 seconds**. Ruff lint, formatting and Git
whitespace checks also passed. In-memory SDK tests cover authentication, permission,
rate/quota, schema and missing-model errors in both engines, with a relevant usage limit
enabled; they verify the original category survives and secret-bearing error messages
never reach traces. No paid retry was made. The user must run a fresh request in the
terminal holding their credentials to obtain an actual diagnostic.

The next user-run result (`artifacts/smoke/12f1d02fcefc4feca7d7156abf4196b3/result.json`)
reported HTTP 400 with no recognized code, zero tool actions and a planning failure.
Its original message had not been stored, so its precise cause remains unconfirmed.
Added HTTP-400-only redacted message detail and an allowlisted parameter field, keeping
schema context while removing configured credentials, credential-like tokens, quoted
values and control characters. The request schema was inspected locally and compared
with the official Structured Outputs format; no live schema-acceptance claim is made.

The same focused command then passed **143 tests in 12.58 seconds**, including detail
redaction and non-400 message suppression. Ruff and whitespace checks passed. No new
live request was issued by the assistant; a fresh user-run request is needed to obtain
the new detail field.

A subsequent screenshot still had an empty detail because extraction had assumed the
standard JSON message shape. Expanded extraction to plain text, alternate JSON fields
and the SDK fallback message, retaining the same credential/value redaction. Added
`body_format` for the SDK-normalized body shape. The original message from that request
was not stored and cannot be reconstructed; its precise 400 cause remains unknown.

Real SDK transport tests now exercise plain text, JSON `detail`, JSON string `error`,
and empty responses. They confirm that SDK normalization can unwrap a JSON string error
to a text body. The focused provider/budget/interpretation suite passed **147 tests**;
lint and whitespace checks passed. No live request was issued by the assistant.

Metadata check follow-up: added `check-provider` for one model metadata GET without generation. Actual SDK with mocked HTTP transport verifies success and empty 400/401/404 responses, a single GET, and no secret in output. Provider diagnostic tests: 24 passed; Ruff checks passed. Live metadata access remains unverified pending the user's terminal run.

### First successful live static smoke — 2026-11-19

Inspected the user-run artifact `artifacts/smoke/95d7f7b2a9484c5bb90b94a3909c94b9/result.json`.
The OpenAI static engine with `gpt-6.1-terra` passed the silent-drop smoke: fault detected,
one recovery attempt, two tool actions, verified final state and independent audit passed.
ISSUE-1 changed from open/version 0 to done/version 1; ISSUE-2 and ISSUE-3 stayed unchanged.
One generation request reported 386 input and 107 output tokens (493 total), elapsed
5.5 seconds. No caller prices were configured, so no dollar cost is inferred. Provider
diagnostic and model-budget stop reason were null. This validates one static scenario,
not dynamic model behavior or statistical reliability. The assistant read saved artifacts
and did not retrieve credentials or issue further generation requests.

The user also demonstrated a successful metadata check. Earlier malformed credential,
401 and 429 attempts are historical failures; subsequent success does not establish each
earlier response's precise cause.

Post-live regression check: full suite outside the Windows sandbox passed **278 tests in
57.38 seconds**, with one existing Starlette/httpx deprecation warning. The sandboxed run
was interrupted after stalling near completion; its output is not counted as a pass.
Ruff checks and git whitespace checks passed. No further live generation was run.

### First successful live dynamic smoke — 2026-11-19

Inspected `artifacts/smoke/1167005c35bc4e29a139cffc7f8575f3/result.json` after the user's
terminal run. Dynamic smoke passed with fault detection, one recovery attempt, three
tool actions, three model calls and 1,834 reported total tokens in approximately 7.219
seconds. Final verification and independent audit passed; untargeted issues stayed
unchanged and the provider diagnostic was null. This is one controlled live dynamic
scenario, not a statistical reliability comparison. The visible PowerShell error came
from concatenating `Format-List` and the next pasted command; saved evidence confirms
the dynamic run itself passed. No additional generation request was needed.

### Live reviewed multi-target dynamic trial — 2026-11-19

The first live interpretation of 'Please resolve ISSUE-1 and begin work on ISSUE-2'
requested clarification ('Should ISSUE-1 be marked done?'); review emitted no approval
digest. This is a conservative clarification outcome, not a successful interpretation
of that wording. The subsequent explicit objective 'Set ISSUE-1 to done and set ISSUE-2
to in_progress' produced the exact expected requirements, no clarification, and digest
`c390f06e8ca806cfad9c3f2d2d0e4ac28eddce57c568ade0a52462cb0087f31a`.

Inspected proposal `artifacts/proposals/8b8a7d19f03e4d9ba0551d90c1d51a87/proposal.json`
and run `b9621815b9254b53b797b205022082ca` in `artifacts/traces.sqlite`. The trace's
requirements_review digest matches the reviewed proposal. Dynamic execution reported
verified success, five actions, one recovery attempt, five generation calls, 3,601 tokens
(3,373 input / 228 output), and approximately 12.219 seconds. Interpretation separately
used one call and 341 tokens; the successful proposal/execution workflow used six calls
and 3,942 tokens total, excluding the earlier clarification attempt. Cost was not estimated.

A separate read-only SQLite query against
`artifacts/reviewed-36a05e72610b4bfd9261bb0852919415.sqlite` confirmed ISSUE-1 done/version 1,
ISSUE-2 in_progress/version 1, and ISSUE-3 open/version 0. Exported proposal, digest, ordered
trace events and final rows to
`artifacts/reviewed-validation/b9621815b9254b53b797b205022082ca/evidence.json`.
No additional live requests were issued. One successful explicit task and one conservative
clarification do not establish broad interpretation accuracy or general agent reliability.

### Repeated-trial benchmark infrastructure — 2026-11-19

Added offline-default `benchmark` CLI: fresh state per mode/repetition, fixed four-scenario
matrix, rotated mode order, per-run bounds, direct read-only SQL oracle, source hashes,
model configuration without credentials, durable per-run evidence and atomic partial
summaries. Nominal Wilson intervals are reported per scenario/mode with independence
assumptions and explicit deterministic-mock limitations. Fixed requirements mean zero
interpretation calls; unknown execution usage remains null. Live batches require an
explicit provider and cumulative per-run output allowance. Provider diagnostics stop a
batch without submitting remaining runs.

Full regression suite passed **290 tests in 64.35 seconds**, one existing Starlette/httpx
warning. After the final batch-stop change, **13 benchmark tests passed in 10.73 seconds**,
including the added provider-error stop/close test. Ruff lint/format and whitespace checks
passed. The sandbox's long temporary paths caused initial SQLite test-open failures;
verification outside the sandbox resolved those. A test fixture also initially omitted
required verification evidence; corrected that fixture before the reported passing runs.

Ran default 36-run offline dynamic matrix at
`artifacts/benchmarks/98a521df48214861a8529cae29c340c7/benchmark.json`. All clean groups
succeeded 3/3. Recovery succeeded 3/3 for single drops and transient faults; persistent
drops remained unsuccessful. Baseline falsely claimed success 3/3 for each drop scenario;
verify/recover had zero false successes in this matrix. No untargeted status/version
changes occurred. These repeated deterministic outcomes check implementation, not live
model reliability. No paid benchmark or additional live request was made.

### Varied fixed-task corpus — 2026-11-19

Added six packaged task/initial-state cases: single completion, paired completion, mixed
statuses, reopening, already-satisfied and partially-satisfied goals. Requirements are
specified directly in the fixture, separate from provider parsing. Validated known/unique
IDs and full seeded initial statuses. `benchmark --task` selects cases; `--all-tasks`
selects the corpus. Task count is included in preflight's 120-run ceiling, before provider
construction or artifact writes. Manifest schema 2 records selected cases and corpus hash;
summaries group by task/scenario/mode. Each run records initial rows and configured and
remaining fault counters. Direct SQL audits check every target and compare untargeted
rows with their starting values, including added/deleted IDs.

Focused benchmark suite: **20 passed in 21.11 seconds**. Full regression suite:
**298 passed in 86.26 seconds**, one existing Starlette/httpx deprecation warning.
Ruff lint/format and whitespace checks passed. Tests cover missing/unsatisfied second
targets, unrelated row additions/deletions, reopening from nondefault initial states,
unused faults on already-satisfied dynamic goals, and preflight task-count limits.

Ran 72 offline dynamic trials (6 cases × 4 scenarios × 3 modes) at
`artifacts/benchmarks/e621f94eb9574dd0a38ef12403a553ec/benchmark.json`. No untargeted
changes and no false successes outside baseline. Recover mode achieved goals in all
clean, single-drop and transient cases. Persistent drops prevented initially-unsatisfied
goals from completing; already-satisfied goals succeeded without consuming faults or
claiming recovery. These are deterministic regression outcomes, not stochastic model
reliability estimates or proof of equal realized fault exposure across engines. No live
request or paid batch was made.

### Indexed write-fault schedules — 2026-11-19

Added benchmark-only `ScheduledSandbox` and explicit second-write silent drop,
second-write transient error, and first-two-write drop profiles. Original default
scenarios remain unchanged. Indexed writes include retries and no-op assignments;
reads do not advance the schedule. Preconditions precede injection; a timed-out or
missing-target attempt keeps its event undelivered without moving it to a later index.
Counter and indexed faults cannot be mixed. Agents receive ordinary tool observations,
not the hidden fault schedule. Result artifacts record planned events, every reached
write position/target, actual injections and unused events; summaries include exposure
counts instead of assuming equal faults from scenario labels.

Focused indexed-fault and benchmark tests: **31 passed in 25.29 seconds**. Tests verify
second-target partial commits, transient non-commit, no-op indexing, retry persistence,
precondition failure without shifted delivery, invalid schedules, recovery under both
engines and unused second-write events on single-target goals.

Ran 18 offline dynamic pair_done trials (three indexed scenarios, two repetitions,
three modes) at `artifacts/benchmarks/e878e09041de4423a9b6acc923eeafc0/benchmark.json`.
Recovery succeeded 2/2 for each scenario. Verify/recover had zero false successes.
For two_drops, baseline and recover each delivered both indexed events per trial;
verify stopped after the first mismatch, leaving event 2 unused. This observed difference
confirms that matching profile labels alone does not establish equal fault exposure.
No live generation request was issued. Ruff lint/format and whitespace checks passed.

Full regression suite after indexed scheduling: **309 passed in 99.25 seconds**, with
one existing Starlette/httpx deprecation warning. No additional API usage occurred.

### Local benchmark metric review — 2026-11-19

Reviewed fixed task initial states/targets, independent final-state audits, no-op/unused
fault exposure, and summary definitions against EVALUATION.md. Found that the reported
false-success and recovery rates used all trials only. Preserved those fields and added
false_success_given_claim and recovery_given_fault_mismatch with explicit denominators.
The latter conditions on delivered pre-commit faults affecting an unmet authorized
write, not every failure type. Zero denominators return null rates/intervals. Instrumented
pre-fault local status separately from agent verification; documented its latency overhead
and adapter-specific unchanged-state assumption. Updated stale protocol wording about
individual live checks while retaining that no stochastic live benchmark has run.

Focused benchmark/metric/fault tests: **36 passed in 28.38 seconds**. They cover differing
all-run/conditional denominators, no-claim undefined rates, fault-mismatch eligibility,
no-op injections without recovery opportunity, and measured second-target recovery.

Ran six offline static trials (already_satisfied and pair_done, single-drop profile,
three modes) at `artifacts/benchmarks/4a332ae285e6412f812ce26bcfa695ac/benchmark.json`.
All already-satisfied trials had zero eligible fault mismatches and null conditional
recovery. pair_done baseline falsely claimed success; verify made no claim and its
conditional false-success rate was null; recover succeeded with one eligible opportunity.
No paid request was issued. This was an implementation review by the implementing
assistant, not independent external review or external corpus validation.

Full regression suite after metric corrections: **314 passed in 80.28 seconds**, one
existing Starlette/httpx deprecation warning. Ruff lint/format and whitespace checks passed.

### First Phase 3 local browser slice — 2026-11-20

Added the optional `browser` dependency (locked Playwright 1.65.2), packaged local issue
HTML/JS, fixed DOM browser tools and browser-smoke CLI. Every trial owns a loopback server,
fresh headless Chromium/context and fresh SQLite state. Request routing restricts browser
context requests to fixed paths/methods on that origin. Existing action authorization,
idempotency/recovery budgets and independent SQLite verification remain in force. Model
selectors/scripts/arbitrary URLs and personal profiles are not supported.

The page deliberately trusts a successful write acknowledgment optimistically. Real-browser
tests confirmed DOM status done while a dropped commit leaves SQLite open; reloading reads
the actual status. Both engines detected and recovered the fault. Tests also exercise
literal title rendering, missing issues, transient pre-commit errors, zero/stalled action
deadlines, blocked external navigation and honest smoke failure without retries. Evidence
captures refreshed final DOM and screenshots; final capture failure is tracked separately.

Focused browser/existing-smoke checks passed **27 tests in 8.90 seconds** before adding
the stalled-UI and no-recovery checks. Full suite with `VERIAGENT_BROWSER_TESTS=1` then
passed **334 tests in 99.00 seconds**, one existing Starlette/httpx deprecation warning.
Ruff lint/format and whitespace checks passed. Built the wheel offline and inspected it:
HTML, JS and benchmark corpus resources are included. Existing project import and installed
package versions were verified after installation.

Dependency sync initially hit Windows access denied while removing editable project
metadata. Installed optional dependencies with no-install-project and restored the editable
project via uv pip install --no-deps --editable .; subsequent import/version, wheel and full
suite checks passed. No application data or user browser profiles were removed.

Actual dynamic CLI smoke saved
`artifacts/browser-smoke/b5d205afb8fa4bda92b5a68dc79a05cb/result.json`: smoke passed,
injected mismatch detected, recovery performed, final version 1, unrelated issues unchanged,
zero model calls and capture_complete true. Browser version 159.0.8154.6. Visually inspected
the refreshed after screenshot: ISSUE-1 done/version 1. The prior initial implementation
smoke at `6356d343820a40189ec1dda3468b5236` also passed. No live-model browser trial or paid
request was made. This validates a fixed local fixture, not arbitrary-site autonomy or a
browser/network security sandbox. Benchmark external review remains pending.

### Reviewed multi-target browser backend — 2026-11-20

Added `execute --tool-backend browser`, leaving sandbox execution as default. The parsed
immutable approved proposal supplies all browser targets; invalid digests and browser/
worker-isolation combinations are rejected before provider/state/browser creation.
Browser execute defaults to five-second action deadlines; existing sandbox execute
retains one second unless explicitly overridden. The new evidence helper captures initial
and final rows via read-only SQL, per-target DOM/screenshots and the approved proposal,
digest, budget, original agent result and ordered trace events.

The post-cleanup browser audit separately checks all target statuses, target titles and
entire untargeted rows, including added/deleted IDs. Original claims are retained; overall
browser_execution_passed and CLI exit status reject collateral changes or unconfirmed
cleanup even if internal target verification passed. Baseline verification remains null
and its independent audit never feeds execution. Bounded setup metadata is retained if
no agent report was produced. Browser shutdown errors are normalized without raw messages.

Focused reviewed-browser, interpretation and browser suites: **72 passed in 23.08 seconds**.
Real Chromium checks cover static/dynamic two-target recovery, review-before-action trace
ordering, zero model calls despite ambient test credentials, default deadline selection,
collateral changes, baseline false claims and cleanup uncertainty. Unit/preflight checks
cover all-target/title/add-delete audits and early rejection without provider/state/browser
side effects.

A fresh offline dynamic CLI demonstration saved
`artifacts/reviewed-browser-trials/e3823dc771ef419582f041ff08e0a267/evidence/ce98ff4e72c84188be7ff1218cf97da6/result.json`.
It passed with six browser actions, one recovery and zero model calls. Read-only audit
confirmed ISSUE-1 done/version 1, ISSUE-2 in_progress/version 1, unchanged untargeted data
and unchanged target titles. No live-model browser request was issued.

Full regression suite with real Chromium checks enabled: **344 passed in 108.50 seconds**,
one existing Starlette/httpx deprecation warning. Ruff lint/format and whitespace checks
passed. No paid model calls were made.

### Browser stale-DOM and post-commit ambiguity — 2026-11-20

Added optional clean/silent_drop/stale_dom/lost_ack profiles for browser smoke and
reviewed browser execution. The post-commit profiles fire once, only after a durable
status-changing commit. stale_dom renders the previous status despite persistence;
lost_ack returns HTTP 503 after persistence (not literal network packet loss). Browser
write observations now reflect rendered status instead of assuming it equals the request.
Bounded DOM/action and application commit/HTTP event logs are saved separately; hidden
profile/commit metadata stays outside provider context. CLI rejects non-browser scenarios
and mixed non-clean profile/counter flags before side effects. JS/HTML line endings now
use the same explicit LF convention as the project's other source types.

Corrected smoke fault_detected to exclude initial unsatisfied dynamic verification:
only mismatches after mutation observations count. Browser ambiguity smoke instead requires
actual anomaly evidence, a single durable application write, no replay/recovery, final
verified state and unchanged unrelated issues. Zero events lost are required for the
scenario evidence check. Already-satisfied/no-op writes do not consume post-commit profiles.

Reviewing multi-target ambiguity exposed a dynamic-agent edge case: a completed write
that reported an error could spend retry budget or stop verify/zero-retry execution while
other targets remained unfinished. The agent now continues when authoritative evidence
confirms that mutation's target completed, without allocating a retry to it. Unsafe worker
cleanup still stops before this rule. Unit tests cover transient/timeout observations in
verify/recover modes with zero retries, plus real-browser static/dynamic two-target lost-ack
execution with exactly one write and one version increment per target.

Initial browser/ambiguity/existing-smoke suites passed **50 tests in 28.14 seconds**.
After the multi-target fix, focused ambiguity/dynamic/reviewed-browser/smoke suites passed
**65 tests in 30.89 seconds**. They also check fault-label exclusion, no-op/pending profiles,
event persistence, DOM-versus-SQL disagreement and no unnecessary replay.

Final offline dynamic demonstrations:
- `artifacts/browser-smoke/719315b229304385a5c75bc88efb4a72/result.json` (stale_dom).
- `artifacts/browser-smoke/28be5f69449a4262b1e45114f5675933/result.json` (lost_ack).

Both passed with observed anomaly, no post-write SQLite mismatch, one committed write,
version 1, zero recovery attempts, unchanged unrelated issues and zero model calls.
The early lost_ack demonstration `955a86122c4e40f59ba43a689a2d7399` predates the initial-
verification counting fix; its fault_detected flag is superseded by these final runs.
No paid browser/model request was issued.

Full regression suite with real browser checks enabled: **361 passed in 123.86 seconds**,
one existing Starlette/httpx deprecation warning. Ruff lint/format and whitespace checks
passed. No live-model browser request was made.

### Pending-response browser action timeouts — 2026-11-20

Added timeout_before_commit and timeout_after_commit profiles. The fixture holds an actual
HTTP response while Playwright waits for the UI save result, so the browser's real action
deadline produces the timeout observation. A trusted fixture callback releases the handler
only after that observation; no commit-state hint is given to the planning provider.
The pre-commit request rejects without writing on release; the post-commit request has
already committed. Browser/server cleanup also release held handlers without acquiring
the held write lock. A ten-second safety release bounds abandoned waits, and incompatible
action deadlines are rejected before provider/artifact/state creation. Event metadata
records held/released response state and release reason; safety/cleanup release alone is
insufficient to pass a timeout smoke.

Focused timeout/ambiguity/reviewed-browser suites: **40 passed in 50.62 seconds**. Unit
checks observe SQLite while responses are held, prove no late pre-commit write, exercise
cleanup release without deadlock, distinguish safety release and validate early budget
rejection. Real Chromium tests cover static/dynamic before/after-commit smoke, honest
failure without retries, and dynamic reviewed mixed_status/reopen/partial_satisfied cases
using the fixed corpus's starting states. They verify one final version increment per
changed target and unchanged unrelated data.

Final dynamic mock CLI demonstrations:
- `artifacts/browser-smoke/25bfc4c19b4b4b5e9e075daf36b6216b/result.json` (before commit):
  smoke passed, two application attempts, one commit, one recovery, final version 1.
- `artifacts/browser-smoke/2c8b50c48de04e94be20f8c902e3ebce/result.json` (after commit):
  smoke passed, one application attempt/commit, zero recovery/replay, final version 1.
Both recorded release_reason action_timeout and zero model calls. An earlier post-commit
smoke at `41c233193ca84988ba4ad83952d1ecbf` also passed before the final thread-publication
ordering cleanup. These are browser action deadlines while HTTP is pending, not a real
remote-service cancellation guarantee or an OS TCP timeout. No API credits were used.

Full regression suite with real Chromium checks enabled: **378 passed in 182.36 seconds**,
one existing Starlette/httpx deprecation warning. Ruff lint/format and whitespace checks
passed. No paid model/API requests were made.
# Offline browser corpus batches — 2026-11-20

Added the mock-only `browser-batch` command with fresh trial state, fixed corpus
requirements, bounded selections, atomic partial manifests and grouped claim/audit/exposure
metrics. Focused tests: **8 passed**, including four real browser trials. Pure tests cover
invalid preflight selections, interruption evidence and empty conditional denominators.

Final CLI evidence:
`artifacts/browser-batches/9bbd6bb2cfb84fd096512f2fcf60549a/manifest.json`.
Twelve dynamic mock trials crossed single_done/already_satisfied, clean/silent_drop/
timeout_after_commit and baseline/recover. The dropped-write single_done baseline claimed
success but failed the SQL audit; recover passed with one retry. Post-commit timeout left
the correct goal state in both modes, but the baseline did not claim success. Already-
satisfied recover trials made no writes and never counted the selected fault as exposure.
This is a control check, not a requirement that every baseline outcome pass.

Full Chromium-enabled suite: **386 passed in 155.89 seconds**, with the existing
Starlette/httpx deprecation warning. The final additional summary count fields were also
checked by the seven pure batch tests and refreshed 12-trial CLI evidence. Ruff format,
lint and whitespace checks passed. No paid API/model calls were made. These deterministic
local trials do not establish stochastic reliability or independently reviewed task quality.
## Browser expected-outcome matrix — 2026-11-20

The offline `evaluate-browser` CLI completed **42/42 matching controls** with exact
coverage: six task cases × six profiles in dynamic recovery mode, and six single-target
baseline controls. Final evidence:
`artifacts/browser-controls/99ea6520549547d1961c8683d8ce6a25/controls.json`.
An initial matrix at `8ec80c6ea516412082d2edafac06ce6b` also matched all 42 before
the final duplicate/missing coverage check was added.

Recovery cases matched explicit fault exposure, audited outcomes, one commit per changed
target and retry/attempt counts. Already-satisfied cases made no writes. Expected baseline
false claims and committed-error outcomes remain distinct from successful task execution.
Unit checks deliberately alter audit results, commit counts, exposure, retry counts and
event completeness; mismatches are rejected. Missing and duplicate matrix coverage cannot
pass; interruptions preserve completed controls.

Full regression suite with Chromium enabled: **397 passed in 169.44 seconds**, with
the existing Starlette/httpx deprecation warning. Ruff formatting/lint and whitespace
checks passed. No paid API/model calls were made. This finite deterministic fixture matrix
does not establish independently reviewed corpus quality or stochastic reliability.
## Indexed browser faults — 2026-11-20

Added second_drop, second_lost_ack and second_timeout_before/after_commit schedules.
The indexed CLI evaluation matched **24/24 controls** with exact coverage; evidence:
`artifacts/browser-controls/333be8f8cc3847898f7ab49ff3172f23/controls.json`.
Two-changing-target cases injected at attempt 2; zero/one-changing-target cases retained
an unused fault. Commit, retry, attempt and final/collateral audit expectations matched.

Focused regression checks: **31 passed in 24.63 seconds**. Real browser tests cover both
engines across all four profiles on pair_done, with a single first-target write and final
version 1 per target. Pure tests cover read/no-op/missing-target schedule positions and
deliberately shifted injection evidence.

The original matrix still matched **42/42 controls** at
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-controls/169f52b0f50f4590aa8426a3964d3e6d/controls.json`.
An earlier rerun under OneDrive stopped on Windows access-denied replacing a manifest
(`artifacts/browser-controls/dbfd4a0e87cf4057b9b95e8b2015fa53`); it is not counted as a
completed evaluation. The successful rerun used the other writable local directory.

Full Chromium-enabled regression suite: **409 passed in 178.24 seconds**, one existing
Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks passed.
No paid model/API calls were made; results remain finite deterministic fixture checks.
## Multi-event browser recovery — 2026-11-20

The `evaluate-browser --multi-event` CLI matched **12/12 controls**, covering pair_done
and mixed_status with second_two_drops/second_drop_then_lost_ack and retry limits 0/1/2.
Evidence:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-controls/a1b2b999060046dba27fca337e76c004/controls.json`.
Expected exhausted-retry failures retained first-target done/version 1 and second-target
open/version 0, with unchanged unrelated data. Two drops required two retries; the
drop/committed-error schedule required one retry and did not replay the committed write.
Full event positions/kinds and unused event counts were retained.

Focused tests: **35 passed in 34.00 seconds**, including both engines with zero and
sufficient retries. Tests deliberately alter partial progress/version/collateral evidence
and verify that an ineligible earlier event does not shift a later event.
The existing indexed CLI matrix still matched **24/24 controls** at
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-controls/34dd3fe7a17a425999d9c763c5383d95/controls.json`.

Full Chromium-enabled regression suite: **421 passed in 186.96 seconds**, with the
existing Starlette/httpx deprecation warning. Ruff formatting/lint and whitespace checks
passed. No paid API/model calls were made. The original matrix scope remains unchanged;
this increment reran the indexed matrix and browser regressions, not the full original
42-control CLI matrix. Results remain finite local mechanism checks.
## Offline browser evidence audits — 2026-11-21

New reviewed browser bundles include unsigned SHA-256 inventories; `audit-browser`
rechecks files, reviewed requirements, saved state, application replay and trace/report
consistency without opening a browser, calling a model or modifying the bundle.
Focused tests: **15 passed in 8.08 seconds**. Cases remove required files/captures, alter
capture bytes, reseal inconsistent state/digests/reports/events, duplicate snapshot rows,
attempt external filenames and exceed file limits. Real Chromium runs confirm that both
successful recovery and honestly reported partial failure can have valid evidence.
The first focused run found Windows CRLF trace rendering differences; normalization was
corrected while exact-byte hash checks remain unchanged.

Final CLI bundle:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-evidence-validation/075a99ff72864209bc07078424b94ec1/trial-001/7e4d630b84fe48a9818d1fd6226b38d3`.
The pair_done second_two_drops dynamic trial passed, and a subsequent offline CLI audit
reported evidence_passed/task_passed true. CLI JSON summaries are retained at
`artifacts/browser-evidence-batch.json` and `artifacts/browser-evidence-audit.json`.

Full Chromium-enabled suite: **436 passed in 204.86 seconds**, with the existing
Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks passed.
No paid API/model calls were made. These audits compare saved evidence, not the current
live database; an unsigned inventory cannot prevent coordinated rewriting of all files.
## Whole-batch browser evidence reconciliation — 2026-11-21

New manifests retain relative bundle directories and inventory hashes. The read-only
`audit-browser-batch` command checks exact selection coverage, unique run IDs,
current-corpus tasks/initial states, trial configuration, nested bundle evidence and
reconstructed grouped summaries. Counter-based silent drops now record explicit
application-event injection labels for offline exposure reconstruction.

Focused regressions: **33 passed in 25.86 seconds**, including existing batch/ambiguity
tests. New cases cover moving a batch without modifying files, removed/duplicate trials,
altered rows/summaries, interrupted status, changed corpus hash, escaped relative paths,
missing bundles, inventory changes and copied evidence reused as another repeat.

Final CLI batch evidence:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-batch-audit-validation/c2cc7d6297e34f4dba288f55ab3bb3b5`.
The saved baseline/recover silent-drop batch passed the offline audit. Recomputed summaries
preserved one exposed baseline false claim and one exposed successful recovery. CLI JSON
is retained at `artifacts/browser-batch-audit-validation.json` and
`artifacts/browser-batch-audit-result.json`.

Full Chromium-enabled suite: **448 passed in 204.35 seconds**, with the existing
Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks passed.
No paid model/API calls were made. Batches/manifests are unsigned; this checks saved
evidence consistency, not authenticated provenance or a new live-database query.
## Complete browser control-evaluation audits — 2026-11-21

New evaluations bind relative nested batches to manifest hashes and retain relative
control/trial associations. `audit-browser-controls` checks all nested batch/trial
evidence, fixed matrix budgets/selections, cross-batch unique run IDs and regenerated
expected outcomes/mismatches. Evidence validity and control expectation success remain
separate; accurately recorded expectation mismatches need not invalidate evidence.

Focused checks: **25 passed in 3.78 seconds**. Audit tests cover the 42/24/12 matrix
shapes, moved/read-only artifacts, changed pass flags or expectations, missing/duplicate
controls, altered manifest hashes, escaped paths, interrupted status, conflicting matrix
flags, invalid nested evidence, changed retry budgets and honestly reported mismatches.
The updated generation tests initially hit the sandbox's Windows temporary-path limit;
rerunning outside that sandbox passed all 11 generation checks.

Final 12-control multi-event CLI evaluation and successful offline audit:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-controls-audit-validation/5bb6db817cc8457ea4470bb85467df7b`.
Both evidence_passed and controls_passed were true. CLI JSON is retained at
`artifacts/browser-controls-audit-validation.json` and
`artifacts/browser-controls-audit-result.json`. No paid model/API calls were made.

Full Chromium-enabled suite: **462 passed in 213.68 seconds**, with the existing
Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks passed.
Audits remain unsigned saved-evidence consistency checks, not authenticated provenance.
## Compact browser control review — 2026-11-21

Added `review-browser-controls` with shared text/JSON views derived from a complete
offline control audit. It distinguishes expected and unexpected task failures from
expectation mismatches, retains relative evidence references and withholds outcome
totals for invalid evidence or inconsistent trial mapping. Compact evidence-gap display
is bounded to 100 entries with an explicit truncation marker.

Focused tests: **10 passed in 1.06 seconds**. They cover expected/unexpected failures,
unexpected success, an expected failure with another mismatch, partial evidence,
bounded gaps, missing/duplicate/unknown trial outcomes, both CLI formats, read-only audit
input handling and missing evidence exit behavior without constructing a provider.

Both CLI formats were run against the saved evaluation at
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-controls-audit-validation/5bb6db817cc8457ea4470bb85467df7b`.
The report showed valid evidence, 12/12 matched controls, six successful tasks, six
expected task failures and zero unexpected failures/expectation mismatches. Outputs:
`artifacts/browser-control-review.txt` and `artifacts/browser-control-review.json`.
This reused saved evidence; no browser launches or paid API/model calls were needed
for the report commands.

Full Chromium-enabled regression suite: **472 passed in 207.71 seconds**, with the
existing Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks
passed. Reports remain unsigned deterministic fixture reviews, not reliability estimates.
## Browser action/decision boundaries — 2026-11-21

Added the separate `evaluate-browser --budget-boundaries` dynamic mock matrix: pair_done
and mixed_status with action limits 2/3/4 and decision limit 8, plus decision limits 2/3/4
and action limit 8. All **12/12 controls matched**, with four successful tasks and eight
expected budget failures. Lower limits retained first-target done/version 1 and
second-target open/version 0; four steps completed both targets without a budget failure.
No fault injection, recovery, collateral changes or replay was expected.

The complete evaluation passed offline audit and review at:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-budget-validation/9467a81502be4ba78d3345a89c3bd5fd`.
CLI JSON/text outputs are retained at `artifacts/browser-budget-validation.json`,
`artifacts/browser-budget-audit.json` and `artifacts/browser-budget-review.txt`.
The prior multi-event evaluation at `browser-controls-audit-validation/5bb6db817cc8457ea4470bb85467df7b`
under the same writable artifact root also still passed its offline audit; output is
`artifacts/browser-budget-compatibility-audit.json`.

Focused tests: **35 passed in 5.01 seconds**, covering overrun counts, false claims,
missing terminal budget failure, lost progress, distinct resource identities, exact
completion, matrix flag conflicts, review limit display and the fourth supported audit
matrix shape. No paid API/model calls were made.

Full Chromium-enabled suite: **482 passed in 208.30 seconds**, with the existing
Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks passed.
These exact-step boundaries apply to the fixed local mock flow, not arbitrary model runs.
## Browser fault/recovery budget boundaries — 2026-11-21

Added `evaluate-browser --fault-budget-boundaries`: 24 dynamic mock controls across
pair_done/mixed_status, second_drop/second_lost_ack and action or decision limits 4/5/6.
All **24/24 matched**, with 16 successful tasks, eight expected budget failures and no
unexpected failures or expectation mismatches. The complete evaluation passed offline
audit and review.

For drops, limit 4 stopped before recovery admission, limit 5 admitted one recovery but
only completed its read, and limit 6 completed the repair. Both partial cases retained
first-target version 1 and second-target version 0. Post-commit errors completed at four
steps without replay or recovery at every selected limit. No production agent-loop
changes were required.

Evidence:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-fault-budget-validation/22f45ca9dc8a41c2ad4aaf8faf6b9b6b`.
CLI JSON/text outputs are retained at `artifacts/browser-fault-budget-validation.json`,
`artifacts/browser-fault-budget-audit.json` and `artifacts/browser-fault-budget-review.txt`.
The prior clean boundary evaluation at `browser-budget-validation/9467a81502be4ba78d3345a89c3bd5fd`
under the same writable artifact root also passed its offline audit; output is
`artifacts/browser-fault-budget-compatibility-audit.json`.

Focused tests: **37 passed in 3.82 seconds**, including both resource limits, premature
recovery admission, unfinished repair claims, committed-error replay rejection, flag
conflicts and the fifth supported matrix shape. No paid API/model calls were made.

Full Chromium-enabled regression suite: **495 passed in 213.52 seconds**, with the
existing Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks
passed. These are fixed local mechanism checks, not stochastic reliability estimates.
## Pre-satisfied browser budget boundaries — 2026-11-21

Added `evaluate-browser --satisfied-budget-boundaries`: already_satisfied and
partial_satisfied, clean/second_drop, and action or decision limits 1/2. All **16/16
controls matched**, with 12 successful tasks, four expected budget failures and no
unexpected failures or expectation mismatches. Offline audit and review also passed.

Already-satisfied goals took zero agent actions/decisions and preserved version 0;
initial verification/evidence reads still occurred outside those action counts. Partial
goals preserved the seeded completed target at version 0, read without writing at limit 1,
and completed the remaining target with one write at limit 2. All selected second-write
faults remained unused, with exposure false and one pending event. No recovery was expected.

Evidence:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-satisfied-budget-validation/ded6a8db0a75483083931acae06622e7`.
CLI outputs: `artifacts/browser-satisfied-budget-validation.json`,
`artifacts/browser-satisfied-budget-audit.json` and `artifacts/browser-satisfied-budget-review.txt`.
The previous fault-budget evaluation at `browser-fault-budget-validation/22f45ca9dc8a41c2ad4aaf8faf6b9b6b`
under the same writable artifact root still passed its offline audit; compatibility output
is `artifacts/browser-satisfied-budget-compatibility-audit.json`.

Focused tests: **37 passed in 5.78 seconds**, covering unwanted actions/commits, altered
seeded versions, falsely claimed exposure, unused-event counts, premature success,
one-write completion under both resource limits, flag conflicts and the sixth audit
matrix shape. No paid API/model calls were made.

Full Chromium-enabled regression suite: **507 passed in 209.37 seconds**, with the
existing Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks
passed. Counts remain finite local mechanism checks, not stochastic reliability estimates.
