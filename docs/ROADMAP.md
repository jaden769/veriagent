# Development roadmap

1. **Phase 1 — deterministic vertical slice:** typed schemas, constrained mock planner,
   SQLite sandbox, tool boundary, three agent modes, independent state checks, bounded
   selective recovery, durable traces, CLI, local API and automated tests.
2. **Phase 2 — real LLM:** implement the planning-provider protocol with environment-based
   OpenAI credentials and schema-validated responses. Add usage records and caller-supplied
   pricing, model/request timeouts, varied task instructions, structured tool selection,
   and prompt-injection / authorization tests. Keep the offline provider.
3. **Phase 3 — browser:** authorized local applications, Playwright adapter, DOM observations
   and independent application-state oracles. Resolve uncertain commits before retrying.
4. **Phase 4 — benchmarking:** baseline, self-reflection, verification, adaptive recovery;
   identical tasks, fault schedules and budgets; repeated stochastic trials and uncertainty.
5. **Phase 5 — release:** ablations, failure analysis, dashboard, reproducible technical
   report, architecture documentation and portfolio demonstration.

Completed Phase 2 milestone: an optional metered OpenAI planning adapter, strict response
schemas, request/output limits, sanitized planning failures and adversarial-plan tests.
The actual SDK is exercised against an in-memory HTTP transport. A user-run live static
smoke passed on 2026-11-19 (see VALIDATION.md). This is not completion of all Phase 2 objectives.

The isolated `smoke` command is ready for that live check and has passed offline. It
captures fresh state, injected-fault detection, recovery, an audit and package metadata.
Credentials remain confined to the user's terminal. Its saved live result has now been
inspected and confirms fault detection, recovery and the independent final-state audit.

Completed next increment: offline and optional OpenAI requirement proposals, explicit
content-bound review, execution against the reviewed requirements, interpretation usage
capture and a 24-case varied-instruction fixture. The offline grammar is intentionally
limited; ambiguity produces clarification. Live interpretation quality is untested.

Completed dynamic increment: an optional observation-driven engine, strict single-function
decisions, per-action authorization, verified repair, action/decision/recovery limits,
normalized feedback and aggregate model usage. The offline mock and SDK transport tests
exercise controlled failures, malicious decisions, premature finish claims and ambiguous
commit acknowledgments. The static engine remains the default.

Completed model-budget increment: a per-run admission ledger, cumulative output allowance,
observed total-token and estimated-cost thresholds, unknown-usage rejection and explicit
budget evidence in reports/traces. Token/cost observations may overshoot in the current
request; no exact billed-dollar guarantee is claimed. Tests use synthetic usage only.

Completed process-execution increment: an optional fixed-tool worker, parent-side deadline
termination/reaping, before/after-commit fault injection, authoritative ambiguity checks
and terminal failure on unconfirmed cleanup. Actual worker tests cover both agent engines
on Windows. This is deadline isolation, not a whole-agent real-time or OS security guarantee.

Completed boundary-evaluation increment: a packaged 24-case offline adversarial/fault
corpus, independent final-state oracle, explicit expected labels, separate baseline
controls, context-canary checks, artifacts/provenance and tests that deliberately weaken
guards to prove violations are reported. It measures finite local boundaries only.

The bounded live dynamic smoke also passed on 2026-11-19, including injected-fault
detection, recovery and independent audit (see VALIDATION.md).

Completed live reviewed trial: explicit two-target interpretation, matching approval
digest, dynamic execution with injected dropped-write recovery, and a separate read-only
final-state audit. The synonym-based objective requested clarification; broad language
accuracy remains unestablished. See VALIDATION.md for artifacts and separate usage totals.

Completed benchmark infrastructure: fixed scenarios, fresh repeated trials, explicit
per-run limits, execution-only accounting, independent SQL audits and nominal Wilson
intervals. Defaults to deterministic mock; live execution requires explicit provider and
output allowance. Partial evidence survives interruption; provider diagnostics stop a batch.
See BENCHMARK.md. No live repeated-trial batch has been run.

Completed varied-task increment: six manually specified task/initial-state cases,
multi-target audits, per-task summaries, corpus provenance, and configured/remaining
fault counters. Already-satisfied success is distinguished from actual recovery.

Completed indexed-fault increment: second-write drop/transient profiles and a two-drop
profile, with explicit planned events, realized write positions/targets and unused events.
Legacy defaults remain unchanged; unreached events are not counted as injections.

Next milestone: independent review of the task corpus and fault definitions before
optional stochastic comparisons. A local implementation review added conditional metric
denominators and fault-mismatch eligibility checks; external review remains pending.
Do not infer reliability from the three successful live trials.
Broader generated attacks, independent live task corpora and
stochastic reliability comparisons remain future work before research claims. No live model
quality or general injection resistance is established. No general browser agent, dashboard,
learned verifier, or broad reliability claim is included.

Completed first Phase 3 slice: optional headless Chromium, a loopback issue UI, fixed
DOM tools, independent SQLite verification, browser screenshots/DOM artifacts and real
browser regression checks. Both engines can recover the controlled dropped write using
the mock provider. See BROWSER.md. No live-model browser trial has been run.

Completed reviewed-browser increment: explicit execute backend, approved multi-target
UI actions, direct final-state/collateral audits, original-claim preservation and evidence
bundles. Tests cover unrelated changes, baseline false claims and unconfirmed cleanup.

Completed browser ambiguity increment: controlled stale rendered status and post-commit
HTTP-error profiles, bounded DOM/application event evidence, and no-replay checks. Dynamic
multi-target progress now handles confirmed commits with errors without spending retries.

Completed pending-response timeout increment: real browser action deadlines before/after
commit, bounded handler release, no-late-commit rejection, and replay-versus-progress checks.
Dynamic reviewed trials cover mixed statuses, reopening and partially satisfied goals.

Completed browser corpus batch increment: bounded offline task/scenario/mode selections,
fresh per-trial state, partial manifests, provenance and explicit realized fault exposure
with separate audited outcomes and claim denominators.

Completed browser controls increment: a 42-trial dynamic mock matrix covering the six
tasks/profiles in recovery mode and single-target baseline controls, with explicit
expected outcomes, mismatch evidence and exact coverage checks.

Completed indexed browser increment: four second-write profiles, explicit planned/realized
positions and unused faults, a 24-control dynamic matrix and both-engine multi-target
no-replay regressions.

Completed multi-event browser increment: two-event write schedules, exact pending-event
evidence, a 12-control retry-exhaustion matrix and explicit per-target status/version
audits preserving partial progress.

Completed browser evidence increment: per-trial hash inventories and bounded read-only
offline audits for missing/altered files, reviewed requirements, trace/event consistency
and independently recomputed saved-state outcomes. Inventories are unsigned.

Completed batch evidence increment: relative trial/inventory bindings, bounded offline
whole-batch audits, exact coverage/unique-run checks and saved-summary reconciliation.

Completed control-evaluation evidence increment: relative nested-manifest bindings and
offline reconciliation of all supported matrices, expected outcomes, mismatch details
and nested batch/trial evidence.

Completed browser review increment: compact text/JSON reports derived from full offline
audits, with separate expected/unexpected task failures, expectation mismatches and
bounded evidence gaps. Invalid evidence withholds aggregate outcomes.

Completed browser budget-boundary increment: 12 clean dynamic action/decision-limit
controls, exact completion boundaries, explicit partial-progress/failure evidence and
offline audit/review support with prior-evaluation compatibility.

Next browser increment: combine second-write faults with action/decision boundaries to
check recovery admission and preserved progress. Benchmark external review and optional
stochastic comparisons remain separate pending work.
