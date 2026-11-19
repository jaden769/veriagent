# Reviewed natural-language requirements

This Phase 2 increment separates **interpreting an objective** from **authorizing its
requirements** and **planning its execution**. A model's interpretation can be wrong even
when it matches a JSON schema. It therefore produces a proposal, never direct tool calls.

## Offline example

From the repository's PowerShell terminal:

```powershell
$proposalResult = .\.venv\Scripts\veriagent.exe propose "Close ISSUE-1 and start ISSUE-2" | ConvertFrom-Json
.\.venv\Scripts\veriagent.exe review $proposalResult.proposal_file
```

Read the objective and requirements printed by `review`. In this example they should be
ISSUE-1 → done and ISSUE-2 → in_progress. If they match your intent, copy the displayed
`approval_digest` and execute:

```powershell
.\.venv\Scripts\veriagent.exe execute $proposalResult.proposal_file --approve (Read-Host "Reviewed approval digest") --db artifacts/reviewed.sqlite --silent-drops 1
```

This uses only the offline provider, including the execution planner. The injected fault
causes the first write to report success without persisting. The verifier should detect
that mismatch, selectively retry ISSUE-1, and verify both final statuses. Use a fresh
`--db` for an independent trial; `execute` otherwise preserves existing sandbox state.

## Supported offline requests

- `close`, `finish`, `complete`, `resolve` → done.
- `start`, `begin` → in_progress.
- `open`, `reopen` → open.
- Existing `set/mark ISSUE-N to/as open|in_progress|done` syntax also works.
- Explicit issue lists, optional `please`, and clauses joined with `and` or semicolons.

This is a full-match grammar, not broad language understanding. Negative requests,
conditional instructions, implicit issue references, repeated targets, conflicting
statuses and unsupported trailing instructions produce clarification without partial work.
For example, `Close the login issue` needs an explicit issue ID. `Don't close ISSUE-1`
does not mean `Close ISSUE-1`. A clarification proposal cannot be executed, even with its
computed digest. Refine the objective and generate a new proposal.

## Optional OpenAI interpretation

With the optional SDK and environment credentials configured:

```powershell
.\.venv\Scripts\veriagent.exe propose "Please resolve ISSUE-1 and begin work on ISSUE-2" --provider openai
```

This attempts one potentially billable interpretation request. The model returns typed
requirements or a clarification. Every issue ID must explicitly occur in the objective,
and the set of proposed IDs must exactly match the mentioned set. Mixed positive/negative
instructions may consequently require clarification rather than automatically excluding
a mentioned target. Status enums, uniqueness and response shape are checked locally.

The model is instructed to treat the objective as untrusted data. These checks cannot
prove semantic correctness or general prompt-injection resistance: review the actual
statuses yourself. No application state or tool output is included in the interpretation
request. The existing `run` command keeps its original narrow deterministic parser.

Interpretation and planning are separate provider choices. After reviewing an OpenAI
proposal, `execute` defaults to offline planning. Explicit `execute --provider openai`
attempts a second paid request for a plan; recovery remains deterministic and local.
The execution planner cannot change the reviewed requirements. Refusals, invalid schema,
unmentioned/omitted targets and expired interpretation budgets produce a failed result
without a usable proposal or any tool operation.

## Files, accounting and approval semantics

Each `propose` call creates a UUID directory under `artifacts/proposals/` with an
`interpretation.json` result and, when interpretation succeeds, `proposal.json`. These
files include the objective and usage where available. Do not put secrets in objectives.
Interpretation failures retain usage and a sanitized error code, not raw provider errors.

`review` prints the normalized objective, requirements, interpretation usage and a SHA-256
digest of the canonical proposal content. `execute --approve <digest>` reads at most
64 KiB once, validates the schema and target IDs, and checks the digest **before** creating
the execution provider or sandbox. Formatting/key-order changes preserve the digest;
content changes invalidate it. Unknown fields such as `approved: true` are rejected.

The parsed immutable proposal is retained for execution, so it is not reread after checking.
The trace includes a `requirements_review` event before planning, with the approved content
digest and interpretation usage. Execution reports meter planning only: add interpretation
usage separately when measuring the total workflow. Proposal accounting is local metadata,
not an independently signed billing statement.

The digest is an accidental-change guard, not authentication, a secret token, a signature,
or proof that a human carefully reviewed the request. Anyone with local access can recompute
it. Programmatic callers can still construct `Task` objects directly; this is a CLI review
workflow, not an operating-system security boundary.

`propose` exits 0 when a proposal or clarification was saved, 1 on an interpretation
failure, and 2 for invalid CLI/configuration. `review` exits 1 for a clarification and
prints no executable digest. `execute` exits 2 for missing/invalid approval or proposal,
1 for a reported execution failure, and 0 for the agent's success claim. Baseline success
remains unverified; use `verify` or the default `recover` mode for independent checks.

## Reproducible checks and limits

`tests/fixtures/interpretation_cases.json` contains 24 fixed examples: 12 supported forms
and 12 requiring clarification. Tests check their exact expected outputs, not an LLM judge.
Additional tests cover changed-content approvals, malicious proposal fields, file-size
limits, early rejection, reviewed execution/recovery, and actual OpenAI SDK serialization
against an in-memory HTTP transport. All tests run without real credentials or paid calls.

These hand-authored grammar cases establish behavior only on this fixture. They are not
an unbiased language benchmark or a live-model accuracy result. Live schema acceptance,
real latency/cost, multilingual interpretation, interactive tool selection and model-driven
replanning remain unvalidated or unimplemented.
