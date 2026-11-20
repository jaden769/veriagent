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
