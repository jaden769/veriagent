"""Fixed, independently specified benchmark requirements and initial application states."""

import hashlib
from importlib.resources import files

from pydantic import Field, model_validator

from veriagent.models import Schema, Status, Task


class BenchmarkCase(Schema):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    task: Task
    initial_statuses: dict[str, Status]

    @model_validator(mode="after")
    def seeded_targets(self) -> "BenchmarkCase":
        if set(self.initial_statuses) != {"ISSUE-1", "ISSUE-2", "ISSUE-3"}:
            raise ValueError("Specify the initial status of all three seeded issues")
        if any(r.issue_id not in self.initial_statuses for r in self.task.requirements):
            raise ValueError("Benchmark requirements must target seeded issues")
        return self


class BenchmarkCorpus(Schema):
    schema_version: int = Field(ge=1, le=1)
    cases: tuple[BenchmarkCase, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_ids(self) -> "BenchmarkCorpus":
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate benchmark case IDs")
        return self


def load_corpus() -> tuple[BenchmarkCorpus, str]:
    raw = files("veriagent").joinpath("scenarios/benchmark_tasks.json").read_bytes()
    if len(raw) > 65536:
        raise ValueError("Benchmark corpus exceeds 64 KiB")
    return BenchmarkCorpus.model_validate_json(raw), hashlib.sha256(raw).hexdigest()


def select_cases(task_ids: tuple[str, ...]) -> tuple[tuple[BenchmarkCase, ...], str]:
    corpus, digest = load_corpus()
    mapping = {case.id: case for case in corpus.cases}
    if not task_ids or len(set(task_ids)) != len(task_ids):
        raise ValueError("Select unique benchmark task IDs")
    if any(task_id not in mapping for task_id in task_ids):
        raise ValueError("Unknown benchmark task ID")
    return tuple(mapping[task_id] for task_id in task_ids), digest
