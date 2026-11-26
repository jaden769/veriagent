# Research validation review packet

Prepared 2026-11-21; updated 2026-11-26 by the implementing assistant. External review
remains pending. This packet connects local implementation facts, recorded fixed-mock
findings and review priorities. It records no independent approval. The historical
[snapshot](review/offline-baseline.json) pins its original corpus, modes, matrix identities
and selected source hashes; later studies retain their own prospective bindings.

## Current evidence and open gaps

| Area | Available evidence | Remaining requirement before broader claims |
| --- | --- | --- |
| Execution mechanisms | Deterministic mock tasks, faults and independent final-state checks | Independent corpus/fault review and broader task coverage |
| Browser controls | Six fixed matrices, 130 declared controls, sealed nested artifacts | External review of expectations; controls are finite mechanism checks |
| Live integration | Individual user-run static, dynamic and reviewed checks | Repeated, prospectively specified model comparisons |
| Comparators | Completed 96-condition common-corpus comparison of four fixed mock policies | Live/metered reflection comparator and actual resource ablations |
| Metrics | Pinned assigned denominators; independent SQL outcomes separate from claims and exposure | Stochastic estimand, analysis plan and dependence assumptions for any live study |
| Transfer/review | Three portable study evidence sets, with the interrupted sensitivity attempt archived separately | External review; unsigned consistency does not establish authenticity or model reliability |

The latest broad complete-suite record is 850 passing tests; the latest focused evidence
regression run passed 269 tests. Subsequent additions were checked with focused suites,
not a new full run; see [validation history](VALIDATION.md). Test counts are software-validation evidence.
They are not independent task samples or a reliability denominator.

## Recorded studies and evidence routes

| Study | Assigned scope | Findings and review route |
| --- | --- | --- |
| Initial offline comparison | 144 static/dynamic mock runs | [Plan](OFFLINE_COMPARISON.md), [results](OFFLINE_COMPARISON_RESULTS.md), [verification-work ledger](VERIFICATION_WORK.md); historical execution pins remain unchanged |
| Bounded trusted oracle | 72 dynamic mock conditions across three tasks, two scenarios, three modes and four quotas | [Results](BOUNDED_ORACLE_RESULTS.md), [portable package and audit instructions](BOUNDED_ORACLE_PACKAGE.md) |
| Common-corpus reflection | 96 runs across six tasks, four scenarios and four fixed mock arms | [Results](REFLECTION_COMPARISON_RESULTS.md), [portable package and audit instructions](REFLECTION_PACKAGE.md) |
| Decision-cap sensitivity | 288 completed mock conditions at caps 4/8/12, plus a separate retained interrupted attempt | [Results](DECISION_BUDGET_RESULTS.md), [separate portable complete/partial packages](DECISION_BUDGET_PACKAGE.md) |

Start with each prospective plan, then its recorded results, external manifest binding
and archive audit. Inspect representative raw reports, traces and final SQLite states
after the package passes. The embedded runner sources are never executed by the auditors.
No fresh paid calls or study reruns are required to inspect these packages.

In the bounded-oracle study, all 28 predicted denials occurred. Ten denied runs still
ended with satisfied targets. The recorded 42 completed trusted checks and 55 known
logical target rows exclude setup and final evaluator work. These quota-boundary results
test admission semantics, not general recovery quality.

In the common-corpus study, baseline and verify each reached 9/24 goals; recover and
mock reflection each reached 19/24. Baseline made ten false success claims; the other
arms made none. Reflection claimed success in 14/24, with five achieved-goal budget
failures retained separately from its five unsatisfied persistent-drop budget failures.
No untargeted status/version changes were observed. Status/version truth does not establish
title preservation, which this oracle does not check.

Shared caps did not equalize information or work: reflection used 85 ordinary reads and
163 decisions, while recover used 46 ordinary reads, 92 decisions and 70 trusted checks
covering 112 logical target rows. These are totals over 24 runs per arm, not interchangeable
cost units. All model calls/tokens were zero. Equal 15-run fault eligibility counts per
arm do not establish equal exposure. One deterministic observation per cell supports no
stochastic interval, significance, causal effect or LLM-quality conclusion.

## Priority 1: review the fixed corpus and fault semantics

Read the raw [task corpus](../src/veriagent/scenarios/benchmark_tasks.json),
[sandbox fault adapter](../src/veriagent/benchmark_faults.py),
[browser schedules](../src/veriagent/browser_faults.py) and
[control expectations](../src/veriagent/browser_controls.py). Compare them against the
snapshot before recording conclusions; changed fingerprints require an updated review.

| Task | Requested targets | Initially unmet targets | Question for reviewer |
| --- | --- | --- | --- |
| `single_done` | ISSUE-1 done | 1 | Does a single changed target expose the intended fault? |
| `pair_done` | ISSUE-1/2 done | 2 | Are partial progress and target order represented correctly? |
| `mixed_status` | ISSUE-1 done, ISSUE-2 in_progress | 2 | Is the mixed goal preserved rather than flattened? |
| `reopen` | ISSUE-2 open | 1 | Are reopening and unrelated seeded statuses checked? |
| `already_satisfied` | ISSUE-1 done | 0 | Is success without a write excluded from recovery evidence? |
| `partial_satisfied` | ISSUE-1/2 done | 1 | Are the satisfied target's value and version preserved? |

For each fault profile, record whether injection occurs before or after commit, whether
the visible acknowledgement can disagree with persisted state, how write attempts are
indexed, and when a scheduled fault remains unused. A shared scenario label does not
guarantee equal realized exposure when policies choose different actions.

Review all-target success, unrelated row/status/version checks, missed schedules, no-op
writes and partial progress separately. Check that expected failures remain distinguishable
from expectation mismatches. Agreement between two components sharing assumptions does
not by itself establish oracle accuracy. Inspect raw states, events and traces as well.

External review should record reviewer identity, date, exact snapshot, per-item findings,
unresolved disagreements and a disposition for each issue. Do not mark this packet
approved on the basis of the implementing assistant's local review. No reviewer has been
contacted and no external sign-off is recorded here.

## Priority 2: specify a comparison before collecting new live outcomes

The three production modes remain unchanged. A separate mock-only reflection prototype
now exercises observation-only corrective phases; a live/metered reflection arm is still
missing. Review its observations, stopping rule and tool access before any model comparison.
Specify ablations that distinguish verification/recovery policy from simply granting
more actions, decisions, tokens or elapsed time. Static and dynamic engines verify at
different times; analyze them separately unless the design explicitly controls that.

Before a live study, record:

- The primary outcome and denominator, selected tasks and fault schedules, model/configuration,
  trial count, ordering, per-run budgets and exclusion rules.
- How failures, provider errors, interruptions, unknown usage and unused injections enter
  the analysis. Preserve failed runs and partial evidence.
- Whether task/scenario/mode comparisons are paired, how shared conditions affect
  dependence, and which uncertainty calculation the design supports.
- A budget-controlled comparator plan, stopping rule, cost-accounting scope and handling
  of observed token/cost overshoot. Existing infrastructure has no global dollar cap.
- The claim boundary: fixed local execution mechanisms versus general language quality,
  prompt-injection resistance or autonomous browser reliability.

The benchmark currently measures execution of fixed requirements, not interpretation.
Conditional recovery metrics select realized fault-exposed subsets and are not causal
effects. Repeated deterministic mock runs do not add stochastic reliability evidence.
Nominal Wilson intervals do not establish independence or replace a paired study design.
See [the benchmark protocol](BENCHMARK.md) for the implemented metric definitions.

## Reviewer checklist and disposition

| Review item | Evidence to inspect | Current disposition |
| --- | --- | --- |
| Original goals, fault timing and no-op exposure | Corpus, fault adapter and per-run realized attempts | Awaiting external review |
| Oracle scope and collateral outcomes | Final SQL states versus original targets and untargeted versions | Locally reconciled; external review pending |
| Quota denials and unknown work | 72-run package, reservations and admission replay | Locally reconciled; external review pending |
| Reflection phases and stopping rules | 96-run package, native reports and five achieved-goal budget failures | Locally reconciled; external review pending |
| Counter/resource comparability | Per-condition vectors and separate trusted/ordinary reads | Shared caps only; equal-resource claims unsupported |
| Artifact portability and provenance | Archive hashes, external manifest bindings and relocated audits | Local consistency passed; unsigned provenance |
| Generalization and live model behavior | No prospective metered LLM comparison exists | Unsupported; future specification required |

For any external disposition, record reviewer/date, exact plan/archive/checker hashes,
per-item evidence, disagreements and follow-up decisions. All rows above remain unsigned
implementer summaries. No reviewer has been assigned or contacted.

## Next concrete work

The [prospective decision-budget sensitivity study](DECISION_BUDGET_COMPARISON.md) now
specifies 288 fresh conditions at caps 4/8/12. Its [runner](DECISION_BUDGET_RUNNER.md)
and pretrial binding are implemented; [recorded results](DECISION_BUDGET_RESULTS.md)
now retain the completed study and separate operational interruption. At twelve versus
eight decisions, goals were unchanged and four achieved-goal reflection stops retained
exhausted action counters. Next, specify an action-cap follow-up before new execution,
keeping decision and information policies explicit. Predeclare its grid, denominator,
ordering and treatment of achieved-goal stops. Neither sensitivity check equalizes oracle
information or establishes dollar-cost parity. The [comparator design](COMPARATOR_DESIGN.md)
retains the broader ablation requirements.

External review, metered LLM reflection, stochastic sample-size/analysis design and any
paid execution remain separate pending work. This updated packet authorizes none of them.
