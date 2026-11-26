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

Completed fault/budget browser increment: 24 second-write drop/committed-error controls
across action and decision limits, distinguishing recovery admission, unfinished repair
and exact completion without replay. Offline audit/review support is included.

Completed pre-satisfied browser budget increment: 16 controls for already/partially
satisfied goals at action/decision limits 1/2, preserving seeded versions and explicitly
unused second-write faults, with audit/review support.

Completed browser suite-review increment: bounded offline review of distinct saved
matrices, explicit partial/full selection coverage, duplicate matrix/run rejection and
separate aggregate outcomes. Complete coverage can be required without rerunning trials.

Completed browser catalog increment: immutable declarative selections shared by CLI,
execution, auditing and suite coverage, with pinned prior batch-order fingerprints and
cross-layer consistency checks. Existing matrix behavior and saved evidence remain supported.

Completed browser contract-identity increment: schema-2 evaluations require a versioned
matrix/corpus/budget/expectation fingerprint, audits reject explicit contract mismatches
before nested interpretation, and reports label legacy schema-1 artifacts explicitly.

Completed browser contract-inspection increment: a compact read-only text/JSON catalog
command exposes current names, flags, counts, ordered budgets and identities without
generating evaluations or rewriting saved evidence.

Completed strict contract-review increment: optional matched-identity requirements on
evaluation audit/review and suite review, fail-closed totals under strict policy, and
explicit default legacy compatibility without artifact upgrades.

Completed suite contract-coverage increment: explicit input-level matched/legacy/
unverifiable identity counts, retained under strict-policy rejection or invalid evidence,
separate from task outcomes and distinct matrix selection coverage.

Completed suite output-schema increment: version-2 strict report models, exported JSON
Schema, runtime cross-field validation and corruption regressions separate metadata
coverage, selection policy and outcome totals.

Completed exported-report validation increment: bounded read-only JSON loading, strict
runtime validation, text/JSON diagnostics and explicit report-consistency scope without
reopening evidence directories.

Completed complete-evaluation portability increment: real nested audits after relocating
a fresh sealed evaluation, unchanged-byte checks and fail-closed relocated corruption
regressions.

Completed bounded archive-transfer increment: offline ZIP creation/restoration with
portable relative paths, resource limits, staged nested audits, no-overwrite outputs and
real Chromium evidence round-trip coverage.

Completed archive-inspection increment: read-only text/JSON directory metadata, declared
resource summaries, shared extraction preflight and explicit separation from payload CRC
verification and evidence auditing.

Completed offline-workflow validation review: exact integer schema versions and original
ZIP filename checks close reproduced type-coercion and NUL-truncation gaps.

Completed legacy archive compatibility increment: default byte-preserving legacy transfer,
strict rejection without publication, modern missing/mismatched identity rejection and
real nested-evidence downstream policy coverage.

Completed archive filesystem-failure review: injected staging, audit and publication
failures preserve inputs and competing outputs while cleaning temporary trees; missing
output parents and destinations created during audit are covered.

Completed offline operator-guide increment: a compact review/export/validation/transfer
workflow, explicit result-field meanings, policy choices and verified exit-status table.

Completed operator-workflow smoke increment: separate CLI processes cover catalog
inspection, evidence review/export, report validation, archive/inspect/restore and re-review,
including partial-selection rejection versus valid exported-report consistency.

Completed research-priority review: RESEARCH_REVIEW.md and a machine-readable pinned
corpus/matrix/source snapshot distinguish local mechanism evidence from pending external
review, missing self-reflection/budget ablations and prospective stochastic study design.

Completed prospective offline comparison specification: two explicit 72-run mock batches,
pinned selections/budgets, per-condition outcomes, failure handling and missing comparator/
ablation boundaries. CLI argument paths were checked without executing trials.

Completed specified mock comparison: 72 static and 72 dynamic runs, pinned coverage/
budget checks, read-only final-state reconciliation and per-condition descriptive results.
A OneDrive-interrupted attempt is retained separately and the output-path amendment is
disclosed. Partial-satisfaction exposure differences are recorded, not treated as recovery.

Completed comparator/ablation design: proposed observation-only self-reflection semantics,
explicit missing implementations, separate tool/decision/oracle/recovery accounting and
exposure-aware analysis rules. Read-only trace spot-checks confirm differing verifier work.

Completed verification-work ledger increment: bounded single-run trace reconciliation,
separate action/decision/recovery/oracle units, unknown error-path work and a hash-bound
derivation for all 144 completed comparison runs.

Completed standalone verification-admission semantics: strict optional call/target-row
limits, pre-work reservations, no refunds on errors and unknown partial-work accounting,
with acceptance tests. The ledger remains disconnected from execution and CLI.

Completed opt-in trusted-verifier adapter: original target reservations precede SQLite
connections, complete/missing/mismatched snapshots settle work, and errors/cancellation
retain reservations and unknown work. Existing agents and CLI remain unchanged.

Completed explicit agent admission integration: fresh run/task binding, opt-in limit
configuration and durable admitted/completed/error/denied snapshots; denial maps to honest
budget failure with no stale verification, while ordinary defaults remain on their old path.

Completed offline admission-trace reconciliation: replay strict limits and state changes,
pair outcomes, reconcile work counters and reject dishonest denial/error reports without
executing an oracle. Default traces and historical work derivations remain unchanged.

Completed prospective bounded-oracle specification: 72 dynamic mock conditions across
three tasks, two scenarios, three modes and four quota profiles, with pinned source/budget
inputs and 28 predicted denial boundaries validated before running agents.

Completed bounded-oracle runner/execution: all 72 mock conditions completed and reconciled,
28 predicted denials matched, and final-state success remains separate from budget denial.
Raw artifacts, per-condition results and interruption/expectation-retention tests are recorded.

Completed portable raw-evidence release: a 436-file/72-run ZIP is included in the repo,
with external manifest binding, file/SQLite/trace/admission/state rechecks and blocked-
original-path relocation validation. Source/corpus/runner bytes and checksums travel with it.

Completed mock-only reflection prototype: separate typed execution/corrective states and
report, original/final claims, fresh ordinary read-back, safe replay guards, shared caps and
no trusted verifier access. Spoofed-read false claims are retained as a limitation.

Completed prospective common-corpus specification: 96 mock conditions, four distinct
report/policy arms, shared caps with explicit information differences, balanced fixed
arm positions, separate resource vectors and exposure-aware analysis gates.

Completed offline reflection-trace reconciliation: typed phases, shared counters, claims,
authorization and fresh-read/idempotence retry guards, with separate final-state truth.

Completed mock-only common-corpus runner and pretrial execution lock: exact ordered
coverage, native reports, independent final SQL audit, separate resource vectors and
partial-attempt retention. Published plan/source pins remain unchanged.

Completed frozen common-corpus execution: 96 assigned runs and independent evidence
rechecks, with condition-level truth, claims, resources and exposure retained. Reflection
and recover each reached 19/24 goals; reflection retained five achieved-goal budget stops.

Completed portable common-corpus evidence release: all 96 runs in a 583-file archive,
with bound corpus/source snapshots, relocated replay/SQL checks and corruption rejection.
Published plan, execution lock, raw evidence and measured results remain unchanged.

Completed research review packet refresh: both portable studies, measured findings,
reviewer evidence routes and explicit pending external-review/LLM/ablation boundaries.

Completed prospective mock decision-budget specification: 288 assigned fresh conditions
at decision caps 4/8/12, fixed action/information policies, balanced ordering and explicit
joint-cap diagnostics. No new trials executed.

Completed mock decision-budget runner and pretrial binding: exact 288-condition validation,
fresh native execution, trace/SQL/resource reconciliation, separate joint-cap diagnostics
and partial-attempt retention. The planned study remains unexecuted.

Completed frozen decision-budget execution and independent audit: 288 completed conditions,
cap contrasts and prior-reference checks, with a separate retained 206-run interrupted
attempt. Extra decisions left goal truth unchanged at 12 versus 8; four reflection
achieved-goal action-cap stops remained.

Completed portable decision-budget release: separate 288-run complete and 206-run partial
archives, with bound execution sources/reference inputs and explicit prefix/unknown status.
No attempt outcomes or coverage claims are pooled.

Completed prospective action-cap sensitivity specification: 288 fresh conditions at
action caps 8/10/12 with twelve decisions, unchanged information policies and a fixed
fault-generation ceiling so persistent-drop counters do not vary with the intervention.

Completed dedicated action-cap runner and pretrial binding: fixed fault ceiling across
caps, fresh native execution, trace/SQL/resource/fault/stop reconciliation and retained
partial attempts. The planned study remains unexecuted.

Next research increment: execute the frozen action-cap study and independently audit
coverage, matched sensitivity, achieved-goal stops and resource/exposure findings.
Benchmark external review and optional stochastic comparisons remain separate pending work.
