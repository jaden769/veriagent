# Portable action-budget evidence

The [evidence ZIP](evidence/action-budget-2026-11-26.zip) contains all 288 runs from the
[recorded fixed-fault study](ACTION_BUDGET_RESULTS.md): 1,742 files and 2,035,138 bytes.
The [package record](review/action-budget-package.json) includes the checker source hash.

Archive SHA-256:
`e6b7f4ac0207d4c1850027224cabf168ce3b1fd23d20f3cbbe46994554874c5f`

The ZIP contains six files per trial, original manifest/plan/lock, the pinned corpus and
prior-result reference, plus nine frozen execution source snapshots under their original
research/analysis namespaces. Embedded sources are evidence bytes and are never executed.
Original raw evidence, plans, locks, measured result records and prior archives are unchanged.

## Audit from the archive

Use the external manifest binding from the committed
[results record](review/action-budget-results.json):
`94a1e78000d637910db03370ba9f3bf5cb21a67600eb0b3472e15abd36e5ec45`.
Do not replace it with a hash supplied by an unknown archive.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from analysis.action_budget_evidence import audit_archive; print(audit_archive(Path('docs/evidence/action-budget-2026-11-26.zip'), '94a1e78000d637910db03370ba9f3bf5cb21a67600eb0b3472e15abd36e5ec45'))"
```

The result reports consistency passed, study complete, 288 completed runs and 1,742 files.
All 30 baseline false claims across the three action caps remain in the evidence; none
are removed to make the audit pass. Evidence consistency is separate from task success.

The checker uses bounded temporary extraction and the existing portable ZIP path/name,
duplicate, link, compression and size checks. Tree inventory rejects linked/escaping
paths, excessive files/bytes and unbound members. Duplicate JSON keys are rejected and
canonical comparisons distinguish boolean and numeric labels. Read-only SQLite queries
have a progress limit; these bounds do not promise exact wall-clock completion.

It verifies external manifest and bundled plan/lock/source/corpus/prior-reference hashes,
exact assignment order, unique identities, native reports and SQLite/JSON traces. It
reconciles dynamic admission or reflection phases, resource vectors, fixed configured
faults, assigned budgets, stop diagnostics and independent final SQL states. The fixed
factory ceiling must yield thirteen persistent drops at every action cap.

Audit inputs resolve from relative bundled evidence. The original artifact directory,
repository plans and current source inventories are not opened to resolve inputs;
compatible installed auditing code is still required. Relocation tests block original
artifact/repository metadata reads. Corruption tests cover coverage, fault metadata,
resources, stop flags, outcomes, sources and prior reference, plus unsafe ZIPs and overwrite
rejection. Packaging audits a staged ZIP before publishing a new output.

The historical eight-action reference used nine persistent drops. The bound study plan
and result record disclose this difference; unchanged outcome/resource findings are a
descriptive anchor check. Bundling the prior reference does not pool it into this study.

No study rerun, browser trial or paid call was used for packaging. These are unsigned
consistency checks, not authenticated provenance or independent reenactment of fault
delivery. They establish no stochastic confidence, causal effect, equal-information/
dollar parity or LLM-quality conclusion. External review remains pending.
