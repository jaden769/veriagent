# Research validation review packet

Prepared 2026-11-21 by the implementing assistant. External review remains pending.
This packet records local implementation facts and review priorities, not experimental
findings or independent approval. The [snapshot](review/offline-baseline.json) pins the
corpus, implemented modes, matrix identities and selected source-file hashes.

## Current evidence and open gaps

| Area | Available evidence | Remaining requirement before broader claims |
| --- | --- | --- |
| Execution mechanisms | Deterministic mock tasks, faults and independent final-state checks | Independent corpus/fault review and broader task coverage |
| Browser controls | Six fixed matrices, 130 declared controls, sealed nested artifacts | External review of expectations; controls are finite mechanism checks |
| Live integration | Individual user-run static, dynamic and reviewed checks | Repeated, prospectively specified model comparisons |
| Comparators | Baseline, verify and recover modes | Self-reflection comparator and budget-controlled ablations |
| Metrics | Explicit denominators and descriptive Wilson intervals in sandbox benchmark | Study-specific estimand, analysis plan and dependence assumptions |
| Transfer/review | Audits, report validation, archive round-trips and CLI smoke coverage | These establish workflow consistency, not model reliability |

The latest complete-suite record is 670 passing tests, followed by focused increments;
see [validation history](VALIDATION.md). Test counts are software-validation evidence.
They are not independent task samples or a reliability denominator.

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

Review all-target success, unrelated row/title/version checks, missed schedules, no-op
writes and partial progress separately. Check that expected failures remain distinguishable
from expectation mismatches. Agreement between two components sharing assumptions does
not by itself establish oracle accuracy. Inspect raw states, events and traces as well.

External review should record reviewer identity, date, exact snapshot, per-item findings,
unresolved disagreements and a disposition for each issue. Do not mark this packet
approved on the basis of the implementing assistant's local review. No reviewer has been
contacted and no external sign-off is recorded here.

## Priority 2: specify a comparison before collecting new live outcomes

The current three modes do not implement the roadmap's self-reflection comparator.
Define its observations, stopping rule and permitted tool access before adding it.
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

## Next concrete work

Prepare a prospective **offline-only comparison specification** from this pinned corpus:
identify selected task/fault groups, existing comparator budgets, planned primary metrics
and missing comparator behavior. Keep live execution and external approval pending.
No API calls or new benchmark results are authorized or implied by this review packet.
