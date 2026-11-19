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
