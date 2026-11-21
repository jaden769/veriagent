# Recorded offline comparison outcomes

Recorded 2026-11-21 from the [prospective specification](OFFLINE_COMPARISON.md).
Both completed batches used the mock provider: 72 static runs and 72 dynamic runs,
one observation per task/scenario/mode condition. The
[machine-readable record](review/offline-comparison-results.json) binds the plan hash,
manifest hashes, per-condition run evidence and original summaries. Raw SQLite/trace
artifacts remain local at the recorded paths; this document does not publish a complete
portable raw-evidence bundle or authenticate its provenance.

## Execution deviation and retained partial attempt

The first static attempt in the planned OneDrive output directory stopped with WinError 5
when replacing `benchmark.tmp` with `benchmark.json`. It exited 2. The committed manifest
records 38 completed rows; the temporary manifest and saved per-run result files contain
39. Both manifest hashes and the directory are retained in the result record. No
interrupted-attempt outcomes are silently pooled into the completed batches.

Both engines were then run as fresh batches under the writable local visualization
artifact root. Only the output path was changed; source fingerprints, tasks, scenarios,
modes, repetition, provider and budgets remained as specified. Each fresh batch completed
72 rows. This is a disclosed restart after a filesystem failure, not a resumed batch.
The prospective plan is retained unchanged; the output-path amendment is in the result
record.

## Evidence checks

For each completed batch, checks confirmed completeness, exact coverage of all selected
conditions, pinned corpus/provider/budget, unique run IDs across all 144 completed rows,
per-run JSON equality with the manifest, trace-file presence and recomputed summary
equality. Read-only queries of all final SQLite files matched saved final rows. Target
status success, untargeted status/version changes and false-success labels were recomputed
from initial/final rows. No untargeted status/version changes were observed. Token totals
were zero for the mock provider; this says nothing about live API cost.

## Descriptive outcomes by condition

Each cell lists **baseline / verify / recover** in that order. `S` means requested final
target statuses were satisfied; `C` means an unsatisfied target with an agent success
claim; `F` means an unsatisfied target without a success claim. These symbols do not
replace the detailed exposure, retry, collateral and resource fields in the JSON record.
No engine, task or scenario pooling or stochastic inference is used here.

| Engine | Task | Scenario | Baseline / verify / recover |
| --- | --- | --- | --- |
| static | single_done | clean | S / S / S |
| static | single_done | silent_drop | C / F / S |
| static | single_done | persistent_drop | C / F / F |
| static | single_done | transient | F / F / S |
| static | pair_done | clean | S / S / S |
| static | pair_done | silent_drop | C / F / S |
| static | pair_done | persistent_drop | C / F / F |
| static | pair_done | transient | F / F / S |
| static | mixed_status | clean | S / S / S |
| static | mixed_status | silent_drop | C / F / S |
| static | mixed_status | persistent_drop | C / F / F |
| static | mixed_status | transient | F / F / S |
| static | reopen | clean | S / S / S |
| static | reopen | silent_drop | C / F / S |
| static | reopen | persistent_drop | C / F / F |
| static | reopen | transient | F / F / S |
| static | already_satisfied | clean | S / S / S |
| static | already_satisfied | silent_drop | S / S / S |
| static | already_satisfied | persistent_drop | S / S / S |
| static | already_satisfied | transient | S / S / S |
| static | partial_satisfied | clean | S / S / S |
| static | partial_satisfied | silent_drop | S / S / S |
| static | partial_satisfied | persistent_drop | C / F / F |
| static | partial_satisfied | transient | S / S / S |
| dynamic | single_done | clean | S / S / S |
| dynamic | single_done | silent_drop | C / F / S |
| dynamic | single_done | persistent_drop | C / F / F |
| dynamic | single_done | transient | F / F / S |
| dynamic | pair_done | clean | S / S / S |
| dynamic | pair_done | silent_drop | C / F / S |
| dynamic | pair_done | persistent_drop | C / F / F |
| dynamic | pair_done | transient | F / F / S |
| dynamic | mixed_status | clean | S / S / S |
| dynamic | mixed_status | silent_drop | C / F / S |
| dynamic | mixed_status | persistent_drop | C / F / F |
| dynamic | mixed_status | transient | F / F / S |
| dynamic | reopen | clean | S / S / S |
| dynamic | reopen | silent_drop | C / F / S |
| dynamic | reopen | persistent_drop | C / F / F |
| dynamic | reopen | transient | F / F / S |
| dynamic | already_satisfied | clean | S / S / S |
| dynamic | already_satisfied | silent_drop | S / S / S |
| dynamic | already_satisfied | persistent_drop | S / S / S |
| dynamic | already_satisfied | transient | S / S / S |
| dynamic | partial_satisfied | clean | S / S / S |
| dynamic | partial_satisfied | silent_drop | C / F / S |
| dynamic | partial_satisfied | persistent_drop | C / F / F |
| dynamic | partial_satisfied | transient | F / F / S |

## Interpretation boundaries

Clean conditions satisfied their targets in both engines. Persistent dropped writes
left unmet targets except when the goals were already satisfied. Verification detected
false claims in the selected dropped-write conditions; recover mode repaired the
one-shot faults when those faults affected unmet writes. These are finite observations
under the recorded caps, not estimates of general recovery or model reliability.

For `partial_satisfied`, static silent-drop/transient runs all succeeded without recovery:
the first write attempted an already-satisfied target, consuming the fault without an
unmet required write. Their `fault_recovery_eligible` fields are false. Dynamic execution
skipped the satisfied target; its first write exposed the unfinished target to the fault.
Dynamic baseline/verify then failed, while recover succeeded with one recovery attempt.
Its eligibility fields are true. Comparing the raw scenario labels alone would hide this
exposure difference. Already-satisfied success likewise does not establish recovery.

The JSON preserves implementation-generated nominal Wilson intervals, but one deterministic
observation per condition supplies no stochastic confidence claim. Latency includes local
instrumentation and was not randomized or causally analyzed. Self-reflection and
budget-controlled ablations are still absent. External corpus/fault review, a live-study
design and repeated live-model evidence remain pending.
