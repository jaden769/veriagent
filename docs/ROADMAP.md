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

Next milestone: a reproducible repeated-trial benchmark with fixed scenarios, explicit
per-run limits, separate interpretation/execution accounting, and uncertainty reporting.
Keep live requests opt-in; do not infer reliability from the three successful live trials.
Broader generated attacks, independent live task corpora and
stochastic reliability comparisons remain future work before research claims. No live model
quality or general injection resistance is established. No browser agent, dashboard,
learned verifier, or broad reliability claim is included.
