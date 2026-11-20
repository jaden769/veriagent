"""Immutable catalog for fixed browser matrix selections and their ordered batches."""

from dataclasses import dataclass

from veriagent.browser_faults import (
    BROWSER_SCENARIOS,
    INDEXED_BROWSER_SCENARIOS,
    MULTI_BROWSER_SCENARIOS,
)

ALL_TASKS = (
    "single_done",
    "pair_done",
    "mixed_status",
    "reopen",
    "already_satisfied",
    "partial_satisfied",
)
PAIRED_TASKS = ("pair_done", "mixed_status")


@dataclass(frozen=True)
class MatrixBatch:
    tasks: tuple[str, ...]
    scenarios: tuple[str, ...]
    modes: tuple[str, ...] = ("recover",)
    max_retries: int = 2
    max_actions: int = 8
    max_decisions: int = 8

    def spec(self) -> dict:
        return {
            "tasks": self.tasks,
            "scenarios": self.scenarios,
            "modes": self.modes,
            "max_retries": self.max_retries,
            "max_actions": self.max_actions,
            "max_decisions": self.max_decisions,
        }


@dataclass(frozen=True)
class ControlMatrix:
    name: str
    description: str
    batches: tuple[MatrixBatch, ...]
    flag: str | None = None
    legacy_required: bool = False
    requires_budget_metadata: bool = False

    @property
    def control_count(self) -> int:
        return sum(len(b.tasks) * len(b.scenarios) * len(b.modes) for b in self.batches)

    @property
    def cli_option(self) -> str | None:
        return "--" + self.flag.replace("_", "-") if self.flag else None

    @property
    def cli_help(self) -> str:
        return f"Check {self.control_count} {self.description} controls"

    def specs(self) -> list[dict]:
        return [batch.spec() for batch in self.batches]


def _limits(tasks, scenarios, levels):
    pairs = tuple((level, 8) for level in levels) + tuple((8, level) for level in levels)
    return tuple(
        MatrixBatch(tasks, scenarios, max_actions=actions, max_decisions=decisions)
        for actions, decisions in pairs
    )


CONTROL_CATALOG = (
    ControlMatrix(
        "default",
        "fixed offline dynamic",
        (
            MatrixBatch(ALL_TASKS, BROWSER_SCENARIOS),
            MatrixBatch(("single_done",), BROWSER_SCENARIOS, ("baseline",)),
        ),
    ),
    ControlMatrix(
        "indexed",
        "later-write",
        (MatrixBatch(ALL_TASKS, INDEXED_BROWSER_SCENARIOS),),
        flag="indexed",
        legacy_required=True,
    ),
    ControlMatrix(
        "multi_event",
        "retry-exhaustion",
        tuple(
            MatrixBatch(PAIRED_TASKS, MULTI_BROWSER_SCENARIOS, max_retries=retries)
            for retries in (0, 1, 2)
        ),
        flag="multi_event",
        legacy_required=True,
    ),
    ControlMatrix(
        "budget_boundaries",
        "action/decision-limit",
        _limits(PAIRED_TASKS, ("clean",), (2, 3, 4)),
        flag="budget_boundaries",
        requires_budget_metadata=True,
    ),
    ControlMatrix(
        "fault_budget_boundaries",
        "fault/recovery budget",
        _limits(PAIRED_TASKS, ("second_drop", "second_lost_ack"), (4, 5, 6)),
        flag="fault_budget_boundaries",
        requires_budget_metadata=True,
    ),
    ControlMatrix(
        "satisfied_budget_boundaries",
        "pre-satisfied goal budget",
        _limits(("already_satisfied", "partial_satisfied"), ("clean", "second_drop"), (1, 2)),
        flag="satisfied_budget_boundaries",
        requires_budget_metadata=True,
    ),
)
CONTROL_MATRICES = tuple(matrix.name for matrix in CONTROL_CATALOG)
CONTROL_MATRIX_FLAGS = tuple(matrix.flag for matrix in CONTROL_CATALOG if matrix.flag)


def select_control_matrix(flags: dict) -> ControlMatrix:
    if set(flags) - set(CONTROL_MATRIX_FLAGS) or any(
        type(value) is not bool for value in flags.values()
    ):
        raise ValueError("Unknown or non-boolean browser matrix flag")
    selected = [
        matrix for matrix in CONTROL_CATALOG if matrix.flag and flags.get(matrix.flag, False)
    ]
    if len(selected) > 1:
        raise ValueError("Select one browser control matrix")
    return selected[0] if selected else CONTROL_CATALOG[0]


def saved_control_matrix(saved: dict) -> ControlMatrix:
    if any(matrix.legacy_required and matrix.flag not in saved for matrix in CONTROL_CATALOG):
        raise ValueError("Missing legacy browser matrix flag")
    return select_control_matrix({flag: saved.get(flag, False) for flag in CONTROL_MATRIX_FLAGS})
