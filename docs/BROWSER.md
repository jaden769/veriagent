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

## Multiple faults and exhausted retries

```powershell
.\.venv\Scripts\veriagent.exe evaluate-browser --multi-event
```

This separate 12-control dynamic matrix crosses pair_done/mixed_status, two schedules,
and retry allowances 0/1/2. second_two_drops drops attempts 2 and 3;
second_drop_then_lost_ack drops attempt 2 and commits attempt 3 while returning an error.
Each scheduled event retains its original position and kind. Ineligible events do not
shift; pending_application_faults counts unused events. The batch manifest includes the
full planned_faults list and application logs include scheduled_kind/injected_kind.

Controls explicitly require first-target done/version 1, correct second-target state and
version, unchanged unrelated issues/titles, exact attempts/commits/retries, and honest
failure on retry exhaustion. With no retries, one fault remains unused and the second
target stays open. Two drops still fail with one retry; with two retries both targets
complete. A drop followed by a committed error succeeds with one retry and no replay of
the committed request. An expected partial failure can pass the evaluation control while
the task audit fails. Recovery never rolls back the first completed target.

The default 42-control and optional 24-control indexed selections remain separate;
--indexed and --multi-event are mutually exclusive. Generic browser-batch also accepts
the two multi-event profile names. Tests additionally exercise both engines with zero
and sufficient retries. These are fixed local schedules, not arbitrary remote-failure models.

## Re-auditing saved trial evidence

New reviewed-browser executions and browser-batch trials include `evidence.json`, an
inventory of local filenames, byte lengths and SHA-256 hashes. Audit a trial directory:

```powershell
.\.venv\Scripts\veriagent.exe audit-browser <trial-bundle-directory>
```

This command reads local files only. It launches no browser, makes no API requests and
writes no files. It does not follow embedded artifact paths, so bundles can be moved.
It checks required files, all inventoried hashes, proposal/task/digest agreement, saved
state audits, application-event replay, report/trace agreement, readable trace rendering
and before/after capture availability. It rejects duplicate snapshot IDs, truncated event
logs, malformed or missing evidence, external filenames and oversized inputs (64 files,
16 MiB per file, 64 MiB total). Trace text accepts Windows CRLF or LF line endings while
hash checks still use exact bytes. PNG/HTML hashes check byte integrity, not visual quality.

`evidence_passed` describes evidence consistency/completeness; `task_passed` recomputes the
saved execution outcome. An honestly recorded exhausted-retry failure can have valid
evidence and task_passed false. Exit code 0 requires evidence_passed; code 1 reports failed
checks. Earlier bundles lacking evidence.json fail the inventory check; no inventory is
silently generated during audit. This command audits individual reviewed execution
bundles, not browser-smoke or a whole batch manifest; batch auditing is described below.

The inventory is unsigned. It detects missing/changed files against that inventory and
cross-file inconsistencies; someone rewriting the inventory and all matching evidence can
evade it. Audits use saved snapshots and logs, not a new query of the original live SQLite
database, and do not establish authenticated provenance or independently reproduced runs.

## Re-auditing a whole batch

```powershell
.\.venv\Scripts\veriagent.exe audit-browser-batch <batch-directory>
```

New browser-batch manifests bind each trial to a relative bundle_directory and an
inventory_sha256. The auditor reads at most 120 trials, validates the configured
task/profile/mode/repeat coverage, rejects duplicate run IDs, and confines bundle paths
to the selected batch directory. Recorded absolute artifact paths are never followed,
so moving the complete directory preserves auditability. Each trial must pass the
individual evidence audit and match the recorded inventory hash.

The auditor checks reviewed task requirements and initial statuses against the current
packaged corpus/hash, binds trial engine/mode/budget/provider configuration, reconstructs
outcomes, write/commit/retry counts, fault exposure, indexed positions and remaining
application faults, then recomputes grouped summaries. First-write counter drops now
carry explicit application-event injection labels so exposure can be reconstructed
without consulting live fault counters. All reads retain the per-file/per-bundle limits
of audit-browser; the manifest itself is bounded to 16 MiB.

`evidence_passed` means complete, consistent batch evidence, not universal task success.
Expected baseline failures remain failures in the reconciled summaries. Interrupted or
incomplete coverage, missing bundles, changed inventories/rows/summaries and escaped paths
fail closed (exit 1). Exit 0 requires all checks to pass. The command writes no files,
starts no browsers and makes no API calls. Older manifests lacking relative paths or
inventory bindings are unsupported and fail; no evidence is silently upgraded.

This checks current-corpus consistency, not installed source fingerprint equality or a
new query of the original SQLite databases. Batch manifests and inventories are unsigned;
coordinated rewriting of all matching evidence/configuration is not prevented. Control
evaluation controls.json files remain outside this command's scope; use the control audit
below for the whole evaluation or audit nested browser-batch directories individually.

## Re-auditing a complete control evaluation

```powershell
.\.venv\Scripts\veriagent.exe audit-browser-controls <evaluation-directory>
```

New evaluations bind each relative nested batch directory to its manifest SHA-256 and
retain each control's relative trial/batch association. The offline audit supports the
default 42-control matrix, --indexed 24-control matrix, --multi-event 12-control matrix
and --budget-boundaries 12-control matrix.
The --fault-budget-boundaries selection adds a 24-control recovery-admission matrix.
The --satisfied-budget-boundaries selection adds 16 pre-satisfied-goal controls.
It checks completed status, the selected matrix shape and fixed budgets, nested manifest
bindings, all nested batch/trial evidence, unique run IDs across batches, exact control
coverage, expected values, mismatch details and the reported evaluation outcome.

The command reconstructs comparisons using the current control definitions. It follows
only confined relative directories, so complete evaluations can be moved. Stored absolute
paths are not followed. The controls.json input is bounded to 16 MiB and the selected
matrix permits at most six nested batches and 42 controls; nested batch/file limits
also apply. Older evaluations lacking batch_bindings are unsupported and fail closed.

`evidence_passed` means complete, consistent saved evidence. `controls_passed` independently
reports whether the current expectations matched; an honestly recorded expectation
mismatch can have evidence_passed true and controls_passed false. Individual expected
baseline or retry-exhaustion task failures can pass their controls. Exit 0 requires valid
evidence, while exit 1 reports incomplete or inconsistent evidence. Auditing reads files
only: it launches no browsers, makes no API calls and does not rewrite artifacts. The
unsigned manifests/hashes do not authenticate provenance or prevent coordinated rewriting.

## Compact offline review

```powershell
.\.venv\Scripts\veriagent.exe review-browser-controls <evaluation-directory>
.\.venv\Scripts\veriagent.exe review-browser-controls <evaluation-directory> --format json
```

The review command runs the complete control audit, then prints a compact text report
(default) or JSON. It separates successful tasks, expected task failures, unexpected task
failures and expectation mismatches, with relative evidence paths for the detailed rows.
Task outcomes use the saved execution outcome (claim, state audit and cleanup), not the
SQL goal state alone. A task failure is expected when the control explicitly expected
execution_passed false; another mismatch on that same row remains separately visible.
Unexpected successes also appear in the expectation-mismatch list.

When evidence is invalid or incomplete, outcome counts are withheld rather than computed
from partial results. Evidence gaps include nested batch/trial locations; the compact
display caps them at 100 and notes truncation. Use audit-browser-controls for full details.
The command prints to stdout, writes no artifacts and starts no browsers/model calls.
Exit 0 means evidence is valid, even when controls_passed is false; exit 1 means evidence
could not support the report. Unsigned inventories and deterministic fixture counts do
not establish authenticated provenance or stochastic reliability.

## Action and decision boundaries

```powershell
.\.venv\Scripts\veriagent.exe evaluate-browser --budget-boundaries
```

This separate dynamic mock matrix crosses pair_done/mixed_status with action limits
2/3/4 (decision limit 8) and decision limits 2/3/4 (action limit 8), using the clean profile.
It checks 12 controls with two retries available but no injected faults or recoveries.
The fixed mock reads then writes each target: limits 2/3 must stop with failure budget,
first target done/version 1 and second target open/version 0. At exactly four steps,
both targets must complete and no budget failure may be reported. Unrelated issues and
target titles must remain unchanged throughout.

Trial rows retain max_actions/max_decisions, observed decisions and terminal failure.
Control identities and review detail rows distinguish the two budget dimensions. The
offline control auditor requires this metadata for the boundary matrix and validates
the exact configured limits; reports show four successes and eight expected task failures
when all controls match. The existing default, indexed and multi-event matrices keep
their original identities. Previously generated bound evaluations without the new optional
budget fields remain auditable; no files are upgraded during audit.

## Faults at action and decision boundaries

```powershell
.\.venv\Scripts\veriagent.exe evaluate-browser --fault-budget-boundaries
```

This separate 24-control dynamic mock matrix crosses pair_done/mixed_status,
second_drop/second_lost_ack, and action limits 4/5/6 (decision limit 8) or decision limits
4/5/6 (action limit 8). A write fault is reached on the fourth step after the first target
has committed. Every control requires injection at write attempt 2, no replay of the first
target and unchanged unrelated state/titles.

For second_drop, limit 4 must stop with a budget failure before admitting recovery:
two write attempts, one commit, zero retries. Limit 5 admits one recovery but only has
room to reread the second target; it still fails budget with that target open/version 0.
Limit 6 completes the repair with three write attempts, two commits and one retry.
For second_lost_ack, verification confirms the second commit at step 4, so every selected
limit must succeed at four actions/decisions with two commits and no retry or replay.

All 24 matching controls therefore represent 16 successful tasks and eight expected
budget failures. Offline audit and review support the new matrix and display its exact
limits. Existing saved bound evaluations remain supported. Counts describe this fixed
mock flow and do not establish stochastic model or remote-service reliability.

## Pre-satisfied goals under tight budgets

```powershell
.\.venv\Scripts\veriagent.exe evaluate-browser --satisfied-budget-boundaries
```

This separate 16-control dynamic mock matrix crosses already_satisfied/partial_satisfied,
clean/second_drop, and action limits 1/2 (decision limit 8) or decision limits 1/2
(action limit 8). Already-satisfied goals must complete with zero agent actions/decisions,
zero writes/commits and their original version 0. Initial SQL verification and browser
evidence-capture reads still occur; those are not agent action counts.

Partially satisfied goals must leave the seeded completed target at version 0. At limit 1,
the unfinished target is read but not written, so the task honestly fails budget with
both target versions unchanged. At limit 2, one read/write completes the remaining target
at version 1. No recovery is needed. second_drop must stay unused in all selected cases:
at most one mutation is reached, so exposure is false and one scheduled fault remains.
Unrelated state and target titles must remain unchanged.

A matching review therefore shows 12 successful tasks and four expected budget failures.
Offline audits require the same exact budget metadata and retain compatibility with
previous bound evaluations. These are local initial-state/budget controls, not model-quality
or general browser-reliability measurements.

## Reviewing multiple saved matrices

```powershell
.\.venv\Scripts\veriagent.exe review-browser-suite <evaluation-one> <evaluation-two>
.\.venv\Scripts\veriagent.exe review-browser-suite <evaluation-one> <evaluation-two> --format json
```

Select one to six distinct saved evaluation directories. The command re-audits every
evaluation and identifies its matrix from validated selection flags. It reports present
and missing matrix types among default, indexed, multi_event, budget_boundaries,
fault_budget_boundaries and satisfied_budget_boundaries. A valid partial selection is
accepted by default but clearly displays partial coverage; --require-all requires all six
types. No browser runs or API calls are made, and the command writes nothing itself.

Suite totals preserve successful tasks, expected/unexpected task failures and expectation
mismatches. Each evaluation retains its own compact review and evidence path. Canonical
directory duplicates are rejected before auditing. Distinct directories containing the
same matrix, reused/missing run IDs, or any invalid evaluation evidence withhold all suite
totals rather than inflating them. Per-evaluation reports can still help locate the gap.
Requiring all matrices on a partial valid selection also withholds totals and reports
required_matrices_missing. A full selection contains 130 fixed controls under current
definitions; a partial selection is never presented as full-suite validation.

Exit 0 requires valid evidence and satisfied selection constraints, even if an accurately
recorded expectation mismatch makes controls_passed false. Exit 1 reports evidence or
selection failure; invalid argument counts or duplicate canonical directories exit 2.
--require-all does not run missing matrices. These are unsigned saved-fixture totals,
not independent stochastic samples, paired model comparisons or a reliability estimate.

## Matrix catalog and compatibility

`browser_catalog.py` is the immutable source for matrix names, flags, ordered task/
scenario/mode batches, resource limits, legacy flag requirements and budget-metadata
requirements. CLI options/help counts, execution selections, audit selections and suite
coverage derive from that catalog. Common run deadlines remain in the shared budget helper.
Existing CLI flags and saved matrix identities retain their behavior.

Catalog checks pin normalized ordered-batch fingerprints from the preceding implementation
for all six matrices, independently check the six task IDs and 130-control total, and
verify CLI dispatch/help and immutable definitions. Expected task/fault outcomes remain
separately specified in browser_controls.py rather than being inferred from the catalog.
Saved legacy evaluations still require their original indexed/multi_event flags while
later optional flags default to false. Unknown, non-boolean or conflicting runtime
selection flags fail before execution artifacts are created.

## Versioned matrix contracts

New evaluations use controls.json schema 2 and require a matrix_contract header with
version 1, matrix name and SHA-256 identity. The canonical payload covers the installed
corpus fingerprint, matrix selection flag/name, ordered batches, common/full budgets,
mock/dynamic configuration and separately declared expected outcomes. Artifact paths,
run IDs, timestamps and display-only catalog descriptions are excluded. This identifies
the evaluation contract, not the complete implementation or its author.

Audits compute the current identity before interpreting nested batches. Reports show
matched, mismatch, missing, invalid or unsupported_version explicitly; mismatches and
unsupported/malformed/missing required identities reject the evaluation and withhold
outcome counts. JSON retains current/saved identities when well-formed, and suite text
shows each evaluation's contract status. No nested evidence is interpreted under a
contract that differs from the currently installed declarations.

Schema-1 evaluations without a header remain supported and are labeled legacy_missing.
Their nested evidence is still checked against current definitions, but historical
contract identity cannot be established. Auditing never adds a header or rewrites old
files. A schema-1 file with an explicit header must still match it; absence is not the
same as a malformed header. Schema-2 files cannot silently omit the required identity.

Contract hashes are unsigned identifiers, not signatures. Someone rewriting metadata,
including downgrading a schema version, and all matching evidence can evade these checks.
They do not authenticate provenance or replace the nested file/state/trace audits.

## Inspecting installed contracts without evaluations

```powershell
.\.venv\Scripts\veriagent.exe inspect-browser-matrices
.\.venv\Scripts\veriagent.exe inspect-browser-matrices --matrix indexed --format json
```

The read-only inspector lists all six installed matrices by default, or the unique matrix
names selected with repeated --matrix options. Text shows CLI flags, control/batch counts
and full versioned identities. JSON also includes ordered batch selections and budgets.
The identity function is the same one used to write and audit evaluation headers, so the
output can be compared with a saved matrix_contract without generating a new evaluation.

The command reads the installed corpus/declarations only. It creates no artifacts,
constructs no provider and launches no browser/evaluation; redirect stdout explicitly to
save a copy. Unknown names, empty programmatic selections and duplicate selections are
rejected. Counts describe declared controls, not newly executed trials. Printed identities
remain unsigned declaration fingerprints, not signatures or implementation hashes.

## Requiring a matched contract

```powershell
.\.venv\Scripts\veriagent.exe audit-browser-controls <evaluation-directory> --require-contract
.\.venv\Scripts\veriagent.exe review-browser-controls <evaluation-directory> --require-contract
.\.venv\Scripts\veriagent.exe review-browser-suite <directories...> --require-contract
```

The optional strict policy requires matrix_contract status matched for every selected
evaluation. A schema-1 evaluation without an identity remains labeled legacy_missing,
but fails matrix_contract_required before nested interpretation. Strict review withholds
counts and exits 1; it does not rewrite or upgrade legacy data. Default review still
accepts otherwise valid legacy evidence with its explicit label. Malformed or mismatched
explicit identities remain rejected regardless of the optional flag.

JSON records require_contract and text reports state the selected policy. In suites,
one unmatched evaluation withholds all suite totals. --require-contract applies to the
selected evaluations only; --require-all independently requires all six matrix types.
The two options can be combined. Requiring a matched unsigned identity does not authenticate
provenance or establish reliability, and no new browser/API work is performed by review.

## Contract-policy coverage in suites

Suite JSON includes contract_coverage with scope selected_evaluation_inputs: total inputs,
matched identities, legacy_missing identities and unverifiable identities. Text prints
the same counts. Mismatch, missing, invalid, unsupported_version, not_checked and unknown
future statuses belong to unverifiable, while per-evaluation reviews retain the exact
status and failure details.

These counts remain visible when strict policy rejects legacy evidence or other evidence
checks withhold task totals. They count inputs, not distinct matrices or executed controls.
Two duplicate matrix inputs can therefore have two matching headers while distinct matrix
coverage stays one and suite selection fails. A matching header can also coexist with a
failed nested file audit; matching identity counts never override evidence failures.
Task outcomes, accepted matrix coverage and contract metadata coverage remain separate.
