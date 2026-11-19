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
The actual SDK is exercised against an in-memory HTTP transport. No paid request has
been made or validated. This is not completion of all Phase 2 objectives.

The isolated `smoke` command is ready for that live check and has passed offline. It
captures fresh state, injected-fault detection, recovery, an audit and package metadata.
API credentials and a model are not configured in the implementation environment, so no
live result is claimed.

Completed next increment: offline and optional OpenAI requirement proposals, explicit
content-bound review, execution against the reviewed requirements, interpretation usage
capture and a 24-case varied-instruction fixture. The offline grammar is intentionally
limited; ambiguity produces clarification. Live interpretation quality is untested.

Next milestones: the still-pending authorized live smoke test and reviewed-interpretation
trial when credentials are configured, followed by dynamic tool selection against the
same approved requirements and budgets.
Dynamic model-driven tool selection, model-driven replanning and full injection defenses
remain open. Do not expand tools until authorization and timeout behavior are independently
tested. No browser agent, dashboard, learned verifier, or broad reliability claim is included.
