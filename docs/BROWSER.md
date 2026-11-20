# Local browser recovery slice

This optional Phase 3 slice drives a purpose-built local issue page through headless
Chromium. It is not a general web agent. The existing static and dynamic agents keep
their typed `read_issue` / `set_status` actions and trusted target/status authorization.
Browser actions use fixed DOM locators and form controls rather than direct API calls.
Independent verification and the final audit read SQLite, not the page's success message.

## Install and run

From the project root:

```powershell
.\.tools\uv.exe sync --locked --extra dev --extra browser --extra openai
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\veriagent.exe browser-smoke --engine dynamic
```

The OpenAI extra keeps live-provider support installed, but the command above defaults
to mock and uses zero API credits, even if credentials exist. Playwright requires its
matching browser binaries; see the official [browser installation guide](https://playwright.dev/python/docs/browsers).
The adapter uses Playwright's [fixed test-ID locators](https://playwright.dev/python/docs/locators).

Each smoke starts its own application on an OS-assigned `127.0.0.1` port, opens a new
headless browser/context, seeds a fresh database and injects one dropped write. The UI
optimistically displays the requested status after the server acknowledges the write.
The first acknowledgment can therefore say done while SQLite remains open. The agent
must detect that mismatch, repair it within its budget and verify the persisted status.
Other issues must stay unchanged. Browser, driver and local application are closed at
exit; a local-server thread that cannot be joined is reported as a setup/cleanup error.

`--engine static` selects static planning (the default). Browser smoke defaults to eight
actions, eight dynamic decisions, a five-second per-action deadline and a cooperative
60-second agent deadline. Playwright waits use the remaining action allowance across
navigation, locating, selection, click and result observation. Timeout can leave a write
ambiguous; the existing verifier/retry policy resolves state before selective repair.
This is not process deadline isolation or a whole-agent hard wall-clock guarantee.
Browser/application startup and evidence capture are outside the agent-loop budget.

## Evidence

A UUID directory under `artifacts/browser-smoke/` contains:

- Initial/final SQLite state, report, audit and environment versions in `result.json`.
- Structured/readable traces and their SQLite trace store.
- `browser-before.png`, a refreshed `browser-after.png`, and final DOM HTML.

`report.tool_execution` is `browser`. A passing smoke requires detected mismatch, an
actual recovery attempt, verified success, final audit success and unchanged untargeted
issues. The final screenshot reloads application state after execution; the recovery
test does not treat that screenshot as its ground-truth oracle. If final capture fails,
`browser.capture_complete` is false and the agent report/audit are still saved. Screenshot
capture alone never establishes task success. Setup failures return CLI exit 2 and can
leave a partial artifact directory; reported smoke failure returns 1, passing smoke 0.

## Scope and boundaries

The browser uses a fresh temporary context, no personal browser profile, no reused
cookies and no account sign-in. Model actions cannot supply URLs, selectors or scripts.
Context request routing permits only the owned application's fixed page/script/read/write
paths and methods, blocks service workers/download acceptance, and rejects other origins.
A loopback-only constructor check is additional validation, not proof of server ownership;
`browser-smoke` itself creates the server. Issue titles enter the DOM through `textContent`.
The UI has a content security policy and no third-party assets.

Chromium is launched with an environment allowlist excluding OpenAI credentials; the
Playwright driver itself remains a trusted local subprocess. Request routing is a browser
context boundary, not an OS/network security sandbox or a guarantee against every browser
background connection. The local app/API is unauthenticated and must remain on loopback.
These checks do not establish general prompt-injection resistance or arbitrary-site safety.
Only the local fixture and existing SQLite actions are supported. Reviewed `execute`
supports an explicit browser backend; process workers and repeated-trial benchmarks do not.

Explicit `--provider openai` enables potentially billable planning/decisions, using the
same provider flags and usage ledger as ordinary smoke. It is not run automatically.
Use an explicit cumulative `--max-model-output-tokens` allowance for a live trial.
Live-model browser quality remains unvalidated; the implemented checks use the mock.

## Tests

The normal suite runs URL/origin checks without a browser installation. Real Chromium
checks are opt-in:

```powershell
$env:VERIAGENT_BROWSER_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_browser.py tests/test_browser_execution.py -q
```

They exercise static/dynamic recovery, optimistic acknowledgments, title-as-text handling,
missing issues, transient non-commit, external-navigation blocking, stalled UI timeouts,
and honest failure when recovery is disabled. The browser tests require Chromium already
installed; they do not download binaries or issue paid model calls.

## Reviewed multi-target execution

`execute --tool-backend browser` operates the same owned local fixture through Chromium.
The default remains `--tool-backend sandbox`. Approval is checked before browser startup,
provider construction and state creation. The exact parsed immutable proposal is retained;
the execution model cannot substitute requirements. Browser mode rejects `--isolate-tools`
and worker hang-injection flags before side effects. Its default action deadline is five
seconds; sandbox execute retains its one-second default. Explicit limits still override.

Create and inspect a proposal first (mock interpretation uses no API credits):

```powershell
$proposalResult = .\.venv\Scripts\veriagent.exe propose "Close ISSUE-1 and start ISSUE-2" | ConvertFrom-Json
.\.venv\Scripts\veriagent.exe review $proposalResult.proposal_file
```

Read the requirements: ISSUE-1 done, ISSUE-2 in_progress. If they match your intent,
execute using the displayed digest and a fresh trial directory:

```powershell
$trialDir = Join-Path "artifacts/reviewed-browser-trials" ([guid]::NewGuid().ToString("N"))
$execution = .\.venv\Scripts\veriagent.exe execute $proposalResult.proposal_file --approve (Read-Host "Reviewed approval digest") --tool-backend browser --engine dynamic --silent-drops 1 --max-actions 8 --max-decisions 8 --db "$trialDir/state.sqlite" --traces "$trialDir/traces.sqlite" --browser-artifacts "$trialDir/evidence" | ConvertFrom-Json
$execution.browser_execution_passed
$execution.browser_audit | ConvertTo-Json -Depth 5
```

This also defaults to mock. Explicit OpenAI provider selection uses API credits; no
live-model reviewed-browser trial has been validated. Existing database files are preserved
and seeded without resetting their current statuses; choose a fresh path for independent
trials. The artifact root must differ from state/trace database files.

The output preserves the agent's original claim, verification result and usage. A separate
`browser_audit` reads all final SQLite rows, checks every approved target, compares every
untargeted row (including title/version and added/deleted IDs), and checks that target titles
were unchanged. It does not judge target version counts beyond retaining them as evidence.
This audit occurs after browser/server cleanup and never feeds corrections to the agent.
`browser_execution_passed` requires an agent success claim, passed audit and completed
cleanup; CLI exit 1 means this overall result failed, even if the agent claimed success.
A baseline's internal verification remains null; the independent audit is separate.

Each UUID evidence directory saves the full approved proposal/digest, task, budget,
initial/final state, original report plus audit, ordered traces, and before/after screenshot
and DOM files for each target. Filenames use ordinal numbers; capture metadata maps them
to issue IDs. Captures are outside the run budget and their failure is recorded without
changing agent outcomes. A setup failure before an agent report returns exit 2 and saves
bounded setup metadata. Unconfirmed cleanup after a report preserves it but fails the
overall result. Passing cleanup records successful API shutdown, not an OS attestation of
all possible subprocess descendants. Browser startup/capture/cleanup are not hard real-time.
