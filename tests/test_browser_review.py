import copy
import json

import pytest

from veriagent.browser_review import render_control_review, summarize_control_audit
from veriagent.cli import main


def audited_outcomes():
    rows, trials = [], []
    # Success, expected failure, unexpected failure, unexpected success.
    for index, (actual, expected, matched) in enumerate(
        [(True, True, True), (False, False, True), (False, True, False), (True, False, False)]
    ):
        relative = f"trial-{index + 1:03d}/" + str(index) * 32
        trials.append(dict(bundle_directory=relative, task_passed=actual, checks=[]))
        rows.append(
            dict(
                task_id=f"case_{index}",
                scenario="fixture",
                mode="recover",
                max_retries=2,
                batch_directory="a" * 32,
                bundle_directory=relative,
                expected={"execution_passed": expected},
                passed=matched,
                mismatches={}
                if matched
                else {"execution_passed": {"expected": expected, "actual": actual}},
            )
        )
    return dict(
        evidence_passed=True,
        controls_passed=False,
        controls=rows,
        checks=[],
        batches=[dict(directory="a" * 32, checks=[], trials=trials)],
    )


def test_task_failures_and_expectation_mismatches_remain_distinct():
    report = summarize_control_audit(audited_outcomes())
    assert report["counts"] == dict(
        controls=4,
        matched_controls=2,
        successful_tasks=2,
        expected_task_failures=1,
        unexpected_task_failures=1,
        expectation_mismatches=2,
    )
    assert report["expected_task_failures"][0]["task_id"] == "case_1"
    assert report["unexpected_task_failures"][0]["task_id"] == "case_2"
    assert report["controls_passed"] is False and report["evidence_passed"]
    text = render_control_review(report)
    assert "Controls matched: 2/4" in text and "Differences:" in text
    assert "Evidence: " + "a" * 32 in text


def test_expected_failure_with_another_mismatch_is_still_an_expected_task_failure():
    audit = audited_outcomes()
    audit["controls"][1].update(passed=False, mismatches={"commits": {"expected": 1, "actual": 2}})
    report = summarize_control_audit(audit)
    assert report["counts"]["expected_task_failures"] == 1
    assert report["counts"]["unexpected_task_failures"] == 1
    assert report["counts"]["expectation_mismatches"] == 3


def test_partial_evidence_withholds_all_outcome_counts_and_collects_nested_gaps():
    audit = audited_outcomes()
    audit["evidence_passed"] = False
    audit["batches"][0]["trials"][0]["checks"] = [{"check": "hash:trace.json", "passed": False}]
    report = summarize_control_audit(audit)
    assert report["counts"] is None and report["controls_passed"] is None
    assert not report["expectation_mismatches"]
    assert report["evidence_gaps"][0]["check"] == "hash:trace.json"
    assert "Outcome counts withheld" in render_control_review(report)


def test_evidence_gap_display_is_bounded():
    report = summarize_control_audit(
        dict(
            evidence_passed=False, checks=[dict(check=f"gap-{i}", passed=False) for i in range(101)]
        )
    )
    assert len(report["evidence_gaps"]) == 100 and report["gaps_truncated"]
    assert "Additional evidence gaps omitted" in render_control_review(report)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown_outcome"])
def test_incomplete_trial_mapping_cannot_produce_positive_totals(mutation):
    audit = audited_outcomes()
    if mutation == "missing":
        audit["batches"][0]["trials"].pop()
    elif mutation == "duplicate":
        audit["controls"][1]["bundle_directory"] = audit["controls"][0]["bundle_directory"]
    else:
        audit["batches"][0]["trials"][0]["task_passed"] = None
    report = summarize_control_audit(audit)
    assert not report["evidence_passed"] and report["counts"] is None


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_cli_uses_offline_review_and_preserves_valid_expectation_failure(
    monkeypatch, capsys, output_format
):
    audit = audited_outcomes()
    original = copy.deepcopy(audit)
    monkeypatch.setattr(
        "veriagent.browser_review.audit_browser_controls", lambda path, **options: audit
    )
    monkeypatch.setattr(
        "veriagent.cli.configured_provider", lambda args: pytest.fail("No provider")
    )
    monkeypatch.setattr(
        "sys.argv", ["veriagent", "review-browser-controls", "saved", "--format", output_format]
    )
    main()
    output = capsys.readouterr().out
    if output_format == "json":
        assert json.loads(output)["controls_passed"] is False
    else:
        assert "Unexpected task failures: 1" in output
    assert original == audit


def test_cli_missing_evidence_returns_failure_with_a_readable_report(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sys.argv", ["veriagent", "review-browser-controls", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "Outcome counts withheld" in capsys.readouterr().out
