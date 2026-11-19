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
