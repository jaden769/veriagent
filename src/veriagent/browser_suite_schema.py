"""Version-2 suite output: strict structure plus runtime cross-field invariants."""

from collections import Counter
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from veriagent.browser_catalog import CONTROL_MATRICES
from veriagent.models import Schema

Count = Annotated[int, Field(ge=0, le=130)]
MatrixName = Annotated[str, Field(json_schema_extra={"enum": list(CONTROL_MATRICES)})]
ContractCategory = Literal["matched", "legacy_missing", "unverifiable"]


class OutputSchema(Schema):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class OutcomeCounts(OutputSchema):
    controls: Annotated[int, Field(ge=1, le=130)]
    matched_controls: Count
    successful_tasks: Count
    expected_task_failures: Count
    unexpected_task_failures: Count
    expectation_mismatches: Count

    @model_validator(mode="after")
    def partitions(self):
        if (
            self.controls
            != self.successful_tasks + self.expected_task_failures + self.unexpected_task_failures
        ):
            raise ValueError("Task outcome counts must partition controls")
        if self.controls != self.matched_controls + self.expectation_mismatches:
            raise ValueError("Expectation counts must partition controls")
        return self


class ContractCoverage(OutputSchema):
    scope: Literal["selected_evaluation_inputs"]
    inputs: Annotated[int, Field(ge=1, le=6)]
    matched: Annotated[int, Field(ge=0, le=6)]
    legacy_missing: Annotated[int, Field(ge=0, le=6)]
    unverifiable: Annotated[int, Field(ge=0, le=6)]

    @model_validator(mode="after")
    def partition(self):
        if self.inputs != self.matched + self.legacy_missing + self.unverifiable:
            raise ValueError("Contract categories must partition evaluation inputs")
        return self


class ContractMetadata(OutputSchema):
    status: Annotated[str, Field(min_length=1, max_length=80)]
    saved: dict[str, Any] | None = None
    current: dict[str, Any] | None = None


class ControlDetail(OutputSchema):
    task_id: str
    scenario: str
    mode: Literal["baseline", "verify", "recover"]
    max_retries: Annotated[int, Field(ge=0, le=100)]
    batch_directory: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    bundle_directory: Annotated[str, Field(pattern=r"^trial-[0-9]{3}/[0-9a-f]{32}$")]
    max_actions: Annotated[int, Field(ge=1, le=10000)] | None = None
    max_decisions: Annotated[int, Field(ge=1, le=1000)] | None = None
    mismatches: dict[str, dict[str, Any]] | None = None


class EvidenceGap(OutputSchema):
    location: Annotated[str, Field(min_length=1, max_length=4096)]
    check: Annotated[str, Field(min_length=1, max_length=4096)]


class ControlReviewOutput(OutputSchema):
    schema_version: Literal[1]
    evidence_passed: bool
    controls_passed: bool | None
    require_contract: bool
    matrix_contract: ContractMetadata
    counts: OutcomeCounts | None
    expected_task_failures: Annotated[list[ControlDetail], Field(max_length=130)]
    unexpected_task_failures: Annotated[list[ControlDetail], Field(max_length=130)]
    expectation_mismatches: Annotated[list[ControlDetail], Field(max_length=130)]
    evidence_gaps: Annotated[list[EvidenceGap], Field(max_length=100)]
    gaps_truncated: bool
    limitations: str

    @model_validator(mode="after")
    def valid_outcomes(self):
        lists = (
            self.expected_task_failures,
            self.unexpected_task_failures,
            self.expectation_mismatches,
        )
        if not self.evidence_passed:
            if self.counts is not None or self.controls_passed is not None or any(lists):
                raise ValueError("Invalid evaluation evidence must withhold outcomes")
            return self
        if (
            self.counts is None
            or self.controls_passed is None
            or self.evidence_gaps
            or self.gaps_truncated
        ):
            raise ValueError("Valid evaluation evidence requires complete outcome counts")
        if self.require_contract and self.matrix_contract.status != "matched":
            raise ValueError("Strict evaluation evidence requires a matched contract")
        expected_lengths = (
            self.counts.expected_task_failures,
            self.counts.unexpected_task_failures,
            self.counts.expectation_mismatches,
        )
        if tuple(map(len, lists)) != expected_lengths:
            raise ValueError("Outcome details must match their counters")
        if self.controls_passed != (self.counts.matched_controls == self.counts.controls):
            raise ValueError("Evaluation pass flag disagrees with expectation counts")
        return self


class EvaluationOutput(OutputSchema):
    directory: Annotated[str, Field(min_length=1, max_length=32768)]
    matrix: MatrixName | None
    contract_category: ContractCategory
    review: ControlReviewOutput

    @field_validator("matrix")
    @classmethod
    def known_matrix(cls, value):
        if value is not None and value not in CONTROL_MATRICES:
            raise ValueError("Unknown matrix name")
        return value


class SuiteIssue(OutputSchema):
    issue: Literal[
        "invalid_evaluation_evidence",
        "duplicate_matrix",
        "missing_or_reused_run_ids",
        "required_matrices_missing",
    ]
    evaluation: Annotated[int, Field(ge=1, le=6)] | None = None


class SuiteReviewOutput(OutputSchema):
    schema_version: Literal[2]
    evidence_passed: bool
    selection_passed: bool
    controls_passed: bool | None
    require_all: bool
    require_contract: bool
    coverage_complete: bool
    present_matrices: Annotated[list[MatrixName], Field(max_length=6)]
    missing_matrices: Annotated[list[MatrixName], Field(max_length=6)]
    contract_coverage: ContractCoverage
    counts: OutcomeCounts | None
    evaluations: Annotated[list[EvaluationOutput], Field(min_length=1, max_length=6)]
    issues: Annotated[list[SuiteIssue], Field(max_length=32)]
    limitations: str

    @model_validator(mode="after")
    def reconcile(self):
        if self.contract_coverage.inputs != len(self.evaluations):
            raise ValueError("Contract input denominator disagrees with evaluations")
        categories = Counter()
        admitted = []
        for row in self.evaluations:
            status = row.review.matrix_contract.status
            category = status if status in ("matched", "legacy_missing") else "unverifiable"
            if (
                row.contract_category != category
                or row.review.require_contract != self.require_contract
            ):
                raise ValueError("Evaluation contract metadata disagrees with suite policy")
            categories[category] += 1
            if row.review.evidence_passed:
                if row.matrix is None:
                    raise ValueError("Valid evaluation evidence requires a matrix identity")
                admitted.append(row.matrix)
        if any(
            categories[name] != getattr(self.contract_coverage, name)
            for name in ("matched", "legacy_missing", "unverifiable")
        ):
            raise ValueError("Contract coverage disagrees with per-evaluation metadata")
        present = [name for name in CONTROL_MATRICES if name in admitted]
        missing = [name for name in CONTROL_MATRICES if name not in admitted]
        if (
            self.present_matrices != present
            or self.missing_matrices != missing
            or self.coverage_complete != (not missing)
        ):
            raise ValueError("Matrix coverage is inconsistent")
        duplicate = len(admitted) != len(set(admitted))
        if self.selection_passed != (not duplicate and (not self.require_all or not missing)):
            raise ValueError("Selection status disagrees with coverage requirements")
        if len({row.directory for row in self.evaluations}) != len(self.evaluations):
            raise ValueError("Duplicate evaluation directory")
        if any(
            issue.evaluation is not None and issue.evaluation > len(self.evaluations)
            for issue in self.issues
        ):
            raise ValueError("Issue references a nonexistent evaluation")
        if self.evidence_passed and (
            duplicate
            or any(not row.review.evidence_passed for row in self.evaluations)
            or any(issue.issue != "required_matrices_missing" for issue in self.issues)
        ):
            raise ValueError("Positive evidence flag contradicts evidence diagnostics")
        admitted_outcomes = self.evidence_passed and self.selection_passed
        if not admitted_outcomes:
            if self.counts is not None or self.controls_passed is not None:
                raise ValueError("Rejected suite evidence/selection must withhold outcomes")
        else:
            if self.counts is None or self.controls_passed is None:
                raise ValueError("Accepted suite requires outcome totals")
            totals = {
                key: sum(getattr(row.review.counts, key) for row in self.evaluations)
                for key in OutcomeCounts.model_fields
            }
            if self.counts.model_dump() != totals:
                raise ValueError("Suite totals disagree with evaluation counts")
            if self.controls_passed != all(row.review.controls_passed for row in self.evaluations):
                raise ValueError("Suite pass flag disagrees with evaluation outcomes")
        return self


def validate_suite_review(result: dict) -> dict:
    SuiteReviewOutput.model_validate(result)
    return result


def suite_review_json_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **SuiteReviewOutput.model_json_schema(),
    }
