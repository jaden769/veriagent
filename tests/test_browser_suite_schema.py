import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_browser_suite import evaluation, mock_evaluations

from veriagent.browser_suite import render_suite_review, review_browser_suite
from veriagent.browser_suite_schema import suite_review_json_schema, validate_suite_review


@pytest.fixture
def report(tmp_path, monkeypatch):
    paths = mock_evaluations(monkeypatch, tmp_path, [evaluation("default", "one")])
    return review_browser_suite(paths)


def test_json_roundtrip_and_exported_schema(report):
    restored = json.loads(json.dumps(report))
    assert validate_suite_review(restored) == report
    assert restored["schema_version"] == 2
    path = Path(__file__).resolve().parents[1] / "docs/schemas/browser-suite-review-v2.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == suite_review_json_schema()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), 1),
        (("selection_passed",), "true"),
        (("counts", "controls"), True),
        (("counts", "successful_tasks"), 0),
        (("contract_coverage", "inputs"), 2),
        (("contract_coverage", "matched"), 1),
        (("coverage_complete",), True),
        (("controls_passed",), False),
        (("require_contract",), True),
        (("unexpected_field",), 1),
    ],
)
def test_corrupt_reports_are_rejected_before_rendering(report, path, value):
    changed = copy.deepcopy(report)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        render_suite_review(changed)


def test_consistent_but_inflated_totals_are_rejected(report):
    report["counts"].update(controls=2, matched_controls=2, successful_tasks=2)
    with pytest.raises(ValidationError, match="Suite totals"):
        validate_suite_review(report)


@pytest.mark.parametrize("flag", ["evidence_passed", "selection_passed"])
def test_rejected_reports_cannot_retain_outcomes(report, flag):
    report[flag] = False
    with pytest.raises(ValidationError):
        validate_suite_review(report)


def test_contract_category_must_match_child_metadata(report):
    report["contract_coverage"].update(unverifiable=0, matched=1)
    report["evaluations"][0]["contract_category"] = "matched"
    with pytest.raises(ValidationError, match="contract metadata"):
        validate_suite_review(report)


def test_child_outcome_details_must_match_counters(report):
    child = report["evaluations"][0]["review"]
    child["counts"].update(successful_tasks=0, expected_task_failures=1)
    with pytest.raises(ValidationError, match="Outcome details"):
        validate_suite_review(report)


@pytest.mark.parametrize("value", [True, False, 1.0, 2.0, "2"])
@pytest.mark.parametrize("nested", [False, True])
def test_schema_versions_require_exact_integer_types(report, value, nested):
    target = report["evaluations"][0]["review"] if nested else report
    target["schema_version"] = value
    with pytest.raises(ValidationError):
        validate_suite_review(report)
