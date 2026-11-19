"""Untrusted intent proposals and explicit content-bound review; no tools are called here."""

import hashlib
import hmac
import json
import re
import time
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from veriagent.budgeting import ModelBudgetExceeded
from veriagent.models import (
    Interpretation,
    ModelBudgetState,
    ModelUsage,
    ProviderDiagnostic,
    Requirement,
    Status,
    Task,
    TaskProposal,
)


class InterpretationProvider(Protocol):
    @property
    def diagnostic(self) -> ProviderDiagnostic | None: ...

    def begin_run(self) -> None: ...

    @property
    def budget_state(self) -> ModelBudgetState | None: ...

    @property
    def usage(self) -> ModelUsage: ...

    def interpret(self, objective: str, *, timeout: float | None = None) -> Interpretation: ...


def validate_targets(objective: str, interpretation: Interpretation) -> None:
    if interpretation.clarification is not None:
        return
    mentioned = set(re.findall(r"\bISSUE-\d+\b", objective.upper()))
    proposed = {r.issue_id for r in interpretation.requirements}
    if not mentioned or proposed != mentioned:
        raise ValueError(
            "Proposed targets must exactly match the explicit issue IDs in the objective"
        )


def interpret_offline(objective: str) -> Interpretation:
    """Conservative full-match grammar with explicit IDs and a few status synonyms."""
    verbs = {
        "close": Status.DONE,
        "finish": Status.DONE,
        "complete": Status.DONE,
        "resolve": Status.DONE,
        "reopen": Status.OPEN,
        "open": Status.OPEN,
        "start": Status.IN_PROGRESS,
        "begin": Status.IN_PROGRESS,
    }
    ids = r"(ISSUE-\d+(?:\s*(?:,|and)\s*ISSUE-\d+)*)"
    clauses = re.split(
        r"\s*;\s*|\s+and\s+(?=(?:please\s+)?(?:close|finish|complete|resolve|reopen|open|"
        r"start|begin|set|mark)\b)",
        objective.strip().rstrip("."),
        flags=re.IGNORECASE,
    )
    requirements = []
    for clause in clauses:
        clause = re.sub(r"^please\s+", "", clause.strip(), flags=re.IGNORECASE)
        canonical = re.fullmatch(
            r"(?:set|mark)\s+" + ids + r"\s+(?:to|as)\s+(open|in_progress|done)",
            clause,
            re.IGNORECASE,
        )
        imperative = re.fullmatch(r"(" + "|".join(verbs) + r")\s+" + ids, clause, re.IGNORECASE)
        if canonical:
            targets, value = canonical.groups()
            status = Status(value.lower())
        elif imperative:
            verb, targets = imperative.groups()
            status = verbs[verb.lower()]
        else:
            return Interpretation(
                requirements=(),
                clarification=(
                    "Specify explicit issue IDs and requested statuses. Examples: "
                    "'Close ISSUE-1 and start ISSUE-2' or 'Set ISSUE-1 to done'."
                ),
            )
        requirements.extend(
            Requirement(issue_id=target.upper(), status=status)
            for target in re.findall(r"ISSUE-\d+", targets, re.IGNORECASE)
        )
    if len({r.issue_id for r in requirements}) != len(requirements):
        return Interpretation(
            requirements=(),
            clarification=(
                "Each issue needs one unambiguous final status; "
                "remove repeated or conflicting targets."
            ),
        )
    result = Interpretation(requirements=tuple(requirements))
    validate_targets(objective, result)
    return result


def proposal_digest(proposal: TaskProposal) -> str:
    canonical = json.dumps(
        proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_proposal(path: Path) -> TaskProposal:
    # One bounded read: reviewed bytes are parsed once and retained, avoiding a reread race.
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Proposal exceeds the 64 KiB size limit")
    try:
        proposal = TaskProposal.model_validate_json(raw)
    except ValueError:
        raise ValueError(
            "Invalid proposal schema; regenerate it with the propose command"
        ) from None
    validate_targets(proposal.objective, proposal.interpretation)
    return proposal


def approved_task(path: Path, digest: str) -> tuple[Task, TaskProposal]:
    proposal = load_proposal(path)
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or not hmac.compare_digest(
        proposal_digest(proposal), digest
    ):
        raise ValueError("Approval digest does not match this proposal; review it again")
    return proposal.task(), proposal


def propose_task(
    objective: str, provider: InterpretationProvider, output: Path, *, timeout: float = 60
) -> dict:
    if not isinstance(objective, str) or not 1 <= len(objective) <= 2000:
        raise ValueError("Objective must contain 1 to 2000 characters")
    if not 0 < timeout <= 3600:
        raise ValueError("Interpretation timeout must be between 0 and 3600 seconds")
    directory = output.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    provider.begin_run()
    start = time.monotonic()
    proposal = None
    error = None
    try:
        interpretation = provider.interpret(objective, timeout=timeout)
        if time.monotonic() - start >= timeout:
            raise TimeoutError("Interpretation exceeded its budget")
        validate_targets(objective, interpretation)
        proposal = TaskProposal(
            objective=objective, interpretation=interpretation, interpretation_usage=provider.usage
        )
    except Exception as exc:
        error = (
            "model_budget_exhausted"
            if isinstance(exc, ModelBudgetExceeded)
            else "interpretation_failed"
        )
    result = {
        "schema_version": 1,
        "objective": objective,
        "directory": str(directory),
        "error": error,
        "proposal_file": str(directory / "proposal.json") if proposal else None,
        "needs_clarification": proposal.interpretation.clarification is not None
        if proposal
        else None,
        "elapsed_ms": (time.monotonic() - start) * 1000,
        "model_usage": provider.usage.model_dump(mode="json"),
        "provider_diagnostic": provider.diagnostic.model_dump(mode="json")
        if provider.diagnostic
        else None,
        "model_budget": provider.budget_state.model_dump(mode="json")
        if provider.budget_state
        else None,
    }
    if proposal:
        (directory / "proposal.json").write_text(
            proposal.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    (directory / "interpretation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
