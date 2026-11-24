# Explicit agent verification admission

Agent and DynamicAgent now recognize an explicitly supplied
[BudgetedStateVerifier](BOUNDED_VERIFICATION.md). Existing constructors, CLI defaults,
Budget, Mode and RunReport schemas are unchanged. Ordinary StateVerifier still follows
the original path with no added admission events or limits in configuration.

Given a fresh sandbox and TraceStore, opt in through Python by passing a fresh adapter
and ledger in the existing verifier argument:

```python
from veriagent.bounded_verification import BudgetedStateVerifier
from veriagent.dynamic import DynamicAgent
from veriagent.executor import Executor
from veriagent.models import Budget
from veriagent.planner import MockProvider
from veriagent.verification_budget import VerificationBudgetLedger, VerificationLimits

ledger = VerificationBudgetLedger(VerificationLimits(max_calls=2, max_target_rows=4))
verifier = BudgetedStateVerifier(sandbox.path, ledger)
agent = DynamicAgent(MockProvider(), Executor(sandbox), verifier, traces,
                     Budget(max_actions=8, max_decisions=8))
# report = agent.run(original_task)
```

One adapter/ledger binds to one run ID and original task. Reuse or an already-consumed
ledger is rejected before new task trace entries or planning decisions. Create a fresh
instance for each trial. Unlimited opt-in limits retain existing observed outcomes,
while still adding explicit accounting traces.

## Outcomes and timing

Admission denial is an honest terminal `failure: budget`, with `claimed_success: false`,
`verified_success: null` and no verification snapshot for the denied check. Earlier
mismatch evidence is not reused as the final denied result. No recovery is admitted after
denial; recovery already spent before denial remains recorded.

Static protected modes verify after a plan pass, so tool writes can precede the first
denial. Dynamic protected modes verify initially, so zero allowance can stop before any
action or decision. An already-satisfied dynamic task still needs one admitted trusted
check to claim verified success. Baseline performs no trusted verification and consumes
none of this allowance; its original false-claim controls remain possible.

Denial does not roll back application changes. A repair can commit and then encounter a
denied final check; the agent reports budget failure while an independent final evaluator
may find satisfied targets. Keep those outcomes separate. Admitted verifier exceptions
remain internal failures, with reservations retained and actual partial work unknown.

## Durable trace contract

The opt-in configuration adds `verification_limits`. Each requested check emits a
`verification_budget` event with a state snapshot:

| Phase | Meaning |
| --- | --- |
| `admitted` | Call/row reservation consumed; pending true, before trusted SQLite access |
| `completed` | Full trusted snapshot returned and settled; pending false |
| `error` | Admitted check raised or returned invalid evidence; pending false, total work unknown |
| `denied` | No reservation or oracle read; reason identifies exhausted call or target-row allowance |

Admission and denial include `requested_target_rows`; denial includes the ledger's fixed
reason code. Agents also emit `verification_denied` with `failure: budget`; they do not
label denial as a failed verifier call. Ordinary completed `verification` events and
`verification_error` events continue to describe actual attempts. Report schemas are not
extended: detailed quota state is in the traces. A trace-storage failure cannot establish
durable evidence and must not be interpreted as a successful budget-controlled trial.

No hidden fault labels or quota state are added to provider observations. The existing
task/feedback/verification protocol remains in place. Setup and post-run evaluator reads
remain outside this execution allowance, and tool reads still have their own action cost.

## Validation and research boundary

Focused tests cover initial and post-repair denial, no oracle connection on denial,
fresh-run binding, admitted errors, baseline zero use, initial satisfaction and unlimited
parity in both engines across all modes. The full suite is run for this loop integration.
These are admission/behavior checks, not a new comparator outcome study.

Historical comparison plans/results retain their original code fingerprints. Agent source
has now changed; do not rewrite those historical hashes or silently call this the same
pinned implementation. A new bounded-oracle experiment requires a revised snapshot,
explicit limits, exposure/accounting review and prospective analysis plan. Reflection,
budget-controlled ablations and external research approval remain pending.
