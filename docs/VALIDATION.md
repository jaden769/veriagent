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
