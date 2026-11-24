# Recorded bounded-oracle mechanism outcomes

Recorded 2026-11-24 from the [prospective plan](BOUNDED_ORACLE_COMPARISON.md).
The [machine-readable results](review/bounded-oracle-results.json) retain every assigned
condition, actual outcome, live quota state, report, realized faults and file hashes.
All 72 dynamic mock conditions completed, admission evidence reconciled and all pinned
expectations matched. This is one deterministic observation per condition, not a live
study, a stochastic reliability estimate or a cost-parity ablation.

## Runner and validation

Run from the repository root using the editable environment:

```powershell
.\.venv\Scripts\python.exe -m research.run_bounded_oracle --output PATH_TO_EXISTING_LOCAL_ARTIFACT_ROOT
```

The repository-local runner validates the pinned source/corpus, exact 72 conditions,
quota profiles, budgets and expected fields before creating output or constructing a
provider. It always uses MockProvider; it exposes no provider-selection option and adds
no product CLI command. Each condition gets fresh state, provider, adapter, ledger and
TraceStore. Results and active conditions are saved after each transition; interruption
retains partial evidence and does not resume or silently retry. Expectation mismatches
are recorded without discarding the row. Harness/reconciliation exceptions stop the run
and preserve the incomplete manifest and active trial.

A single new UUID tree was created under the approved non-OneDrive local artifact root.
Raw state/trace databases, JSON traces, reports, admission replays and per-run results
remain at the directory recorded in the results JSON. They are unsigned and not bundled
in this committed record. A complete portable raw-evidence release is still separate work.

Post-run checks independently verified exact coverage and 72 unique run IDs, every bound
file hash, result/manifest and report equality, SQLite trace rows versus exported JSON,
fresh admission replay versus saved replay/live state, final SQLite rows versus saved
snapshots, target-status outcomes and untargeted status/version preservation. No untargeted
changes or verification errors were observed. The plan and runner hashes are recorded.

## Outcomes by assigned condition

Each triplet is **baseline / verify / recover**. `S` denotes satisfied final targets with
a success claim; `C` denotes a success claim with unmet targets; `F` denotes an unmet
failure without a success claim. `D-initial` and `D-post` are honest budget denials before
any tool write or after a write, respectively, with no claim and no final verification.
The last column independently reports final target satisfaction in the same mode order.

| Task | Scenario | Quota profile | Agent outcomes | Final targets satisfied |
| --- | --- | --- | --- | --- |
| single_done | clean | zero_calls | S / D-initial / D-initial | yes / no / no |
| single_done | clean | one_call | S / D-post / D-post | yes / yes / yes |
| single_done | clean | one_row | S / D-post / D-post | yes / yes / yes |
| single_done | clean | unlimited | S / S / S | yes / yes / yes |
| single_done | silent_drop | zero_calls | C / D-initial / D-initial | no / no / no |
| single_done | silent_drop | one_call | C / D-post / D-post | no / no / no |
| single_done | silent_drop | one_row | C / D-post / D-post | no / no / no |
| single_done | silent_drop | unlimited | C / F / S | no / no / yes |
| already_satisfied | clean | zero_calls | S / D-initial / D-initial | yes / yes / yes |
| already_satisfied | clean | one_call | S / S / S | yes / yes / yes |
| already_satisfied | clean | one_row | S / S / S | yes / yes / yes |
| already_satisfied | clean | unlimited | S / S / S | yes / yes / yes |
| already_satisfied | silent_drop | zero_calls | S / D-initial / D-initial | yes / yes / yes |
| already_satisfied | silent_drop | one_call | S / S / S | yes / yes / yes |
| already_satisfied | silent_drop | one_row | S / S / S | yes / yes / yes |
| already_satisfied | silent_drop | unlimited | S / S / S | yes / yes / yes |
| partial_satisfied | clean | zero_calls | S / D-initial / D-initial | yes / no / no |
| partial_satisfied | clean | one_call | S / D-post / D-post | yes / yes / yes |
| partial_satisfied | clean | one_row | S / D-initial / D-initial | yes / no / no |
| partial_satisfied | clean | unlimited | S / S / S | yes / yes / yes |
| partial_satisfied | silent_drop | zero_calls | C / D-initial / D-initial | no / no / no |
| partial_satisfied | silent_drop | one_call | C / D-post / D-post | no / no / no |
| partial_satisfied | silent_drop | one_row | C / D-initial / D-initial | no / no / no |
| partial_satisfied | silent_drop | unlimited | C / F / S | no / no / yes |

## Observed boundaries and interpretation

The 28 predicted denied conditions were observed: 16 initial denials and 12 post-write
denials. Ten denied runs nevertheless had satisfied final targets: four already-satisfied
initial-denial conditions and six clean post-write-denial conditions. Their reports
correctly remained budget failures without a success claim. This separates execution
verification availability from the independent final task outcome.

Baseline used no trusted verification under any profile, preserving its false-claim
controls. One-row allowance denied the two-target initial snapshot without partial access;
one-call/one-row single-target allowances admitted initial verification but denied a
later check. Already-satisfied goals used an admitted initial check under nonzero
allowances. Unlimited runs retained the earlier mechanism behavior.

Work inventory across the recorded cells was 42 completed trusted checks and 55 known
target-row reads, with no recorded verifier errors. These are resource inventories,
not pooled policy success rates or interchangeable action/cost units. The results preserve
per-cell resource and realized-fault evidence; quota labels do not guarantee equal
exposure, information or actual work.

All 148 focused runner/admission/agent/adapter/work/dynamic tests passed. Eight new runner
tests cover pre-output rejection, raw evidence retention on an unexpected prediction,
interruption preservation and separation from pinned product sources. No product agent
code changed for this runner increment. No paid API call or browser trial ran.

Self-reflection, budget-controlled policy ablations, external corpus/fault review and
prospective stochastic study design remain pending. These quota-boundary observations
must not be represented as completing those research comparisons.
