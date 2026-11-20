# Architecture decisions

## 001: Small explicit loop over an agent framework

The research variable is verification and recovery. An explicit loop makes actions,
termination and evidence observable. Pydantic validates boundaries; standard-library
SQLite persists both application state and traces in separate files. FastAPI is only
a local application surface; execution uses an in-process adapter to remove network noise.
PyTorch, browser tooling and Docker add no value to the controlled Phase 1 experiment.

## 002: Requirements precede and constrain plans

The mock provider turns a constrained objective into immutable requirements. Plan writes
must cover those requirements and cannot change their issue IDs or statuses. Dependencies
must refer to earlier unique steps. Expected outcomes in a plan are useful annotations,
but the verifier always checks original task requirements. A Phase 2 task interpreter
will still need user-intent validation; plan validation alone does not solve that problem.

## 003: Tool acknowledgments are not evidence

The fault injector sits in the mutation tool, before commit. The verifier does not call
that tool or accept its observations. It opens a separate `mode=ro` SQLite connection
and reads all target rows inside one snapshot transaction. The evaluator uses the same
state predicate after each run; it is a ground-truth oracle only for this simple status
domain, not a separate statistical estimate of verifier accuracy.

## 004: Conservative bounded recovery

Recovery revises only unsatisfied steps and increments the plan revision. Trust in
idempotency comes from the executor registry. There are three independent bounds:
action count, retry count and cooperative elapsed time. A transient pre-commit fault and
a missing persisted update can be repaired, while missing issues and denied tools stop.
There is no exponential backoff because injected faults are deterministic and immediate;
real transport retries will require bounded backoff and jitter.

## 005: Explicit optional LLM integration

The Phase 1 demo continues to use `MockProvider`. The first Phase 2 milestone adds an
optional `OpenAIProvider` using the Responses API and a strict JSON Schema built from
Pydantic contracts. Wire schemas use homogeneous lists; local plan schemas retain immutable
tuples and dependency validation. Every nullable wire property is still required.

The adapter uses `responses.create` and validates response text locally, preserving usage
from completed API responses even when the plan is rejected. It makes at most one request
per run with SDK retries disabled. The planner receives a bounded timeout and output token
limit; execution checks the remaining run deadline before any tool action. The CLI closes
the client even if local sandbox initialization or execution fails.

The constrained parser establishes original requirements for direct runs before a paid
planning call. Broader objectives instead use a separate proposal and explicit content-bound
review; see decision 006. Only the resulting authorized targets and statuses can enter a
valid plan. The model never receives observations or issue titles, reducing the injection
surface; full prompt-injection resistance is not claimed. Dynamic selection receives
normalized status feedback and verifier evidence, as described in decision 007.
Invalid plans terminate with zero tool actions, a planning-failure event and a terminal report.

Credentials come only from the environment; the production endpoint is pinned. API errors
are sanitized before tracing. Tokens and actual response model are recorded where returned.
Cost uses caller-supplied input/output prices; absent prices or usage produce null, never
invented zero. Cost is approximate: cache discounts and service-tier effects are not modeled.

References: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [SDK retry/timeout configuration](https://github.com/openai/openai-python#retries).

## 006: Interpretation proposes; review authorizes

Natural-language interpretation is an independent step that never calls application tools.
The offline interpreter uses a conservative full-match grammar; the optional OpenAI
interpreter returns structured requirements or a clarification. Both require explicit
issue IDs. Requirements may not add or omit an explicitly mentioned target, and ambiguity
must be resolved before execution. Model output is untrusted even when its schema is valid.

A proposal stores original text, interpreted requirements and interpretation usage. Review
displays normalized content and its canonical SHA-256 digest. The execute command requires
that digest, validates a single bounded file read, and retains the parsed immutable proposal.
This prevents accidental execution of content changed since review, not a malicious local
actor or a mistaken human approval. No signature, identity or secret capability is implied.

Execution traces bind the reviewed digest to the task before planning. The ordinary planner
validation and tool policy remain in force. Interpretation and planning usage are separate
stages so a reused proposal does not silently add historical model calls to a new run.

## 007: Separate dynamic engine with per-decision authorization

The static engine remains unchanged as the default experimental configuration. The
optional dynamic engine requests one typed action or a finish claim at a time. The
OpenAI adapter uses strict Responses function tools and fresh requests with a bounded
projection of recent feedback; it does not maintain a remote conversation. All function
calls are parsed and validated locally before the engine checks task authorization.

Only approved targets and final statuses can be selected. The executor's trusted policy
determines tool permission and idempotency, and the engine separately authorizes retries
for an unmet target after a recoverable failure. Completed targets cannot be rewritten.
No model argument can weaken these checks. Independent verification, not model finish
text or a tool acknowledgment, establishes success in verified modes.

Initial verification avoids requests for already completed tasks. Verification after a
write also resolves ambiguous acknowledgments. Failed evidence reads clear the prior
verification instead of treating it as current. Action, decision, retry and cooperative
time limits bound reads, invalid decisions and false finish claims. A decision limit
bounds possible model requests, not exact dollar expenditure.

Model input includes task requirements, counters/budgets, status-only feedback and typed
verifier evidence. Arbitrary issue titles, messages and exception text remain outside
that projection. This is a tested boundary for this adapter, not a general proof against
prompt injection. Per-decision traces retain usage and call IDs; aggregate usage preserves
unknown values and is reset for each run.

## 008: Admission ledger at the model transport boundary

All OpenAI operations share a per-run ledger. Engines and the proposal workflow invoke
`begin_run()` before their first operation; custom provider protocols expose that lifecycle
and optional budget state. The mock implements it without paid-model accounting.

The adapter checks limits before transport, reserves the next output allowance by capping
the API request, and records returned usage before parsing output. Total-token and cost
thresholds are observed after a response, so they can overshoot within that request. Such
a response cannot authorize an action. Equality can finish a task; only a subsequent
request is rejected. Missing usage needed by an active limit stops execution closed.

Admission failures record zero attempts. Transport errors record an attempt with unknown
usage. Budget failures remain distinct from planning errors and their snapshots persist
alongside token/cost traces. Reusing a provider resets the ledger per run, so this is not
a global workflow or account spending quota. Caller prices are required for cost limits;
cached-token discounts and billing tiers remain outside the approximate cost model.

## 009: Killable workers for fixed sandbox tools

The default executor stays in-process for simple deterministic experiments. The optional
process adapter launches one installed worker module per action and exchanges validated
UTF-8 JSON. Permissions are checked before launch. The worker receives only a fixed
sandbox action and explicit database path; no arbitrary Python callable is serialized.

The parent enforces the wait deadline, kills on timeout, and confirms exit with a bounded
cleanup wait before returning a retryable timeout. Unconfirmed cleanup marks the observation
unsafe to continue; both engines terminate without a success claim, regardless of current
state. Ordinary killed-worker timeouts still require authoritative verification: the write
may already have committed. Only idempotent unmet requirements can be retried.

Fault counters remain in the parent and are reserved per dispatched write, so one-shot
faults cannot be reset by process restart. Python isolated mode and a small environment
allowlist keep ambient model credentials and Python injection settings out of the worker.
This is not a filesystem or network security boundary, and does not cover model calls,
verifier reads, OS launch stalls or arbitrary child process trees.

## 010: Scripted adversarial cases with a separate final oracle

The packaged offline corpus exercises production boundaries through the same local
function-call validator used by the OpenAI adapter. Scripted fixtures never construct an
API client. Tool/verifier faults are explicit typed configuration, not arbitrary plugin
code. The executor and engine continue to enforce original target/status constraints.

A final read-only SQLite snapshot bypasses injected tool reads and evidence failures.
The evaluator compares actual persisted requirements and unrelated status/version rows,
then checks declared expectations without replacing observed outcomes. Baseline
false-success controls are retained separately. Canary cases must actually observe their
payload before successful exclusion from provider context can count as a pass.

Fresh case directories, normalized fixtures, traces, captured provider inputs and
fixture/source fingerprints make failures inspectable. Tests weaken guards, lie about
verification and leak markers to demonstrate that the evaluator can fail. This is finite
local boundary validation, not live LLM robustness, independent statistical benchmarking
or an attestation of a secure runtime.

## 011: A fixed local browser tool adapter

Phase 3 starts with a known loopback application and the existing action schema, rather
than arbitrary-site automation. A new headless Chromium/context and owned OS-assigned
loopback server isolate each smoke's application state and cookies from personal browsing.
Browser tools navigate fixed issue pages, read DOM fields and operate the status form;
model actions cannot supply selectors, scripts or URLs. Request routing allows only the
fixture's known paths/methods on its exact origin, with service workers blocked. This is
not an OS security boundary or a general browser egress guarantee.

The page treats a successful PATCH acknowledgment optimistically. Independent SQLite
verification therefore remains essential: a UI claim can say done while the application
state is still open. The existing trusted task/status authorization, idempotency policy
and retry limits apply unchanged. Browser waits share the remaining action deadline;
timeouts remain potentially ambiguous commits and require state resolution. Browser
startup/evidence capture and shutdown are outside the agent's cooperative run deadline.

The optional browser extra and matching Chromium binaries are explicit installations.
Default commands remain mock/offline. Smoke evidence includes before/after screenshots,
final refreshed DOM, package/browser versions and the original state/audit/traces. A
capture failure is recorded separately from agent/audit outcomes. Neither screenshot
appearance nor DOM acknowledgment is accepted as persisted-state proof. The slice does
not implement arbitrary-site planning, a vision model or personal-profile access.

Reviewed execution now supports an explicit browser backend. Approval validation precedes
state/provider/browser creation; the exact immutable proposal supplies the task. A separate
post-cleanup read-only SQL audit checks target statuses, target titles and entire unrelated
rows. Original agent reports remain intact even when the evaluator rejects collateral
effects or cleanup uncertainty. Overall CLI success is distinct from an agent's claim.
Per-target captures, proposal digest and before/after rows are retained in an evidence
bundle. Worker isolation cannot be combined with browser mode.

## 012: Resolve mutation outcomes before assigning retry budget

Browser fixture profiles separate rendered status and transport/service acknowledgment
from durable SQLite effects. A stale DOM can disagree with a successful commit, and a
post-commit HTTP error can hide one. Browser tools return actual rendered status and
normalized errors; hidden application fault/commit logs are retained only as evaluator
evidence. Initial unsatisfied goals are excluded from post-write fault detection.

For protected dynamic execution, a verified completed mutation target permits progress
to other unmet targets even when its observation reported an error. No retry is needed
for that target, and the existing completed-target guard prevents replay. This check
follows the unsafe-cleanup stop boundary and does not override it. Recoverable unmet
targets still require the existing mode, idempotency, retry/action/decision/time budgets.
Tests exercise zero-retry multi-target progress for transient and timeout observations.
The controlled lost-ack profile returns HTTP 503 after commit. Pending-response profiles
now hold an actual HTTP handler across the browser action deadline, on either side of
commit. Timeout and cleanup callbacks release the handler without taking its write lock;
a ten-second safety release bounds abandoned waits. Pre-commit held requests reject
without a late write; post-commit held requests retain the committed state. Event evidence
distinguishes action-timeout releases from cleanup/safety releases. This is a controlled
browser action deadline, not a general remote-cancellation or TCP-timeout model.
The offline browser corpus runner (`browser_batch.py`) reuses immutable fixed task
requirements and initial states, never model-generated evaluation targets. It runs each
task/scenario/mode/repeat in fresh state with MockProvider and the existing browser audit
path. Atomic manifests retain provenance, completed trials and interrupted trial paths.
Aggregates distinguish claims, independently audited state, overall execution outcomes and
realized fault exposure; already-satisfied/unreached profiles do not imply recovery.
Browser control evaluation (`browser_controls.py`) compares a fixed dynamic mock matrix
against separately specified initial changed-target counts and profile outcomes. It
retains expectation mismatches separately from task success: an intended baseline false
claim can pass the control while failing the independent state audit. Exact matrix
coverage rejects missing/duplicate combinations; interrupted evidence remains partial.
Indexed browser profiles count mutation attempts under the fixture write lock. Four
second-write profiles inject only at attempt 2 on a changing target; no-ops and missing
targets consume positions without moving the scheduled event. Batch evidence retains
planned and realized positions plus pending fault counts. A separate 24-control dynamic
evaluation checks both exposed two-target cases and unused zero/one-target schedules.
Multi-event browser profiles use the same position map for two faults at attempts 2/3.
Their separate control matrix includes retry limits 0/1/2 and compares independent final
target statuses/versions and collateral checks, rather than treating a bounded partial
failure as total loss of progress. Scenario labels and schedules remain fixture evidence,
not provider feedback. Existing default and indexed matrices keep their original scope.
Reviewed browser execution now seals its local evidence files with a bounded SHA-256
inventory after writing the result. The offline browser evidence auditor reads leaf
filenames only, validates reviewed requirements and trace consistency, replays saved
application events and recomputes the saved-state audit. Evidence validity remains
separate from successful task execution. This unsigned inventory detects byte changes
and inconsistencies; it is not authenticated provenance or a new live database query.
Whole-batch re-auditing binds relative trial directories to inventory hashes, rechecks
current-corpus tasks/initial states and trial configuration, rejects reused run IDs and
reconciles summaries from saved trial evidence. Absolute stored artifact paths are never
followed. Counter-based browser drops now record explicit injection labels for offline
exposure reconstruction. Manifest validity remains separate from successful task outcomes.
Control-evaluation audits add a parent layer: relative nested-manifest hashes, fixed
matrix/budget validation, cross-batch run uniqueness and regenerated expected-outcome
comparisons. They call the existing batch/trial auditors and keep evidence validity
separate from expectation matches. This preserves honestly recorded mismatches without
trusting a top-level passed flag or following stored absolute paths.
The browser review layer consumes only the complete audit result. It maps controls to
nested audited task outcomes, distinguishes expected failures from mismatched expectations
and withholds all outcome totals on invalid evidence or inconsistent trial mapping.
Text and JSON views share the same counts and relative references; no evidence is rewritten.
The budget-boundary control matrix adds action/decision limits to control identities and
validates clean two-target partial progress at limits 2/3 versus exact completion at 4.
Trial rows retain observed decisions and terminal failure. Parent audits bind the exact
budget and require boundary metadata, while preserving compatibility with earlier bound
evaluations whose default-budget rows lack the new optional fields.
The fault/budget matrix adds second-write drops and committed errors at limits 4/5/6.
Expectations distinguish no recovery admission, an admitted but unfinished repair, and
successful completion. A verified committed error needs no extra action or retry budget.
This extends matrix definitions/audits without changing the production agent loop.
The pre-satisfied budget matrix checks zero-action completion and selective remaining
work at limits 1/2. Expectations retain initial target versions rather than assuming every
goal needs a commit, and classify an unreached second-write schedule as unused rather
than recovered. Audit/review resource identities and metadata checks apply unchanged.
The suite review layer consumes fully audited evaluations and their unique run IDs.
It rejects repeated matrix types and cross-evaluation run reuse, reports missing matrix
types explicitly, and withholds aggregate counts on evidence or required-selection
failure. A partial selection can be reviewed without pretending it covers all six
matrices; --require-all validates coverage without generating missing evidence.
