# Portable common-corpus evidence

The [evidence ZIP](evidence/reflection-comparison-2026-11-26.zip) contains all 96 runs
from the [recorded comparison](REFLECTION_COMPARISON_RESULTS.md), with 583 files:
six files per trial, the original manifest/plan/execution lock, the pinned corpus and
three bound source snapshots. Source snapshots are evidence bytes and are never executed.

Archive SHA-256:
`34445c56c209d320141a0ce3d085d3ea411a6459e1980368cb6e5eb8d7e1620a`

Archive size: 634,689 bytes. The [package record](review/reflection-comparison-package.json)
also records the checker source hash. The external manifest binding from the committed
[results record](review/reflection-comparison-results.json) is:
`b15d202a3f160e4f9968b287c7a6f4ce46fdcc1834d3c885ab5fb91fb770660c`.
Use that reviewed binding rather than trusting a hash supplied by an unknown archive.

From the repository root, audit without restoring into a working evidence directory:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from research.reflection_evidence import audit_archive; print(audit_archive(Path('docs/evidence/reflection-comparison-2026-11-26.zip'), 'b15d202a3f160e4f9968b287c7a6f4ce46fdcc1834d3c885ab5fb91fb770660c'))"
```

The checker uses bounded temporary extraction and the existing portable ZIP path/name,
link, duplicate and size checks. Tree inventory rejects links, escaping paths, excessive
files/bytes and unbound members. JSON loading rejects duplicate keys; canonical comparisons
distinguish boolean and numeric labels. SQLite reads use read-only connections with a
progress limit. These bounds do not promise exact wall-clock execution time.

It checks the original manifest binding, bundled plan/corpus/lock/source hashes, exact
assigned order and unique identities. Per-trial checks reconcile native reports,
SQLite/JSON traces, budgets, dynamic admission/live-ledger counters or reflection phase
evidence, resource vectors, independent final SQL states, claims and collateral changes.
No original absolute artifact path, repository plan or current source inventory is opened
to resolve evidence. The checker still requires compatible installed auditing code.

The relocated archive passes with original artifact and repository metadata reads blocked.
It preserves all 96 outcomes, including ten baseline false success claims; evidence
consistency does not require task success. Packaging audits a staged archive before
publishing a new output and refuses overwrite or publication inside the raw tree.

This is unsigned consistency evidence, not authenticity or independent reenactment of
fault delivery. Fault eligibility is recomputed from bound records. The original plan,
lock, runner, raw directory and measured results are unchanged. No additional comparison,
live model call or browser trial was needed for this packaging step.
