import json

import pytest
from test_browser_suite import evaluation, mock_evaluations

from veriagent.browser_suite import render_suite_review, review_browser_suite
from veriagent.cli import main


def with_identity(audit, status):
    return {**audit, "matrix_contract": {"status": status}}


def test_mixed_contract_coverage_is_separate_from_task_outcomes(tmp_path, monkeypatch):
    audits = [
        with_identity(evaluation("default", "one"), "matched"),
        with_identity(evaluation("indexed", "two", actual=False, expected=False), "legacy_missing"),
    ]
    paths = mock_evaluations(monkeypatch, tmp_path, audits)
    result = review_browser_suite(paths)
    assert result["contract_coverage"] == dict(
        scope="selected_evaluation_inputs", inputs=2, matched=1, legacy_missing=1, unverifiable=0
    )
    assert result["counts"]["successful_tasks"] == 1
    assert result["counts"]["expected_task_failures"] == 1
    assert result["present_matrices"] == ["default", "indexed"]
    assert "matched=1, legacy_missing=1, unverifiable=0" in render_suite_review(result)


def test_strict_rejection_retains_contract_diagnostics_while_withholding_outcomes(
    tmp_path, monkeypatch
):
    good = with_identity(evaluation("default", "one"), "matched")
    legacy = with_identity(evaluation("indexed", "two"), "legacy_missing")
    legacy.update(evidence_passed=False, require_contract=True)
    legacy["checks"] = [{"check": "matrix_contract_required", "passed": False}]
    paths = mock_evaluations(monkeypatch, tmp_path, [good, legacy])
    result = review_browser_suite(paths, require_contract=True)
    assert result["counts"] is None and not result["evidence_passed"]
    assert result["contract_coverage"]["legacy_missing"] == 1
    assert result["evaluations"][1]["contract_category"] == "legacy_missing"


@pytest.mark.parametrize(
    "status",
    [
        "mismatch",
        "missing",
        "invalid",
        "unsupported_version",
        "not_checked",
        "unavailable",
        "future_status",
    ],
)
def test_unverifiable_statuses_have_a_bounded_explicit_category(tmp_path, monkeypatch, status):
    audit = with_identity(evaluation("default", "one"), status)
    audit["evidence_passed"] = False
    paths = mock_evaluations(monkeypatch, tmp_path, [audit])
    result = review_browser_suite(paths)
    assert result["contract_coverage"] == dict(
        scope="selected_evaluation_inputs", inputs=1, matched=0, legacy_missing=0, unverifiable=1
    )
    assert result["counts"] is None
    assert result["evaluations"][0]["review"]["matrix_contract"]["status"] == status


def test_matching_header_does_not_override_failed_nested_evidence(tmp_path, monkeypatch):
    audit = with_identity(evaluation("default", "one"), "matched")
    audit["evidence_passed"] = False
    audit["checks"] = [{"check": "batch_evidence:1", "passed": False}]
    paths = mock_evaluations(monkeypatch, tmp_path, [audit])
    result = review_browser_suite(paths)
    assert result["contract_coverage"]["matched"] == 1
    assert not result["evidence_passed"] and result["counts"] is None


def test_duplicate_inputs_do_not_inflate_distinct_matrix_coverage(tmp_path, monkeypatch):
    paths = mock_evaluations(
        monkeypatch,
        tmp_path,
        [
            with_identity(evaluation("default", "one"), "matched"),
            with_identity(evaluation("default", "two"), "matched"),
        ],
    )
    result = review_browser_suite(paths)
    assert result["contract_coverage"]["inputs"] == result["contract_coverage"]["matched"] == 2
    assert len(result["present_matrices"]) == 1
    assert not result["selection_passed"] and result["counts"] is None


def test_cli_json_reports_the_contract_denominator_without_provider_use(
    tmp_path, monkeypatch, capsys
):
    paths = mock_evaluations(
        monkeypatch, tmp_path, [with_identity(evaluation("default", "one"), "matched")]
    )
    monkeypatch.setattr(
        "veriagent.cli.configured_provider", lambda args: pytest.fail("No provider")
    )
    monkeypatch.setattr(
        "sys.argv", ["veriagent", "review-browser-suite", str(paths[0]), "--format", "json"]
    )
    main()
    output = json.loads(capsys.readouterr().out)
    assert output["contract_coverage"]["inputs"] == 1
    assert output["contract_coverage"]["matched"] == 1
    assert output["coverage_complete"] is False
