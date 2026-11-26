# Consolidated fixed-mock findings and review handoff

Prepared 2026-11-26 by the implementing assistant. Four completed studies now have
portable evidence. The [handoff index](review/research-handoff.json) binds each plan,
result record, package metadata, archive and checker, plus the separate interrupted
decision-budget attempt. External review is unassigned; this is an implementer summary.

## What the studies establish locally

| Study | Assigned scope | Recorded finding | Boundary |
| --- | --- | --- | --- |
| [Bounded oracle](BOUNDED_ORACLE_RESULTS.md) | 72 dynamic mock conditions | All 28 predicted quota denials occurred; ten denied runs still met their final goals | Admission semantics, not general recovery quality |
| [Common corpus](REFLECTION_COMPARISON_RESULTS.md) | 96 runs; 24 per fixed mock arm | Recover and reflection each met 19/24 goals; reflection claimed 14/24; baseline made ten false claims | Shared caps did not equalize trusted information or work |
| [Decision caps](DECISION_BUDGET_RESULTS.md) | 288 runs at 4/8/12 decisions, actions fixed at eight | Reflection met 11/19/19 goals and claimed 4/14/15; four achieved-goal action-cap stops remained at twelve decisions | New cells were executed; prior and partial attempts were not pooled |
| [Action caps](ACTION_BUDGET_RESULTS.md) | 288 runs at 8/10/12 actions, decisions fixed at twelve | Reflection met 19/19/19 goals and claimed 15/19/19; ten actions removed four achieved-goal budget failures | Fixed thirteen-drop configuration; historical reference used nine |

The common finding is that final persisted goal satisfaction, final claims and terminal
budget outcomes are different measurements. A quota denial can follow a successful write.
A policy can reach a goal and stop before confirmation/finishing. A misleading ordinary
acknowledgement can support a false claim. Keep all three measurements rather than choosing
the most favorable one as the single success label.

Reflection's trajectory illustrates that distinction. Each row below has its own 24-cell
denominator; repeated settings were newly executed and are not additional independent
samples to pool.

| Study and caps | Goals met | Final success claims | Achieved-goal budget failures |
| --- | ---: | ---: | ---: |
| Common corpus: 8 actions, 8 decisions | 19/24 | 14/24 | 5/24 |
| Decision study: 8 actions, 4 decisions | 11/24 | 4/24 | 7/24 |
| Decision study: 8 actions, 8 decisions | 19/24 | 14/24 | 5/24 |
| Decision study: 8 actions, 12 decisions | 19/24 | 15/24 | 4/24 |
| Action study: 8 actions, 12 decisions | 19/24 | 15/24 | 4/24 |
| Action study: 10 actions, 12 decisions | 19/24 | 19/24 | 0/24 |
| Action study: 12 actions, 12 decisions | 19/24 | 19/24 | 0/24 |

Ten versus eight actions changed claims in pair_done and mixed_status under silent_drop/
transient without changing final SQL truth. Twelve versus ten added work without changing
these outcomes. Those are fixed-policy observations, not general action-budget advice.
Original stopping semantics remained unchanged, including no free finish after an action cap.

Work was not equal across arms. In the common-corpus study, reflection used 130 ordinary
actions and 163 decisions; recover used 92 actions, 92 decisions and 70 trusted checks
covering 112 logical target rows. In the action study, reflection's totals increased from
137 actions/171 decisions to 147/185 and 152/190. Keep ordinary reads/writes, trusted
calls/rows, corrective admissions and time separate. All model calls/tokens were zero;
there is no metered LLM or dollar-cost evidence here.

## Evidence routes and denominators

| Evidence | Portable review instructions |
| --- | --- |
| Bounded-oracle complete attempt | [Package and external manifest binding](BOUNDED_ORACLE_PACKAGE.md) |
| Common-corpus complete attempt | [Package and external manifest binding](REFLECTION_PACKAGE.md) |
| Decision-cap complete attempt and retained interruption | [Separate package bindings and coverage](DECISION_BUDGET_PACKAGE.md) |
| Action-cap complete attempt | [Package and external manifest binding](ACTION_BUDGET_PACKAGE.md) |

There are five archives for these four studies. The interrupted decision-cap attempt
retains 206 completed rows and an unknown next assignment after Windows manifest replacement
failed. It is distinct from the separate completed 288-run attempt. Its outcomes and
denominator are not pooled. The earlier 144-run static/dynamic comparison is historical
context in the [review packet](RESEARCH_REVIEW.md), not a fifth portable study in this index.

Use each reviewed external manifest hash when auditing. Embedded source snapshots are
never executed. Local replay/SQL consistency and checksums do not establish authenticated
provenance or independently reenact fault delivery. Inspect raw evidence after an audit
passes, including failed goals, false claims, no-op writes and achieved-goal budget stops.

The action study held persistent faults at thirteen across caps. Earlier eight-action
studies used nine. Both exceed every possible eight-action write count, but configured
and unused counters differ. The recorded anchor comparisons cover outcomes/failures/
resource vectors and are descriptive; they are not exact-input replication claims.

## External review priorities

| Priority | Question | Evidence to inspect | Disposition |
| --- | --- | --- | --- |
| 1 | Does the SQL oracle match the original requested statuses and collateral scope? | Corpus, final state databases, native reports; title preservation is outside this oracle | Unassigned external review |
| 1 | Are fault timing, no-op writes and exposure labels appropriate? | Fault adapter, realized attempts, pre-fault statuses, unused counters and already/partially satisfied cases | Unassigned external review |
| 1 | Are stop/claim semantics and partial-attempt treatment represented honestly? | Native traces, action/decision/corrective flags, quota denials and both decision-cap attempts | Unassigned external review |
| 2 | Are resource vectors adequate for the proposed comparison? | Ordinary/trusted work and phase counts; excludes setup/final evaluator and total database work | Unassigned external review |
| 2 | What can generalize beyond this corpus and fixed policies? | One deterministic observation per cell; sequential follow-ups informed by prior findings | Unsupported beyond stated scope |
| 2 | What is required for a metered LLM comparison? | Provider/observation contract, usage bounds, prospective sampling/analysis and failure accounting | Not specified or executed by this handoff |

For a disposition, record reviewer/date, exact plan/archive/checker bindings, reviewed
items, disagreements, evidence references and follow-up decisions. The index deliberately
has no reviewer or approval entry. No external reviewer has been contacted.

## Remaining work

Prepare an opt-in metered reflection-provider contract and offline validation gates before
any live study. Preserve the mock comparator and existing native report distinction.
Specify usage/error/stopping accounting and a prospective live design separately; this
handoff schedules or authorizes no billable trial. External review remains pending.

No pooled reliability estimate, stochastic confidence, significance, causal verification
benefit, equal-information/dollar parity, LLM reflection quality or broad autonomous-agent
reliability follows from the present evidence. The latest software validation remains the
recorded 850-test broad suite and 318-test focused evidence run; tests are not task samples.
