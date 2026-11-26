# Pinned mock reflection comparison runner

`research/run_reflection_comparison.py` implements the ordered 96 conditions in the
[published common-corpus plan](REFLECTION_COMPARISON.md). It runs only MockProvider and
MockReflectionProvider. No live provider option or product CLI mode was added.

The [execution lock](review/reflection-execution-lock.json) binds the exact plan bytes,
runner, reflection auditor and shared research support module. Before creating outputs
or providers, execution validates these bindings, the original product source inventory,
corpus hash and all ordered conditions. The runner also pins the original published
plan hash; editing that plan is rejected. Deliberate future changes need explicit review
and a new binding, rather than silently refreshing historical fingerprints.

Explicit execution from the repository root is:

```powershell
.\.venv\Scripts\python.exe -m research.run_reflection_comparison --output artifacts/reflection-comparison
```

The frozen study has now been executed; see the separate
[96-condition results](REFLECTION_COMPARISON_RESULTS.md). Unit-test fixtures and simulated
orchestration remain separate from those comparative results.

Each assigned condition receives a fresh state database, trace store, provider, executor
and agent. Dynamic arms receive a fresh unlimited verification ledger. Reflection receives
no verifier or ledger. Native report families remain distinct. The runner saves reports,
JSON/SQLite traces and the relevant offline replay before a separate final SQL audit.
Final target truth, false claims and untargeted changes remain separate findings.

Resources retain ordinary reads/writes, actions, decisions, trusted verification calls,
known logical target rows, policy admissions and model calls/tokens as separate quantities.
Fault records retain pre-fault status, realized attempts, unused counters and recovery
eligibility. These quantities do not establish equal cost or equal information.

A new UUID directory contains a manifest plus per-condition evidence and checksums.
The manifest records the active condition before execution. Interruption retains completed
rows and partial files, marks the active outcome unknown and re-raises the error. There is
no automatic retry, replacement or resume. Task failure and false claims do not stop the
study; a harness/audit exception does. Complete evidence requires all 96 assigned rows,
unique run IDs and successful trace reconciliation; it does not require every task to
succeed. Artifact hashes and the lock are unsigned consistency evidence, not provenance.

Next: explicitly execute the frozen plan, independently inspect assigned coverage and
record condition-level findings without changing the prospective specification.
