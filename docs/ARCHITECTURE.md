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

## 005: No pretend LLM integration

`PlanningProvider` is the initial provider abstraction. `MockProvider` is explicitly named
and the CLI only uses it. A future OpenAI adapter will obtain credentials from environment,
use bounded requests, parse structured output, record model/version/tokens, and keep
credentials out of traces. Adding an untested paid path would weaken Phase 1 reproducibility.
