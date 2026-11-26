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
## Offline multi-matrix suite review — 2026-11-21

Added `review-browser-suite` for one to six distinct saved evaluations. Each input is
fully re-audited; matrix identities and unique run IDs come from validated evidence.
Suite coverage lists present/missing types, rejects duplicate matrix/run use and withholds
totals on evidence or required-selection failure. Text/JSON formats preserve separate
successful tasks, expected/unexpected task failures and expectation mismatches.

Focused tests: **23 passed in 0.92 seconds**, including the existing report checks.
New cases cover partial/all-six selection shapes, --require-all behavior, duplicate
matrices/directories, reused/missing run IDs, invalid evidence, bounds before auditing,
both CLI formats, read-only audit input handling and selection-failure exit behavior.

Both CLI formats reviewed the saved fault-budget and pre-satisfied budget evaluations
under the writable artifact root:
- `browser-fault-budget-validation/22f45ca9dc8a41c2ad4aaf8faf6b9b6b`
- `browser-satisfied-budget-validation/ded6a8db0a75483083931acae06622e7`

The valid partial selection showed **2/6 matrices**, **40/40 matched controls**, 28
successful tasks, 12 expected failures and zero unexpected failures/mismatches. The four
missing matrix types were explicit. --require-all on those same two inputs returned
exit 1, reported required_matrices_missing and withheld totals. No missing matrix was run.
Outputs: `artifacts/browser-suite-review.txt`, `artifacts/browser-suite-review.json` and
`artifacts/browser-suite-required-all.txt`. No browsers or paid API/model calls were needed
for these review commands; full six-matrix empirical CLI validation is not claimed.

Full Chromium-enabled regression suite: **520 passed in 215.81 seconds**, with the
existing Starlette/httpx deprecation warning. Ruff format/lint and whitespace checks
passed. Aggregates remain unsigned deterministic fixture totals, not reliability estimates.
## Declarative browser matrix catalog — 2026-11-21

Consolidated matrix names/flags, ordered batches, resource limits, CLI descriptions/counts,
legacy flag requirements and budget-metadata requirements in immutable catalog definitions.
CLI parsing/dispatch, execution, auditing and suite coverage now consume that catalog;
expected task/fault outcomes remain separately specified.

All six normalized ordered-batch definitions were compared with the preceding committed
implementation and matched exactly. Their fingerprints are pinned in regression fixtures.
Focused checks: **61 passed in 4.95 seconds**, including catalog fingerprints, independent
task/count checks, frozen definitions/spec isolation, invalid/conflicting flags, legacy
defaults, CLI dispatch/help, existing control generation, all audit shapes and suite checks.
After deriving remaining suite help/limit text from catalog size, the catalog/suite checks
also passed **33 tests in 1.33 seconds**. Ruff format/lint and whitespace checks passed.

A fresh catalog-driven 16-control pre-satisfied evaluation passed, as did offline review:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-catalog-validation/378f366e8d9d4b878d86abffd372f69c`.
It retained 12 successful tasks, four expected failures and zero mismatches. Outputs:
`artifacts/browser-catalog-validation.json` and `artifacts/browser-catalog-review.txt`.
The two previously saved fault-budget/pre-satisfied matrices still reviewed as a valid
40-control partial suite with unchanged outcomes; compatibility JSON is
`artifacts/browser-catalog-compatibility-suite.json`. No paid API/model calls were made.

Full Chromium-enabled regression suite: **540 passed in 212.54 seconds**, with the
existing Starlette/httpx deprecation warning. The final catalog-derived help/limit text
was additionally checked by the focused catalog/suite run above. This refactor preserves
the finite local matrix contract; it does not establish stochastic reliability.
## Versioned browser matrix-contract identities — 2026-11-21

New controls.json schema-2 evaluations require a version-1 matrix_contract header.
Its canonical SHA-256 covers the corpus fingerprint, selected matrix/flag, ordered
batches, full budgets, mock/dynamic configuration and independent expected outcomes.
Paths, run IDs, timestamps and display-only descriptions are excluded. Parent audits
compare the current identity before nested interpretation; review and suite text expose
contract status. Legacy schema-1 files without a header remain labeled legacy_missing.

Focused checks: **59 passed in 6.32 seconds**. They cover deterministic identities for
all six matrices, declaration/expectation/corpus drift, display-only stability, read-only
matched audits, legacy compatibility, malformed/unknown-version/wrong-matrix identities,
required-field removal and explicit mismatch reporting before nested reads. The initial
focused run exposed an incomplete synthetic nested-audit fixture; it was completed and
the focused suite passed.

A fresh schema-2 pre-satisfied evaluation passed all **16/16 controls** and offline review
showed matrix contract matched:
`C:/Users/SAMSUNG/.codex/visualizations/2026/11/17/01a1e7ea-e64f-7f61-b1e4-c299e01e75b8/browser-contract-validation/80631766492847c6b75f4cf7b9885037`.
Outputs: `artifacts/browser-contract-validation.json` and `artifacts/browser-contract-review.txt`.
An isolated copied header with an altered digest returned exit 1, contract mismatch and
withheld counts (`artifacts/browser-contract-negative-review.json`); original evidence was
not changed. The previous fault-budget evaluation still reviewed as valid/legacy_missing
with 24/24 matching controls (`artifacts/browser-contract-legacy-review.txt`). No paid
API/model calls were made. Contract identities are unsigned, not authorship signatures.

Final Chromium-enabled regression suite: **559 passed in 229.00 seconds**, with the
existing Starlette/httpx deprecation warning. The final run is retained at
`artifacts/browser-contract-tests.txt` after an earlier session's final output became
unavailable during continuation. Ruff format/lint and whitespace checks passed.
## Read-only installed contract inspection — 2026-11-21

Added `inspect-browser-matrices` with compact text/JSON output for all installed matrices
or a unique named subset. It exposes flags, control/batch counts, ordered selections/full
budgets and the same versioned identity used by evaluation writing/auditing. It constructs
no provider, launches no evaluation/browser and writes no files itself.

Final focused verification: **47 passed in 2.14 seconds**, covering the new inspector,
existing catalog and contract compatibility tests. New cases check all six/130 declared
controls, identity equality, selection order/budgets, invalid preflight selections,
provider/evaluation rejection sentinels, read-only CLI behavior, both formats and duplicate
argument errors. Ruff lint/format and whitespace checks passed. The full Chromium suite
was not repeated for this command-only increment.

Actual CLI output is retained at `artifacts/browser-matrix-inspection.txt` and
`artifacts/browser-matrix-inspection.json`. All six declarations were listed, and the
inspected satisfied-budget identity exactly matched the saved schema-2 evaluation at
`browser-contract-validation/80631766492847c6b75f4cf7b9885037` under the writable artifact
root. The printed 130 controls were declarations, not newly executed trials. No browser
launches or paid API/model calls were needed for this inspection validation.
## Optional strict contract review — 2026-11-21

Added --require-contract to evaluation audits, single reviews and suite reviews. The
caller-selected policy requires status matched and rejects legacy_missing before nested
interpretation, while default legacy compatibility remains explicit. Policy selection
is reported separately from --require-all matrix coverage and never rewrites artifacts.

Focused verification: **96 passed in 9.10 seconds**, covering strict matched acceptance,
legacy early rejection, default compatibility, count withholding, propagation to every
selected evaluation, CLI text/JSON behavior, independent full-suite selection, and the
existing contract/audit/review/suite/catalog/inspection checks. Ruff format/lint and
whitespace checks passed. The full Chromium suite was not repeated for this read-only
review-policy increment.

Actual CLI checks used the saved schema-2 16-control evaluation at
`browser-contract-validation/80631766492847c6b75f4cf7b9885037` and the schema-1 fault-budget
evaluation at `browser-fault-budget-validation/22f45ca9dc8a41c2ad4aaf8faf6b9b6b` under the
writable artifact root. Strict matched review passed; strict legacy review returned
exit 1 with legacy_missing; default legacy review still passed. A mixed strict suite
returned exit 1 and withheld aggregate counts.

Outputs: `artifacts/browser-strict-contract-review.txt`,
`artifacts/browser-strict-contract-legacy.json`, `artifacts/browser-strict-default-compatibility.json`
and `artifacts/browser-strict-suite-review.json`. No browser launches or paid API/model
calls were needed. Strict matching of unsigned identities does not authenticate provenance.
## Suite contract-policy coverage — 2026-11-21

Suite reports now retain input-level contract_coverage counts for matched, legacy_missing
and unverifiable identities. Counts are independent of task outcomes, distinct matrix
coverage and strict-policy acceptance; each evaluation also records its category while
retaining exact identity status. Matching headers never override failed nested evidence.

Focused verification: **63 passed in 3.10 seconds**, including existing contract, strict
policy, suite and single-review checks. New cases cover mixed metadata/outcomes, strict
legacy rejection with retained diagnostics, all unsupported/unknown status categories,
matching headers with failed evidence, duplicate input versus matrix denominators and
CLI JSON coverage. Ruff lint/format and whitespace checks passed. The full Chromium suite
was not repeated for this read-only report increment.

Actual mixed schema-2/legacy suite review showed two inputs: matched=1, legacy_missing=1,
unverifiable=0. Default review still showed 40/40 matched controls, 28 successes and 12
expected task failures across 2/6 matrix types. Strict review returned exit 1 and withheld
outcomes while retaining the same metadata coverage. Outputs:
`artifacts/browser-contract-coverage.txt` and `artifacts/browser-contract-coverage-strict.json`.
The review reused saved evidence; no browser launches or paid API/model calls were needed.

### Suite output schema — 2026-11-21

Added version-2 suite output validation and a checked-in generated JSON Schema.
Ruff passed; 77 focused offline suite, schema, contract-policy, contract-coverage,
control-audit and review tests passed. Corruption cases cover strict types, old versions,
unknown fields, metadata drift, inflated totals, policy flags and outcome detail counts.
Tests ran outside the sandbox to avoid Windows temporary path-length failures.

Actual CLI review of saved modern and legacy evaluations retained 40 matched controls,
28 successful tasks and 12 expected task failures. Strict contract review exited 1,
withheld totals and retained identity coverage (one matched, one legacy input).
Results are saved in `artifacts/browser-suite-schema-v2.json` and its `-strict` variant.
No browser trials or paid API calls were run; the Chromium suite was not rerun for this
read-only report change. JSON Schema structural checks do not replace runtime
cross-field validation or underlying evidence audits.

### Exported suite validation command — 2026-11-21

Added `validate-browser-suite` with text/JSON results, bounded UTF-8 loading and
runtime schema checks. Ruff passed and 92 focused offline review tests passed, including
15 new cases for input bounds, malformed/ambiguous JSON, field corruption, CLI exits,
BOM compatibility, accepted rejection reports and no evidence/provider access.
Tests ran outside the sandbox to avoid Windows temporary path-length limits.

Actual CLI validation accepted both saved version-2 exports: the 40-control mixed suite
and its strict-policy rejection report. Acceptance means report consistency only;
no referenced evidence was reopened and no underlying success was inferred. No browser
trials or paid API calls ran, and the full Chromium suite was not rerun for this change.

### Complete evaluation portability — 2026-11-21

Four Chromium-enabled portability tests passed in 31.95 seconds. A fresh mock-provider
16-control pre-satisfied budget matrix was generated in a CLI subprocess, then relocated
with original absolute paths unavailable. Strict nested audit and suite review passed:
16 matched controls, 12 successful tasks and four expected task failures. All evidence
file hashes remained unchanged across reviews. Three independently copied corruptions
(missing capture, changed manifest bytes, escaping batch binding) rejected evidence and
withheld totals without rewriting remaining files.

The initial in-process generation attempt encountered Windows access denial on rename;
the final regression finishes generation in a separate CLI process before relocation.
This validates completed-artifact portability rather than in-process handle release.
No paid API calls were used. The complete Chromium suite was not rerun for this test-only
increment. All 92 focused offline review regressions also passed; Ruff, formatting and
diff checks passed.

### Bounded evidence archive transfer — 2026-11-21

Added offline archive/restore CLI commands with strict-contract options and staged audit
before publication. All 118 focused tests passed in 50.33 seconds: 21 archive tests,
five Chromium-enabled portability tests and 92 existing offline review regressions.
The real 16-control evaluation round-trip preserved every file hash and remained
strictly auditable after restoration. Its suite still contained 16 controls.

Archive regressions covered traversal, absolute/drive/backslash paths, reserved names,
case-insensitive duplicates, links, resource limits, invalid evidence, existing outputs,
source changes after initial audit, CLI success/failure and staging cleanup. Archive unit
tests isolate nested audits; the Chromium round-trip exercises real nested auditors.
Ruff, formatting and diff checks passed. Tests ran outside the sandbox to avoid Windows
temporary path-length limits. No paid API calls were made. The full Chromium suite was
not rerun for this isolated transfer workflow; five relevant browser integration tests ran.

### Archive metadata inspection — 2026-11-21

Added `inspect-browser-archive` with text/JSON output and shared directory preflight.
All 132 focused tests passed in 50.70 seconds: 14 new metadata inspection regressions,
21 archive transfer tests, five Chromium portability tests and 92 offline review tests.
The real 16-control evidence archive round-trip remains valid under the shared checks.

New cases verify read-only operation without payload access or auditing, declared size
summaries, portable names, case-insensitive duplicates, file/parent conflicts, shared
resource limits, CLI output/exit behavior and corrupt-payload scope. The corrupt ZIP
passes metadata inspection but fails restoration CRC checks with no destination left.
Ruff, formatting and diff checks passed. Tests ran outside the sandbox to avoid Windows
temporary path-length limits. No paid API calls ran. The full Chromium suite was not
rerun; the five relevant browser integration tests were included in the focused run.

### Offline workflow validation review — 2026-11-21

Reproduced and fixed two boundary gaps: strict Pydantic Literal fields accepted numeric
or boolean equivalents for schema versions, and ZipInfo truncated names at NUL before
portable path validation. Output models now require exact integer version types, and
archive preflight rejects normalized original names before opening any payload.
Ten version-type regressions cover suite and nested reviews; one raw ZIP regression
covers both inspection and restoration, including no-payload-access and cleanup checks.
The generated structural JSON Schema remains unchanged.

All 41 targeted schema/inspection tests passed. The complete Chromium-enabled suite then
passed: **670 passed, one existing Starlette/httpx deprecation warning, in 271.04 seconds**.
The durable log is `artifacts/offline-workflow-review-tests.txt`. Ruff, formatting and diff
checks passed. Tests ran outside the sandbox to avoid Windows temporary path-length
limits. Browser runs used the local mock provider; no paid API calls were made.

### Legacy archive compatibility — 2026-11-21

Added nine compatibility regressions without production-code changes. All 71 focused
archive, inspection, portability, strict-policy and identity-coverage tests passed in
62.64 seconds. This includes six Chromium-enabled portability tests and the new real
legacy archive round-trip. The fixture derives schema-1 header omission from a freshly
generated 16-control evaluation while preserving its complete nested sealed evidence.

Default transfer retained legacy status and exact bytes; strict archive creation and
restoration rejected without publishing output or leaving staging directories. Schema-2
missing headers and explicit mismatches were rejected under both policies. CLI exits,
source/archive immutability and downstream default/strict suite results were checked.
Ruff, formatting and diff checks passed. Tests ran outside Windows sandbox path limits.
No paid API calls ran. The full suite was not rerun for this test-only increment; its
previous 670-test run remains the last complete-suite result.

### Archive filesystem failure handling — 2026-11-21

All 55 focused archive tests passed in 14.77 seconds, including 11 new injected failure
regressions. Archive creation and restoration were checked for extraction write failures,
staged audit failures, publication permission failures and concurrent output-file creation.
A restore directory created during audit was preserved, and missing output parents were
not implicitly created. Sources and incoming archives retained their exact hashes/bytes;
private staging was removed after the handled failures.

No production-code changes were needed. Ruff, formatting and diff checks passed. Tests
ran outside Windows sandbox path limits. Chromium was not rerun for this test-only
increment; the previous full result remains 670 passed, followed by the separate legacy
compatibility checks. No paid API calls ran. Abrupt process termination and filesystem
refusal to delete staging were not simulated.

### Offline evidence operator guide — 2026-11-21

Added `docs/OFFLINE_EVIDENCE.md` and linked it from README and the browser guide.
Checked all ten documented command help entries against the installed CLI, verified guide
file links and validated both existing saved suite exports (accepted mixed suite and
strict-policy rejection report). Both exported reports passed internal validation as
expected; this does not re-audit their underlying evidence. Exit-status explanations
were checked against CLI dispatch behavior, including expected task/control failures.
Diff checks passed. No production code or tests changed, so the test suites were not
rerun for this documentation-only increment. No browser trials or paid API calls ran.

### Documented operator workflow smoke — 2026-11-21

All 62 focused portability and archive tests passed in 93.26 seconds. The new
Chromium-enabled operator smoke runs ten command invocations through separate CLI
processes over a fresh, relocated 16-control mock-provider evaluation: catalog inspection,
control and suite review, BOM-compatible report validation, archive creation/inspection,
restoration, restored suite review, required-full-coverage rejection and validation of
that rejection report. The sequence includes two report-validation invocations.

Restored totals match the original (16 controls, four expected task failures), contract
coverage matches and source/restored hashes plus ZIP bytes remain unchanged. Partial
coverage correctly returns exit 1, while its consistent exported rejection report
validates with exit 0. Ruff, formatting and diff checks passed. No production code
changed. The full suite was not rerun for this test/docs-only increment; seven relevant
Chromium portability tests were included. No paid API calls ran.

### Research validation priority review — 2026-11-21

Added a local research-review packet and unsigned machine-readable baseline snapshot.
Verified the corpus hash, all six initially-unmet-target counts (1/2/2/1/0/1), three
implemented modes, six matrix identities totaling 130 controls, 12 selected source hashes
and document links against installed code/data. The packet prioritizes external corpus/
fault review and prospective comparator/ablation design before broader reliability claims.
It does not record independent approval, new measurements or a live study.

No production code or test cases changed; no test suites, browser trials or paid API
calls were run for this documentation/snapshot increment. Diff checks passed. External
review, self-reflection comparison and repeated stochastic evidence remain pending.

### Prospective offline comparison specification — 2026-11-21

Added `OFFLINE_COMPARISON.md` and `review/offline-comparison-plan.json`, bound to the
previous baseline snapshot. Verified all source/corpus hashes, six tasks, four scenarios,
three modes and two batches of 72 planned rows (144 total). Exercised both exact argument
vectors through CLI dispatch with `repeated_trials` intercepted before execution, and
confirmed mock provider selection and matching per-run budgets. Verified document links
and diff checks. This was argument/configuration validation, not a benchmark dry run.

No benchmark trials, browser trials, test suites or paid API calls ran. No production
code changed. The specification is prospective; measured outcomes, external approval,
self-reflection and budget-controlled ablations remain pending.

### Specified offline comparison execution — 2026-11-21

Executed the pinned mock comparison: completed 72 static and 72 dynamic runs. Original
OneDrive static attempt exited 2 on WinError 5 atomic replacement; its committed manifest
has 38 rows, temporary manifest 39, and 39 saved result files. Preserved that attempt and
its hashes separately. Restarted both complete batches in the writable local artifact
root, with output path as the only argument amendment. The prospective plan JSON remains
unchanged. Recorded artifacts and per-condition outcomes in the new results JSON/report.

Verified exact 72-condition coverage per engine, 144 unique run IDs, corpus/provider/
budget matching, per-run result equality, recomputed summaries, trace presence and final
SQLite row equality via read-only queries. Independently recomputed requested target
status outcomes, untargeted status/version changes and false claims. No untargeted changes
were observed. Partial-satisfied static one-shot faults were ineligible no-op exposures;
dynamic one-shot faults affected unmet targets and recovery used one attempt. Results
remain stratified and descriptive; no stochastic or causal reliability inference is made.

Verified plan/manifest hashes, document links and diff checks. No production code or tests
changed, and no test suites were rerun for this recorded experiment. All calls used the
mock provider with zero model tokens; no browser trials or paid API calls ran. Raw traces
and databases remain local rather than bundled in the committed results record.

### Comparator and ablation design — 2026-11-21

Added a prospective design separating trusted verification from observation-only
self-reflection, describing proposed phase admission and resource/exposure controls.
Confirmed existing Mode values remain baseline/verify/recover and inspected actual
agent/verifier behavior. Read-only trace spot-checks for partial_satisfied/silent_drop/
recover found static 1 completed verification/2 evidence rows/2 actions versus dynamic
3 verifications/6 evidence rows/4 actions, with ineligible versus eligible fault exposure.
These quantities are not interchangeable resource units or an equal-exposure contrast.

Verified document links and diff checks. No implementation, tests, benchmark trials,
browser trials or paid API calls changed/ran. The design does not implement a reflection
arm, new caps or fault profiles; external review and stochastic study design remain pending.

### Saved-trace verification work ledger — 2026-11-24

Added a pure bounded ledger for dedicated single-run traces. Reconciled all 144 saved
comparison traces against terminal reports and original benchmark rows: 182 completed
trusted verification calls, 284 known target evidence rows, zero recorded verification
errors. Derived records bind comparison/implementation/trace hashes and keep task,
scenario, engine and mode labels. No interrupted-attempt rows were pooled.

All 85 focused ledger, benchmark, fault, metric and dynamic-engine tests passed in
56.03 seconds, including 16 new cases. Tests cover unknown partial error work (including
zero completed calls), final-evaluator exclusion, strict sequence/counter reconciliation,
wrong identity, missing terminal reports and task/evidence disagreement. The initial
sandbox run encountered seven known long-path SQLite failures; the final run outside
the sandbox passed. Ruff, formatting, document links, derived hashes and diff checks
passed. No browser or paid API calls ran. Regression tests exercised mock benchmarks;
the recorded 144 comparison outcomes were read, not rerun. No execution policy changed.

### Standalone verification admission — 2026-11-24

Added strict optional call/target-row limits and a one-in-flight reservation ledger.
Reservations precede prospective work, denied requests do not mutate state, errors
retain allowances and leave total actual work unknown. Exact completed target-row
accounting, ticket identity, stale/double settlement and detached snapshots are enforced.
The module remains disconnected from StateVerifier, agents, Budget and CLI.

All 77 focused admission, saved-trace and dynamic-engine tests passed in 12.38 seconds,
including 28 new admission tests. Ruff, formatting, documentation links, existing derived
implementation hash and diff checks passed. Existing comparison traces/outcomes and
execution policies were unchanged. No new comparison batches, browser trials or paid API
calls ran. Adapter-level proof of no read on denial remains the next integration gate.

### Opt-in trusted-verifier adapter — 2026-11-24

Added BudgetedStateVerifier as a separate explicit adapter; ordinary StateVerifier,
existing agents, Budget and CLI are unchanged. It reserves original unique targets before
any trusted database connection, validates complete evidence before settlement and records
admitted errors/cancellation as unknown work without refund. Final evaluation stays separate.

All 124 focused adapter, admission, trace-ledger, dynamic and benchmark/fault/metric tests
passed in 54.10 seconds, including 11 new adapter cases. Connection/query spies prove no
SQLite connection on denial and read-only exact-query behavior on admission. Actual invalid
second-target status causes partial-read failure with consumed reservation and null total
work; missing files, missing targets, satisfied targets, incomplete returns, exceptions and
cancellation are covered. Post-denial final verification is independent.

Ruff, formatting, document links, pinned baseline source hashes and diff checks passed.
Broader tests ran outside Windows sandbox path limits. Regression mock trials ran; no new
comparison batch, browser trial or paid API call ran. Agent denial mapping and durable
admission traces remain pending; no bounded-oracle comparison result is claimed.

### Explicit agent verification admission and traces — 2026-11-24

Both engines now recognize an explicitly supplied BudgetedStateVerifier. A fresh adapter/
ledger binds to the original task/run, configuration records its limits and verification
requests emit admitted/completed/error/denied state snapshots. Denial is an honest budget
failure with no success claim and no stale verification snapshot. Actual admitted errors
remain internal failures with unknown partial work. Ordinary verifiers and CLI defaults
retain their original path without admission trace fields.

All 104 focused agent/admission/adapter/trace/dynamic tests passed in 20.13 seconds,
including 16 new opt-in agent cases. Coverage includes no oracle read on initial denial,
post-repair denial despite satisfied final state, independent evaluator access, unlimited
parity across engines/modes, baseline zero use, initial satisfaction, run binding and
admitted errors. The complete Chromium-enabled suite then passed: **762 passed, one
existing Starlette/httpx deprecation warning, in 437.08 seconds**. A portability evidence
read triggered a 30-second faulthandler diagnostic; it resumed and the suite completed
without failures. The full log is `artifacts/agent-verification-admission-tests.txt`.

Ruff, formatting, document links, historical verification-work implementation hash and
diff checks passed. The broad run used the approved outside-sandbox environment to avoid
Windows temporary path limits. Mock benchmarks/browser integration tests ran; no paid API
calls or new comparator study ran. Historical baseline source fingerprints are retained
as historical records, not silently updated to the changed agent implementation.

### Offline admission-trace reconciliation — 2026-11-24

Added a pure opt-in admission reconciler. It validates ordinary work first, then replays
strict limit/counter snapshots, admitted/completed/error/denied transitions, paired outcome
events and terminal report semantics. Snapshot comparisons preserve bool/int/float type
distinctions. Consistent quota failures pass evidence reconciliation without being called
task success; partial error-path work remains unknown.

All 140 focused reconciliation, agent, adapter, admission, work-ledger and dynamic tests
passed in 23.91 seconds, including 36 new cases. Actual traces cover both engines, three
modes, unlimited, zero-call and one-row limits, plus admitted errors. Corruptions exercise
counter/type drift, removed phases/outcomes with sequence renumbering, wrong targets,
changed limits, invalid denial reasons, false success and execution after denial.

Ruff, formatting, document links, historical work implementation hash and diff checks
passed. No agent or CLI behavior changed in this increment. The complete suite was not
rerun after its previous 762-test pass; the new reconciler is isolated and focused tests
exercise its integration. No browser trials, comparison batches or paid API calls ran.

### Prospective bounded-oracle specification — 2026-11-24

Added BOUNDED_ORACLE_COMPARISON.md and a machine-readable 72-condition plan. Selections
are three fixed tasks, clean/silent-drop scenarios, baseline/verify/recover and zero-call,
one-call, one-row/unlimited profiles, dynamic mock only. Per-cell expected denial phase,
reason, final target success, claim, failure and verified-success values are recorded
prospectively. The predicted inventory is 28 denials, not a measured result.

Validated unique exact condition coverage, budget schema, every quota profile, source/
corpus hashes, document links and diff checks. Replayed only abstract ledger reservations
to confirm initial/post-write denial boundaries and reason codes; no agent, tool or oracle
was executed. No production code, test suites, comparison outcomes, browser trials or paid
API calls changed/ran. The explicit runner and outcome collection remain pending.

### Bounded-oracle runner and recorded execution — 2026-11-24

Added the repository-local `research.run_bounded_oracle` runner, outside the product CLI
and pinned product source tree. It validates the reviewed mock-only plan before output,
uses fresh state/provider/ledger/adapter/traces per cell, preserves mismatches and partial
attempts, and stores raw reports, SQLite/JSON traces, final state and admission replay.
All 148 focused runner/admission/agent/adapter/work/dynamic tests passed in 23.43 seconds,
including eight new runner cases for invalid plans, unexpected predictions and interruption.

Executed all 72 pinned conditions once in a new local non-OneDrive UUID artifact tree.
Every expectation and admission check passed: 16 initial denials, 12 post-write denials,
42 completed trusted checks and 55 known target reads. Ten denied runs had independently
satisfied final targets, with claims correctly withheld. No collateral changes or verifier
errors were observed. These are descriptive inventories, not pooled policy estimates.

Independently checked exact coverage, 72 unique IDs, every raw file hash, manifest/result/
report equality, trace SQLite/JSON equality, fresh replay/live-state equality and final
SQLite target/collateral outcomes. Plan and runner hashes and links match the recorded
JSON. Ruff, formatting and diff checks passed. Source/plan predictions were not changed
after observing results. No product agent code changed; the full Chromium suite was not
rerun for this repository-local runner. Tests and the experiment used MockProvider, with
zero model tokens, no browser trials and no paid API calls. Raw artifacts remain local;
the committed record is not a complete portable raw-evidence release.

### Portable bounded-oracle raw evidence — 2026-11-24

Added repository-local packaging/audit utilities and committed-candidate raw ZIP at
`docs/evidence/bounded-oracle-2026-11-24.zip`: 424,810 bytes, 436 files and all 72 recorded
runs. It includes the bound manifest, plan, corpus, generating runner source, state/trace
SQLite files, JSON traces, reports, admission replays and per-trial results. ZIP/checker
fingerprints and relocation validation are recorded separately. The runner source inside
the ZIP is read as bytes and never executed.

The real package passed staged validation and was copied to its repository location;
its re-audit passed with original-source file and SQLite access explicitly blocked.
All 28 denials, per-condition expectations, exact coverage, bound hashes, report/result/
trace equality, quota/budget configuration, fresh admission replay and independent final
SQL outcomes reconciled. Original absolute manifest paths were not followed.

All 165 focused package/runner/admission/agent/adapter/work/dynamic tests passed in
35.13 seconds, including 17 new package cases. Coverage includes relocation, corrupt
payloads, bad external hashes, unbound/escaping members, no overwrite/publication on
failure, preflight before payload access, excessive/duplicate plan dimensions and strict
expected outcome types. Shared archive bounds and SQLite read-only instruction budgets
are used. Ruff, formatting, package/checker checksums, links and diff checks passed.
Tests ran outside Windows sandbox path limits. No new comparison, browser trial or paid
API call ran; fixed mock regression conditions exercised the harness. Product code and
historical predictions/results were unchanged. No authenticated provenance or stochastic
reliability claim is made.

### Mock-only reflection prototype — 2026-11-24

Added a separate ReflectionAgent/MockReflectionProvider and typed phase/context/report
contracts, without extending existing Mode, RunReport or CLI. Execution finish proposals
or recoverable failures request at most two corrective admissions within shared budgets.
Correction uses fresh ordinary reads and read-back after writes; repeated writes need a
new read and safe policy. Original/final claims, admissions and write attempts stay separate.
No StateVerifier or live provider is accepted. Final claims are not trusted verification.

The 850-test Chromium-enabled regression collection passed with one existing Starlette/
httpx warning in 347.08 seconds. Two additional multi-target boundary tests were added
after that collection, followed by strict report-counter/version input tests. The final
focused run passed all 65 tests in 18.74 seconds, including all 40 reflection tests and
runner/package compatibility fixtures. Final changes after the broad run were report
integer-type guards and tests; normal execution logic was unchanged.

Cases cover clean/drop/transient/post-commit timeout behavior, persistent faults, admission
and shared caps, exact eight-decision multi-target completion versus honest repair budget
failure, authorization, stale/unsafe replay, late decisions, unsafe cleanup, hidden context,
canary exclusion and provider restriction. A spoofed ordinary read produces a success
claim with an independently failed SQL audit; that false claim is deliberately preserved.

Historical source plans were not rewritten. Only temporary test-plan source fingerprints
were refreshed because the new source module changes the inventory. Confirmed the old
execution plan rejects drift and the released 72-run/436-file ZIP still audits. Ruff,
formatting, document links and diff checks passed. No comparison study or paid API call
ran; the broad suite exercised mock/browser regressions. A metered LLM reflection arm,
external review and a prospective common-corpus comparison remain pending.

### Prospective reflection common-corpus specification — 2026-11-26

Added REFLECTION_COMPARISON.md and a machine-readable plan for 96 assigned conditions:
six tasks, four default fault scenarios and dynamic baseline/verify/recover plus the
separate mock reflection prototype. One repetition per condition, shared 8-action/
8-decision/2-admission caps and explicit unlimited trusted ledgers for dynamic arms do
not imply equal information or cost. Reflection gets no trusted verifier or quota object.

Verified all 96 unique keys, 24 complete blocks, fixed rotating arm positions (six per
arm/position), budgets, mode/report mapping, quota shapes, source/corpus hashes and document
links. Independent final audit, realized exposure, unknown partial outcomes, native report
contracts and reflection-trace reconciliation are prospective evidence gates. Eventual
runner/auditor hashes must be bound before the first trial.

No code or tests changed, so suites were not rerun for this specification-only increment.
No agents, oracle checks, comparison runs, browser trials or paid API calls were executed.
Historical plans/results were not changed. Diff checks passed. This is not an equal-cost
ablation, LLM reflection study, stochastic comparison or external approval.

### Offline reflection trace reconciliation — 2026-11-26

Added the research-only reflection reconciler and 39 tests for actual phase traces,
strict counters/contexts/claims, authorization, retry guards, policy denials, malformed
frames and deadline limitations. A spoofed-read claim remains trace-consistent while
failing separate SQL truth; reconciliation invokes neither provider nor oracle.

156 focused tests passed, including reflection, verification admission/budget and bounded
oracle runner/package regressions. Product sources and the prospective comparison plan
remain unchanged. Ruff, formatting and diff checks passed. The full browser suite was
not repeated for this isolated research auditor. No comparison study or paid API calls ran.

### Pinned common-corpus runner — 2026-11-26

Implemented a standalone mock-only runner with a separate pretrial execution lock binding
the unchanged published plan, runner, reflection auditor and shared support source. It
validates exact ordered coverage, product/corpus pins and lock hashes before creating
outputs or providers. Per-condition native reports and trace replays precede the final
SQL audit; fresh ledgers apply only to dynamic arms. Resources, false claims, collateral
changes and realized/unused fault evidence remain separate.

196 focused tests passed, including 40 new runner checks: all four arms across four fault
scenarios, multi-target/satisfied reflection tasks, plan/source/lock drift rejection,
interrupted partial-attempt retention and simulated complete/duplicate-ID orchestration.
The simulated orchestration does not execute the 96-condition study. Existing reflection,
admission/budget and bounded-oracle runner/package checks passed in the same run.

Ruff, formatting, document links, execution bindings and diff checks passed. No product
source or historical plan/results changed. No full browser rerun or paid API call was
needed for this research-only change. The planned comparison remains unexecuted.

### Frozen common-corpus execution and result audit — 2026-11-26

Executed all 96 assigned mock conditions using the existing source pins and pretrial lock.
All unique identities, fixed block positions, native reports and per-arm trace replays
completed. A separate read-only result checker verified file hashes, SQLite/JSON trace
agreement, original tasks, budgets, ledger/resource counters and independent final SQL
states. All 96 independent rechecks passed against manifest SHA-256
`b15d202a3f160e4f9968b287c7a6f4ce46fdcc1834d3c885ab5fb91fb770660c`.

Recorded condition-level evidence and descriptive outcomes: baseline and verify reached
9/24 goals each; recover and mock reflection reached 19/24 each. Baseline made ten false
success claims; the other arms made none. Reflection retained five achieved-goal budget
failures and five unsatisfied persistent-drop budget failures. No collateral status/version
changes were observed. Resources and realized exposure remain separate from outcome truth.

210 focused tests passed, including 14 new result-checker tests for all report arms,
false-claim retention, corrupted hashes/resources/outcomes/SQL/report/task data, incomplete
coverage, duplicate identities and changed bindings. The final 14 checker tests also
passed after adding saved per-run metadata. Ruff, formatting, links and diff checks passed.
No product source, prospective plan, execution lock or bound runner changed; no paid API
calls or browser suite rerun occurred. The raw evidence is local and unsigned; portable
packaging, external review and LLM/equal-resource comparisons remain pending.

### Portable common-corpus raw evidence — 2026-11-26

Published a 634,689-byte/583-file ZIP containing all 96 original trials, manifest,
plan/lock, corpus and bound runner/reflection-auditor/support source snapshots. Original
plan, execution lock, runner, measured result record and raw directory remain unchanged.
Archive SHA-256 is
`34445c56c209d320141a0ce3d085d3ea411a6459e1980368cb6e5eb8d7e1620a`.

The portable checker verifies bounded ZIP/tree inventory, external manifest binding,
embedded metadata/source hashes, coverage, native reports, SQLite/JSON traces, admission
or reflection replay, counters and final SQL states. It never executes embedded sources.
Relocated audit passed with original artifact/repository metadata reads blocked. All 96
outcomes and ten baseline false claims remain intact. Source snapshots and hashes are
unsigned evidence; fault delivery is not independently reenacted.

227 focused tests passed, including 17 new archive relocation/corruption/overwrite checks,
alongside reflection result/runner/phase, admission/budget and earlier portable-evidence
regressions. Ruff, formatting, links, package/checker hashes and diff checks passed.
Windows denied staged hard-link publication inside the sandbox; rerunning the same
audited publication outside the sandbox succeeded. No source fix or evidence replacement
was needed. No comparison rerun, paid API call or browser suite execution occurred.

### Updated research review packet — 2026-11-26

Refreshed the implementer review packet with the historical 144-run comparison, portable
72-condition bounded-oracle study and portable 96-condition common-corpus study. Added
measured outcome/resource summaries, reviewer evidence routes and explicit dispositions
for pending corpus/fault/oracle review, provenance, LLM comparison and resource ablations.
Corrected the stale full-suite reference to the recorded 850-test run and distinguished
the latest 227-test focused regression record. No new test count is claimed.

Checked document links and summary numbers against committed machine-readable results,
package metadata and validation history. Diff checks passed. Documentation only; test
suites and studies were not rerun. Historical plans, locks, source snapshots, archives
and result records remain unchanged. No external reviewer was contacted or approval
recorded; no paid execution occurred. Next work is a prospective mock decision-budget
sensitivity specification, not a claim of equal information or dollar cost.

### Prospective decision-budget sensitivity specification — 2026-11-26

Added a prose protocol and machine-readable plan for 288 fresh fixed-mock conditions:
six tasks, four scenarios, four arms and decision caps 4/8/12. Actions stay capped at eight,
retry/corrective admissions at two, with unchanged information access and native reports.
The design explicitly retains the two prior achieved-goal reflection stops that reached
both action and decision caps; increased decisions are not assumed to resolve them.

Verified all unique Cartesian cells and their flattened block order, 24 assigned cells
per arm/cap, eight occurrences of each cap-group position and six occurrences of each
arm position within each cap. Strict Budget validation, source/corpus/prior-result hashes,
document links and diff checks passed. Cap-eight cells must execute anew in the future;
prior outcomes are not substituted or pooled. Runner/auditor binding is a pretrial gate.

This specification-only increment changed no source or tests, so suites were not rerun.
No trials, oracle checks, browser runs or paid API calls occurred. Historical plans,
execution locks, results and archives remain unchanged. The new study remains unexecuted;
it is decision-cap sensitivity, not equal-resource or LLM-quality evidence.

### Pinned mock decision-budget runner — 2026-11-26

Implemented the standalone mock-only runner and pretrial execution lock for the unchanged
288-condition plan. Validation precedes output/provider construction and checks exact
plan bytes/order, typed budgets, product/corpus/prior-result pins and the complete research
Python inventory. Fresh per-condition execution reuses the native mock runner; the existing
portable condition auditor independently checks traces/resources and final SQL state.

Added recorded budget, available repeat-write/time resources and separate action/decision/
corrective/reported-deadline flags, terminal failure and achieved-goal budget outcome.
Reconciliation rejects changed fields or assigned caps. Overlapping exhausted counters
are retained, not interpreted as a unique causal stop. Partial/failed evidence is retained
under an unknown active outcome; no automatic resume, retry or replacement was added.

243 focused tests passed, including 33 new runner checks covering all four arms at caps
4/8/12, reflection single/joint cap examples, plan/lock/resource/diagnostic corruption,
interruption and simulated complete/duplicate-ID orchestration. Existing reflection,
admission/budget, result/runner and bounded-oracle package regressions passed in that run.
Ruff, formatting, links, execution bindings and diff checks passed. No product or historical
bound source/plan/result/archive changed. No full browser rerun or paid API call occurred.
Selected unit fixtures are not study observations; the 288-run study remains unexecuted.

### Recorded decision-budget sensitivity and local audit — 2026-11-26

The initial attempt stopped on Windows atomic manifest replacement after 206 completed
rows; its manifest and unknown active condition remain separate. An explicitly disclosed
fresh attempt outside the sandbox completed all 288 ordered assignments with the same
frozen inputs. No individual cell was resumed/replaced and partial outcomes were not
pooled. Both attempt paths and manifest hashes are recorded in the results.

A post-execution read-only auditor outside the frozen research inventory verified full
coverage, identities, native trace/resource/SQL reconciliation and stopping diagnostics.
All 288 checks passed. Recorded 192 matched cap contrasts. All new cap-eight outcomes,
failures and resource vectors matched the earlier 96-run reference without pooling it.
Goal satisfaction did not change at cap twelve versus eight; reflection gained one final
claim and retained four achieved-goal budget failures with exhausted action counters.

252 focused tests passed, including nine new result-auditor/contrast/manifest checks.
The final nine also passed after adding execution-binding metadata to the saved record.
Ruff, formatting, links, result/auditor hashes, frozen bindings and diff checks passed.
No product or frozen research execution source, plan, lock or historical result/archive
changed. No paid calls or browser suite rerun occurred. Raw evidence remains local and
unsigned; portable complete/partial-attempt packaging and external review remain pending.

### Portable complete and partial decision-budget evidence — 2026-11-26

Published separate audited ZIPs: 1,741 files/1,954,522 bytes for the completed 288-run
attempt and 1,249 files/1,443,101 bytes for the interrupted 206-run prefix. Each includes
its original manifest/plan/lock, native trial evidence, corpus, prior reference and all
eight frozen execution source snapshots. Original attempt paths, identities, source pins,
plans, locks and measured result records remain unchanged. No partial outcomes were pooled.

The portable checker uses the external manifest binding and bundled relative inputs;
it verifies complete versus partial-prefix coverage, active unknown identity, file/source
hashes, native traces/resources/stopping flags and final SQL rows. Both released archives
passed with original artifact/repository metadata reads blocked. The partial archive
reports consistency passed but study_complete false; flipping that flag is rejected.

269 focused tests passed, including 17 new complete/partial package, relocation, corruption,
unsafe archive, wrong-attempt and overwrite checks. The remaining result/runner/reflection,
admission/budget and earlier bounded-oracle regressions passed in the same run. Ruff,
formatting, document links, both ZIP/checker hashes, frozen execution bindings and diff
checks passed. Publication used an escalated staged hard-link operation, as required by
the earlier Windows sandbox denial. No study rerun, paid call or browser suite execution
occurred. The evidence remains unsigned; no authenticity or fault-reenactment claim is made.
