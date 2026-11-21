# Offline evidence operator guide

Use this workflow for completed browser evaluations. All commands below run without
browser trials or API calls. Run them from the repository root with the installed
virtual environment. For generation and browser setup, see [the browser guide](BROWSER.md).

## Choose the check

| Input and purpose | Command | What success establishes |
| --- | --- | --- |
| Installed matrix definitions | `inspect-browser-matrices` | Current catalog metadata; no saved evidence checked |
| A saved trial | `audit-browser` | Trial evidence consistency; inspect `task_passed` separately |
| A saved batch | `audit-browser-batch` | Bound trials, coverage and summary consistency |
| A completed evaluation | `review-browser-controls` | Audited evidence and compact outcome details |
| Up to six distinct matrices | `review-browser-suite` | Audited evidence plus requested selection policy |
| Exported suite JSON | `validate-browser-suite` | Structure and internal report consistency only |
| A ZIP before restoration | `inspect-browser-archive` | Directory metadata and declared resource limits only |
| A completed evaluation to transfer | `archive-browser-controls` | Exact archived bytes passed staged evidence audit |
| A ZIP to restore | `restore-browser-controls` | Restored bytes passed evidence audit before publication |

These are unsigned consistency checks. They do not authenticate provenance or establish
stochastic reliability. Contract matching compares saved identity against installed
definitions; it does not establish authorship.

## Review and export

Replace the example evaluation path with the directory containing `controls.json`.

```powershell
$evaluation = "C:\path\to\evaluation"
.\.venv\Scripts\veriagent.exe inspect-browser-matrices
.\.venv\Scripts\veriagent.exe review-browser-controls $evaluation --require-contract
.\.venv\Scripts\veriagent.exe review-browser-suite $evaluation --require-contract --format json | Out-File -Encoding utf8 suite-review.json
# Check $LASTEXITCODE immediately after the command above.
.\.venv\Scripts\veriagent.exe validate-browser-suite suite-review.json
```

Suite JSON uses schema version 2. The validator accepts UTF-8 with an optional BOM and
rejects files over 4 MiB. Its success checks the report itself and never reopens referenced
evaluations. A report recording rejected evidence can therefore validate successfully.

Add more evaluation paths to `review-browser-suite` to combine different matrix types.
Add `--require-all` only when all six types are intended. A partial selection is accepted
by default and explicitly lists missing matrices. Duplicate matrices or reused run evidence
are rejected; each evaluation must provide its own bound trials.

Read the report fields together:

- `evidence_passed` records evidence consistency, including the requested contract policy.
- `selection_passed` records suite selection requirements, including `--require-all`.
- `controls_passed` records whether observed outcomes matched declared expectations.
- `counts.successful_tasks` counts successful tasks; expected task failures are separate.
- `contract_coverage` counts matched, legacy or unverifiable **evaluation inputs**.
- `present_matrices` and `missing_matrices` describe distinct admitted matrix types.

When evidence or selection is rejected, suite aggregate counts and `controls_passed`
are null. Identity metadata remains diagnostic. Expected task failures can coexist with
`controls_passed: true` because the controls deliberately exercise failure boundaries.

## Transfer and restore

Choose new output names in existing parent directories. Keep the ZIP outside the source
evaluation tree. Do not concurrently modify the source or destination during transfer.

```powershell
.\.venv\Scripts\veriagent.exe archive-browser-controls $evaluation transfer.zip --require-contract
.\.venv\Scripts\veriagent.exe inspect-browser-archive transfer.zip
.\.venv\Scripts\veriagent.exe restore-browser-controls transfer.zip restored-evaluation --require-contract
.\.venv\Scripts\veriagent.exe review-browser-suite restored-evaluation --require-contract
```

Check `$LASTEXITCODE` after each command and continue only when its meaning is acceptable.
Existing outputs are rejected. Source bytes and relative bindings are preserved;
absolute paths stored as display metadata may still name the original location.
Creation and restoration audit staged bytes before publication. Archive publication
requires filesystem hard-link support. All source-tree files, including local SQLite
files, are included; inspect the tree before sharing it.

Inspection reads ZIP directory metadata without opening payloads. It does not check
payload CRCs, contracts or outcomes. Restoration independently checks payloads and runs
the nested evidence auditors. Transfer limits are 4,096 files, 16 MiB per file, 256 MiB
expanded and 128 MiB compressed. See [archive details](BROWSER.md#transfer-a-completed-evaluation-as-a-zip-archive)
for supported paths, compression and failure handling.

`--require-contract` rejects legacy schema-1 evaluations without a matched identity.
Omit it to use default legacy compatibility; accepted artifacts remain labeled
`legacy_missing` and are never upgraded. Missing required modern headers and explicit
contract mismatches fail under both policies.

## Interpret exit status

| Command family | Exit 0 | Exit 1 | Exit 2 |
| --- | --- | --- | --- |
| Trial/batch/control audits and control review | Evidence accepted; outcomes may fail | Evidence rejected | Argument error |
| Suite review | Evidence and selection accepted; controls may fail | Evidence or selection rejected | Argument/selection input error |
| Exported suite validation | Report internally consistent, even if it records rejection | Read, parse or report validation failed | Argument error |
| Matrix inspection | Metadata displayed | Not used | Argument/selection error |
| Archive inspection/creation/restoration | Metadata check or staged audit accepted, as scoped above | Not used | Handled input, audit, limit, filesystem or argument failure |

An exit code alone does not establish task success. Inspect the outcome fields and retain
the original evidence. If a check fails, use full `audit-browser-controls` output for
per-check diagnostics before considering any regeneration; do not edit bound files to
make the audit pass.

## Workflow regression

The Chromium-enabled `test_documented_operator_workflow_through_cli` test runs this
sequence through separate CLI processes against a complete, relocated 16-control
mock-provider evaluation. It checks BOM-compatible exported JSON, byte-preserving ZIP
transfer, unchanged review totals and the difference between a rejected partial selection
(exit 1 from suite review) and a consistent export of that rejection (exit 0 from report
validation). See [validation records](VALIDATION.md) for the recorded run.
