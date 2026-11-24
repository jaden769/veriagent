# Portable raw bounded-oracle evidence

The [evidence ZIP](evidence/bounded-oracle-2026-11-24.zip) contains the complete raw
72-condition experiment: 436 bound files, including state/trace SQLite databases,
JSON traces, agent reports, admission replays, per-run results, the original manifest,
plan, corpus and generating runner source. The
[package record](review/bounded-oracle-package.json) records ZIP size/hash and validation.
It is 424,810 bytes. The [outcome report](BOUNDED_ORACLE_RESULTS.md) remains descriptive.

## Recheck from a fresh checkout

Use the installed editable environment from the repository root:

```powershell
.\.venv\Scripts\python.exe -m research.bounded_oracle_evidence audit docs/evidence/bounded-oracle-2026-11-24.zip --manifest-sha256 97ddc8da800f8e8d7c778a05f94af0ff375151eecfb13a4a38728253d3b8e758
```

Supply the expected manifest hash from the committed result/package record through a
separate trusted reference; a hash copied only from an unknown ZIP does not authenticate
it. The ZIP checksum is in the package record. These references are unsigned and do not
establish authorship or provenance authentication.

The checker extracts into private temporary staging, validates using relative paths and
removes staging afterward. Absolute paths in the historical manifest remain display
metadata and are never followed. The repository ZIP was rechecked with access to the
original file and SQLite evidence paths blocked. No agent, provider, browser or embedded
runner source is executed. Compatible installed validation code is required; the ZIP is
raw evidence plus generating-source provenance, not an entire dependency environment.

## What is checked

The external manifest binding anchors the plan/runner hashes and per-trial file hashes.
The bound corpus supplies the original fixed tasks and initial statuses, independent of
the current checkout's corpus file. The checker verifies bounded, unique Cartesian
condition coverage, unique run/trial identities, exact file bindings and no unbound files.

It cross-checks result/report equality, SQLite traces against JSON exports, task and
quota/budget configuration against the plan, fresh admission replay against saved/live
ledger state, final SQLite rows and independent target/collateral outcomes. Outcome,
denial and expectation-mismatch labels must agree with the evidence and manifest flags.
Fault metadata bytes are bound by the original manifest; this checker does not independently
re-enact hidden fault injection or execute the generating source.

`consistency_passed` describes package consistency. `experiment_evidence_passed` and
`expectations_passed` retain the experiment's separately recomputed flags. A fully recorded
unexpected outcome can be consistent evidence, so those meanings must not be conflated.
The recorded package passed all three checks with 72 runs and 28 denials.

Archive members reuse the existing bounded path/type/size preflight: at most 4,096 files,
16 MiB per file, 256 MiB expanded and 128 MiB compressed. Traversal, duplicate or
normalized names, links and unsupported member types are rejected. Plan dimensions are
bounded before Cartesian expansion; SQLite queries use read-only connections and a
progress-handler instruction budget. These are resource guards, not exact real-time limits.

## Create a new package

```powershell
.\.venv\Scripts\python.exe -m research.bounded_oracle_evidence pack SOURCE_TREE new-evidence.zip
```

Defaults use the committed bounded-oracle results reference, plan, corpus and runner.
For a different reviewed run, supply explicit `--reference`, `--plan`, `--corpus` and
`--runner` paths. Every provided byte binding must match the original manifest. Use a
new ZIP path outside the source and an existing writable output parent. Publication uses
a same-filesystem hard link after auditing the staged ZIP, and never replaces an output.
The source is not rewritten. This repository-local utility adds no product CLI command.

The ZIP contains only fixed mock data, but it preserves original path and timing metadata.
Raw evidence can be inspected and transferred without rerunning the experiment. It does
not establish general reliability, fault-exposure parity, cost parity or external approval.
