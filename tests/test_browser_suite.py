import copy
import json

import pytest

from veriagent.browser_controls import CONTROL_MATRICES
from veriagent.browser_suite import render_suite_review, review_browser_suite
from veriagent.cli import main


def evaluation(matrix, run_id, *, matched=True, actual=True, expected=True):
    relative = "trial-001/" + "b" * 32
    control = dict(
        task_id="fixture",
        scenario="clean",
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
    return dict(
        matrix=matrix,
        evidence_passed=True,
        controls_passed=matched,
        checks=[],
        run_ids=[run_id],
        controls=[control],
        batches=[
            dict(
                directory="a" * 32,
                checks=[],
                trials=[dict(bundle_directory=relative, task_passed=actual, checks=[])],
            )
        ],
    )


def mock_evaluations(monkeypatch, tmp_path, audits):
    paths = [tmp_path / str(i) for i in range(len(audits))]
    mapping = {path.resolve(): audit for path, audit in zip(paths, audits, strict=True)}
    monkeypatch.setattr(
        "veriagent.browser_suite.audit_browser_controls", lambda path, **options: mapping[path]
    )
    return paths


def test_partial_selection_is_explicit_and_outcomes_remain_separate(tmp_path, monkeypatch):
    audits = [
        evaluation("default", "one", actual=False, expected=False),
        evaluation("indexed", "two", matched=False, actual=False),
    ]
    before = copy.deepcopy(audits)
    paths = mock_evaluations(monkeypatch, tmp_path, audits)
    report = review_browser_suite(paths)
    assert report["evidence_passed"] and report["selection_passed"]
    assert not report["coverage_complete"] and report["controls_passed"] is False
    assert len(report["missing_matrices"]) == 4
    assert report["counts"]["expected_task_failures"] == 1
    assert report["counts"]["unexpected_task_failures"] == 1
    assert report["counts"]["expectation_mismatches"] == 1
    assert "Matrix coverage: 2/6" in render_suite_review(report)
    assert audits == before


def test_require_all_withholds_totals_for_a_partial_valid_selection(tmp_path, monkeypatch):
    paths = mock_evaluations(monkeypatch, tmp_path, [evaluation("default", "one")])
    result = review_browser_suite(paths, require_all=True)
    assert result["evidence_passed"] and not result["selection_passed"]
    assert result["counts"] is None and not result["coverage_complete"]


def test_all_six_distinct_matrices_satisfy_required_coverage(tmp_path, monkeypatch):
    paths = mock_evaluations(
        monkeypatch,
        tmp_path,
        [evaluation(matrix, str(i)) for i, matrix in enumerate(CONTROL_MATRICES)],
    )
    result = review_browser_suite(paths, require_all=True)
    assert result["evidence_passed"] and result["selection_passed"] and result["coverage_complete"]
    assert result["counts"]["controls"] == 6 and not result["missing_matrices"]


@pytest.mark.parametrize(
    "problem", ["duplicate_matrix", "reused_run", "missing_run", "invalid_evidence"]
)
def test_untrusted_or_reused_inputs_withhold_suite_totals(tmp_path, monkeypatch, problem):
    first, second = evaluation("default", "one"), evaluation("indexed", "two")
    if problem == "duplicate_matrix":
        second["matrix"] = "default"
    elif problem == "reused_run":
        second["run_ids"] = ["one"]
    elif problem == "missing_run":
        second["run_ids"] = []
    else:
        second["evidence_passed"] = False
        second["checks"] = [{"check": "missing_manifest", "passed": False}]
    paths = mock_evaluations(monkeypatch, tmp_path, [first, second])
    report = review_browser_suite(paths)
    assert not report["evidence_passed"] and report["counts"] is None
    assert "Outcome totals withheld" in render_suite_review(report)


@pytest.mark.parametrize("count", [0, 7])
def test_input_bound_is_checked_before_auditing(tmp_path, monkeypatch, count):
    monkeypatch.setattr(
        "veriagent.browser_suite.audit_browser_controls", lambda path: pytest.fail("No audit")
    )
    with pytest.raises(ValueError):
        review_browser_suite([tmp_path / str(i) for i in range(count)])


def test_same_directory_cannot_be_counted_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "veriagent.browser_suite.audit_browser_controls", lambda path: pytest.fail("No audit")
    )
    with pytest.raises(ValueError):
        review_browser_suite([tmp_path, tmp_path / "."])


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_cli_is_offline_and_emits_selection_coverage(tmp_path, monkeypatch, capsys, output_format):
    paths = mock_evaluations(monkeypatch, tmp_path, [evaluation("default", "one")])
    monkeypatch.setattr(
        "veriagent.cli.configured_provider", lambda args: pytest.fail("No provider")
    )
    monkeypatch.setattr(
        "sys.argv", ["veriagent", "review-browser-suite", str(paths[0]), "--format", output_format]
    )
    main()
    output = capsys.readouterr().out
    if output_format == "json":
        assert json.loads(output)["coverage_complete"] is False
    else:
        assert "Matrix coverage: 1/6" in output


def test_cli_require_all_fails_for_missing_matrices(tmp_path, monkeypatch, capsys):
    paths = mock_evaluations(monkeypatch, tmp_path, [evaluation("default", "one")])
    monkeypatch.setattr(
        "sys.argv", ["veriagent", "review-browser-suite", str(paths[0]), "--require-all"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "required_matrices_missing" in capsys.readouterr().out
