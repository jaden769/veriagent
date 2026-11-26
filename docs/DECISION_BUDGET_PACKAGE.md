# Portable decision-budget attempt evidence

Both attempts from the [decision-budget results](DECISION_BUDGET_RESULTS.md) are included
as separate archives. Their identities, denominators and coverage claims are never pooled.
The [package record](review/decision-budget-package.json) pins both ZIP hashes and the
portable checker's source hash.

| Archive | Completed rows / assigned | Files | Bytes | Coverage |
| --- | ---: | ---: | ---: | --- |
| [Completed attempt](evidence/decision-budget-complete-2026-11-26.zip) | 288 / 288 | 1,741 | 1,954,522 | Complete study |
| [Interrupted attempt](evidence/decision-budget-partial-2026-11-26.zip) | 206 / 288 | 1,249 | 1,443,101 | Partial prefix; active outcome unknown |

Completed archive SHA-256:
`d55e1a2d27a8b2ac3ebceb98929312a44d1caba2fb8a9a55d3c8237451bec9e8`

Partial archive SHA-256:
`ae3dbe20ee0c73d219177ad61a648461d88a179a85f729377c9eef1755a6f24a`

Each ZIP contains the original manifest, plan, execution lock, completed per-trial evidence,
pinned corpus, bound prior-result reference and all eight frozen research execution source
snapshots. Embedded sources are evidence bytes and are never executed. The partial archive
has no directory for the next active assignment: interruption occurred before that trial
was constructed. Its 206 completed rows remain a prefix, not a substitute for missing rows.

## Audit from the archives

Use the external manifest bindings from the committed
[result record](review/decision-budget-results.json), not hashes supplied by an unknown ZIP:

- Complete: `69c8aadd644bf5a6b79aec7d44dde6317f79c40abbd468a63fce2751f16a7d9f`
- Partial: `b9969491867c05b606ec14acafa7c3629289918dcfa3359dfc01ca221a1c9a8f`

From the repository root:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from analysis.decision_budget_evidence import audit_archive; print(audit_archive(Path('docs/evidence/decision-budget-complete-2026-11-26.zip'), '69c8aadd644bf5a6b79aec7d44dde6317f79c40abbd468a63fce2751f16a7d9f'))"
.\.venv\Scripts\python.exe -c "from pathlib import Path; from analysis.decision_budget_evidence import audit_archive; print(audit_archive(Path('docs/evidence/decision-budget-partial-2026-11-26.zip'), 'b9969491867c05b606ec14acafa7c3629289918dcfa3359dfc01ca221a1c9a8f'))"
```

The complete archive returns `consistency_passed: true`, `study_complete: true` and 288
completed runs. The partial archive returns `consistency_passed: true`,
`study_complete: false`, 206 completed runs and `active_outcome: unknown`. Consistency
means the retained evidence agrees; it does not assert complete coverage or task success.
The complete archive retains 26 false claims across the three caps. The partial archive's
20 false claims describe only its own prefix and are not added to the study totals.

## Boundaries and checks

The checker uses bounded temporary extraction and existing portable ZIP path, duplicate,
link, compression and size checks. Tree inventory rejects links, escaping paths, excessive
files/bytes and unbound members. JSON loading rejects duplicate keys; comparisons preserve
boolean versus numeric distinctions. SQLite reads are read-only with a progress limit;
these limits do not guarantee exact wall-clock time.

It checks manifest/plan/lock/source/corpus/prior-reference bindings, exact complete or
partial-prefix assignment order, unique identities, native reports, SQLite/JSON traces,
admission or reflection replay, resource vectors, stopping diagnostics and independent
final SQL states. A partial manifest must identify the next assignment, unknown outcome
and stop reason. Changing it to a complete flag cannot pass with a short prefix.

Auditing follows only relative bundled evidence. Neither original absolute artifact path
nor repository plan/source inventory is used to resolve inputs. Compatible installed audit
code is still required. Tests block original artifact/repository metadata reads, corrupt
coverage, claims and counters, and verify that wrong-attempt publication, unsafe archives
and overwrites are rejected. Packaging audits the staged ZIP before publishing a new file.

The checker is outside the frozen execution inventory. Original raw directories, source
pins, plans, locks, measured results and prior archives remain unchanged. No study rerun,
browser trial or paid call was used to package these files. The archives are unsigned:
hashes establish bound consistency rather than authenticity, and fault delivery is not
independently reenacted. Partial results remain separate from all completed-study findings.
