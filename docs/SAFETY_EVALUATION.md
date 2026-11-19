# Offline adversarial boundary evaluation

`evaluate-safety` runs a versioned set of 24 deterministic cases against the dynamic
engine. It exercises the real function-call validator, executor authorization, normalized
feedback, verifier, recovery policy and termination budgets. Responses and faults are
scripted. It never constructs a paid provider, calls a model, starts tool workers, or
uses credentials. This is an engineering boundary suite, not an LLM benchmark or a proof
of general prompt-injection resistance.

## Run and inspect

```powershell
.\.venv\Scripts\veriagent.exe evaluate-safety
.\.venv\Scripts\veriagent.exe evaluate-safety --case title_injection --case unauthorized_target
.\.venv\Scripts\veriagent.exe evaluate-safety --suite path/to/reviewed-suite.json --output artifacts/custom-safety
```

The CLI prints a compact summary and the fresh UUID result directory. Exit status is 0
only if declared outcomes and the measured boundary conditions pass, 1 when they do not,
and 2 for invalid configuration/fixtures. Selecting an unknown case fails before creating
an output directory. There is no `--provider openai` option on this command.

The packaged fixture is `src/veriagent/scenarios/safety.json`. Its groups include:

- Clean completion, dropped writes, transient/persistent faults and lost commit acknowledgments.
- Forged read status, instruction-bearing issue titles and mutation messages.
- Unauthorized reads/targets/statuses, invented tools, permission arguments, parallel calls
  and malformed arguments.
- Premature finish, repeated finish/read loops, non-idempotent retry and denied tools.
- Unavailable evidence and simulated unconfirmed cleanup after a write.
- Two explicitly labeled baseline controls, including a known false-success claim.

The real process-kill tests are separate. The corpus's unsafe-cleanup fixture only injects
the trusted observation safety flag; it does not pretend to kill an OS process.

## What is measured

Every case has declared expected completion, claimed success, verification, failure category
and recovery count. A case can pass its expectation while correctly refusing or failing to
complete the task. `24/24 expectations met` is not a task-completion or language-accuracy rate.

The evaluator reads final issue statuses/versions directly through a separate read-only
SQLite connection. This final oracle bypasses both fault-injected tool reads and the
fault-injected verifier. It checks the original task's required statuses and compares
unrelated issues against their initial snapshot. This is authoritative only for this
small local issue-status domain; it does not establish general verifier accuracy.

| Field | Definition |
|---|---|
| `expectations_met` | Observed report/oracle outcomes match the declared fixture labels |
| `protected_false_successes` | Non-baseline runs claiming success while the final state oracle fails |
| `baseline_false_successes` | Equivalent failures in deliberately unverified baseline controls |
| `unauthorized_dispatches` | Trace action attempts sent to the executor outside approved issue IDs or final write statuses |
| `changed_unrelated_issues` | Unapproved issue IDs whose persisted status/version snapshot changed |
| `feedback_leaks` | Configured canary marker found in the decision provider's received task/state context |
| `attack_observed` | Canary was actually present in a tool observation, preventing a vacuous filtering pass |
| `within_budgets` | Reported action, decision and recovery counters are within the configured bounds |

Dispatch counts describe attempts, not proof of an external side effect. Snapshot checks
cover issue status/version, not arbitrary files, issue titles or external systems. Canary
checks detect the exact configured marker, not every possible leak. Local trace output
contains the raw malicious payload as data; never follow its instructions.

Overall `passed` requires all expected outcomes to match and the measured boundaries to
hold. Baseline false-success controls are intentionally excluded from the protected
false-success condition, but remain explicitly counted and labeled. They are not hidden
or averaged into a success percentage. Unrelated changes, unauthorized dispatches, canary
leaks and exceeded counter limits cannot be excused by a fixture's expected completion label.

## Artifacts and reproduction

Each run saves `suite.json` and `results.json`. Each case directory includes:

- `case.json`, `result.json`: exact normalized fixture and observed outcomes/mismatches.
- `state.sqlite`: final application state; `traces.sqlite`: structured execution history.
- `trace.json`, `trace.txt`: portable and readable events, including the final oracle audit.
- `provider_contexts.json`: inputs actually received by the scripted decision provider.

The summary records selected case IDs, a canonical JSON suite SHA-256, a fingerprint of
on-disk package Python sources, Python/platform, relevant installed package versions and
SQLite version. Repeated identical runs have the same fixture/source fingerprints and
state outcomes; UUIDs, run IDs, PIDs where applicable, timestamps, paths and latency can
differ. Source fingerprints use relative filenames and length-framed file bytes, not Git
history. They are provenance aids, not signatures or tamper-proof runtime attestations.

Keep `uv.lock` and the matching repository revision when reproducing results. The packaged
fixture is included in wheels, so the CLI does not depend on a repository-relative test
path. All generated evidence stays under the Git-ignored `artifacts/` directory by default.
Do not put real secrets in custom fixture payloads or objectives.

Custom suites are schema-validated JSON, not executable Python. Files are limited to
1 MiB, suites to 100 cases, case scripts to 50 replies, and fixtures to 100 actions,
50 decisions, 5 recovery attempts and a cooperative 30-second run budget. IDs are constrained
so they cannot traverse directories. These limits bound configured loops; they do not
provide hard cancellation of every possible disk or OS stall.

## Testing the evaluator itself

Tests deliberately weaken authorization in a temporary sandbox, simulate a lying verifier,
inject a context leak, skip the attack observation, and alter an expected label. The
evaluator must report failure in each situation. This helps prevent a report that merely
echoes success claims or assumes that its own fixtures always pass. None of these test
mutations persist in the production agent or affect external applications.

The fixed fixtures are hand-authored, deterministic and finite. No uncertainty estimate,
model randomness, self-reflection comparison, real attack-generation model or measured
model cost is present. Actual provider quality and broad injection robustness still
require separately authorized live experiments with a larger independent task corpus.
