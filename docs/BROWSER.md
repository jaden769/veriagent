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
headless browser/context and seeds a fresh database. The default profile injects one
dropped write; other profiles are described below. The UI
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

`report.tool_execution` is `browser`. The default dropped-write smoke requires a detected
post-write mismatch, actual recovery, verified success, final audit success and unchanged
untargeted issues. Other browser scenarios use the expectations below. The final screenshot
reloads application state after execution; the recovery
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

## Stale DOM and post-commit ambiguity

Browser smoke and reviewed browser execution accept `--browser-scenario`:

| Profile | Controlled behavior | Smoke expectation |
| --- | --- | --- |
| `silent_drop` | One successful acknowledgment without a commit | Post-write mismatch detected and repaired |
| `stale_dom` | First status-changing commit succeeds, but the page renders the previous status | Goal verified without replay |
| `lost_ack` | First status-changing commit succeeds, but its response is HTTP 503 | Goal verified without replay |
| `clean` | No additional application fault | Verified completion |

```powershell
.\.venv\Scripts\veriagent.exe browser-smoke --engine dynamic --browser-scenario stale_dom
.\.venv\Scripts\veriagent.exe browser-smoke --engine dynamic --browser-scenario lost_ack
```

Both commands default to mock. The `lost_ack` profile is a post-commit service-error
response, not a literal packet loss or delayed transport timeout. `stale_dom` is a
controlled stale rendered status, not an arbitrary SPA/cache model. The one-shot
post-commit profiles are delivered only when status changes durably; no-op assignments
and dropped writes do not consume them. Initial unsatisfied goals are not counted as
post-write failures: `fault_detected` excludes initial dynamic verification.

For `stale_dom`/`lost_ack`, smoke requires actual anomaly evidence, exactly one recorded
application write, a durable commit, no recovery attempts, final verification/audit success
and unchanged unrelated issues. It reports `anomaly_observed: true` and
`recovery_required: false`; `fault_detected` can correctly be false because SQLite never
mismatched after the write. Truncated event evidence cannot pass these smoke checks.

Application writes are serialized in the fixture while before/after status and version
are recorded. `application-events.json` includes HTTP outcome, persisted state and
post-commit profile delivery; legacy counter faults are also visible through unchanged
state and their fault counters. `browser-events.json` includes DOM reads, requested versus
actually rendered status, observed response code and normalized action outcomes. Each log
is capped at 2,048 events; dropped-event count is explicit. Final screenshots reload fresh
state and can therefore look correct even when an earlier DOM result was stale. Use the
event log to inspect that earlier discrepancy.

These logs are evaluator evidence. Hidden profile labels and application commit metadata
are not supplied to the planning provider; it sees ordinary tool feedback and independent
verification through the existing protocol. Browser write observations now report the
rendered DOM status, rather than copying the requested status as an observation.

Reviewed `execute` defaults to `--browser-scenario clean`, preserving existing behavior;
browser smoke defaults to `silent_drop`. Non-clean scenarios require the browser backend
and cannot be combined with `--silent-drops`. Existing `execute --tool-backend browser
--silent-drops 1` still works with the default clean application profile. Reviewed execution
retains pending fault/event metadata but judges goal/collateral/cleanup outcomes; unlike
smoke, it does not require the selected profile to be exercised on already-satisfied goals.

When a write reports an error but independent verification confirms that target completed,
the dynamic agent can continue to other unmet targets without allocating a retry for the
completed target. This works in verify/recover modes with zero retry budget. Unconfirmed
worker cleanup still terminates execution before this progress rule; completed writes
are never authorized for replay. This is state-based progress, not proof that every
error is harmless, and does not change baseline policy.

## Pending-response action timeouts

Two additional controlled profiles hold the HTTP response until Playwright's action
wait actually times out:

| Profile | State while response is held | Required smoke behavior |
| --- | --- | --- |
| `timeout_before_commit` | Request has not changed SQLite and will be rejected | Detect unmet state, retry once, end with one commit |
| `timeout_after_commit` | SQLite is already committed | Verify completion with no replay |

```powershell
.\.venv\Scripts\veriagent.exe browser-smoke --engine dynamic --browser-scenario timeout_before_commit --action-timeout 1
.\.venv\Scripts\veriagent.exe browser-smoke --engine dynamic --browser-scenario timeout_after_commit --action-timeout 1
```

The browser waits for the page's pending save result, reaches its real action deadline,
and produces a timeout observation. A trusted fixture callback then releases the held
response; the agent gets no commit-state hint from that callback. Independent SQLite
verification resolves the mutation outcome. The pre-commit profile returns a rejection
without ever committing that request, even after release; the post-commit profile releases
a successful acknowledgment for the write that already persisted. These are browser
**action deadlines while HTTP is pending**, not simulated error observations, OS TCP
socket timeouts, arbitrary packet loss or guarantees that real remote services cancel work.

A per-fixture ten-second safety release prevents an abandoned handler from waiting
indefinitely. Action deadlines must be below ten seconds for these profiles; CLI rejects
incompatible budgets before provider/artifact/state creation. Browser and server cleanup
also release a pending handler. Application events record response_state and release_reason
(`action_timeout`, cleanup, or `safety_deadline`). A safety/cleanup release alone cannot pass
a timeout smoke: actual timeout observation and matching action_timeout evidence are required.
Low deadlines that expire before the intended request is reached can fail the smoke honestly.

A passing pre-commit smoke requires two application write attempts, only the second
committed, a detected post-write mismatch, recovery, verified final state and no unrelated
changes. Passing post-commit smoke requires a single committed attempt and zero recovery.
Both keep final version 1. With zero retries, the pre-commit case fails and remains open;
the post-commit case can succeed, including with other approved targets still unfinished.

Reviewed browser execution supports the same profiles. Regression cases use the fixed
mixed_status, reopen and partial_satisfied corpus initial states with original approved
requirements. Both timeout boundaries are tested against those cases using the dynamic
engine, direct final-state/collateral audits and version checks. They are deterministic
local mechanism tests, not repeated stochastic browser or model reliability measurements.

## Offline corpus batches

`browser-batch` runs fresh local browser/state instances against the packaged six-task
corpus. It uses only MockProvider; no API credentials or model requests are needed.
For example, in PowerShell:

```powershell
.\.venv\Scripts\veriagent.exe browser-batch --task single_done --task already_satisfied --scenario clean --scenario silent_drop --scenario timeout_after_commit --mode baseline --mode recover
```

Repeat `--task`, `--scenario`, or `--mode` to select unique values. Defaults are
single_done, clean/silent_drop, recover, dynamic engine, one repeat. `--repeats` accepts
1–20, with a maximum of 120 total trials. Each run has eight actions/decisions,
two retries, a 30-second cooperative run deadline and a one-second action deadline.
Browser setup and evidence captures are outside that run deadline.

The UUID output directory contains an atomically replaced `manifest.json`, per-trial
state/traces and the existing reviewed execution evidence bundles. The manifest retains
the corpus hash, Python/UI/fixture source hashes, exact selection/budget, proposal
digests, actual write/commit counts, event truncation counts and evidence paths.
Interrupted batches retain completed rows and the active trial path; no automatic resume
is provided. A completed batch can contain failed agent outcomes; command success means
the batch completed, not that every trial passed.

Summaries group by task/scenario/mode. They separate independent audited state success,
claimed success, overall execution passes and actual fault exposure. Conditional false
success uses claims as its denominator; audited success given exposure uses exposed runs.
Empty denominators are null. Unreached faults, including already-satisfied goals, do not
count as exposure. The latter metric is not a recovery rate: post-commit faults may need
no recovery. Clean trials have no injected exposure. Repeated deterministic mock results
are fixture checks, not independent stochastic reliability estimates.

## Expected-outcome controls

```powershell
.\.venv\Scripts\veriagent.exe evaluate-browser
```

This mock-only command checks a fixed 42-trial dynamic matrix: all six corpus tasks
across clean, silent_drop, stale_dom, lost_ack, timeout_before_commit and
timeout_after_commit in recover mode, plus all six profiles for the single_done baseline.
Budgets and artifacts are the same as browser-batch. No API requests are made.

`browser_controls.py` specifies changed-target counts independently for the fixed initial
states. Every recovery case must reach the goal with exactly one commit per changed
target. Dropped writes and pre-commit timeouts require one retry/extra attempt;
post-commit ambiguity requires none. Already-satisfied cases must make no writes and
expose no fault. Baseline controls distinguish expected false claims (dropped writes)
from an error claim after a successful commit. They intentionally do not all pass the task.

Each comparison retains the expected values and actual mismatches for exposure, claim,
SQL audit, overall execution, commits, write attempts, retries and event truncation.
Passing the evaluation requires all 42 unique task/profile/mode combinations and no
mismatches. `controls.json` is saved atomically beside the nested browser batches;
interruptions retain completed controls and partial batch manifests. Exit code 1 means
an expectation or coverage mismatch; setup failures exit 2. This command checks the
current fixture contract, not general browser reliability or independent corpus quality.

## Indexed browser writes

The batch runner additionally accepts second_drop, second_lost_ack,
second_timeout_before_commit and second_timeout_after_commit. These profiles schedule one
fault at mutation attempt 2. Reads do not advance that index; no-ops and rejected missing
targets do. Injection requires a changing existing target; an unreached or ineligible
event stays unused and never moves to a later attempt. Existing first-write profiles and
the default 42-control evaluation remain unchanged.

```powershell
.\.venv\Scripts\veriagent.exe evaluate-browser --indexed
```

The indexed evaluation checks 24 dynamic recovery controls: all six tasks across the four
second-write profiles. Two-changing-target cases must expose the fault at attempt 2,
preserve the first completed target, commit each changed target once and retry exactly
once only for the drop/pre-commit timeout. Zero/one-changing-target cases must finish
without exposure and retain one unused scheduled fault. These expectations are separate
from the batch implementation and include exact injected positions and remaining faults.
The batch manifest records planned_fault_attempt, injected_attempts and
pending_application_faults alongside its ordinary results. Both agent engines also have
real browser regressions for all four indexed profiles on pair_done.
