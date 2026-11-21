import json

import pytest
from test_browser_contract import versioned_evaluation
from test_browser_controls_audit import fixture_evaluation
from test_browser_controls_audit import nested_audit as nested_audit
from test_browser_suite import evaluation, mock_evaluations

from veriagent.browser_controls_audit import audit_browser_controls
from veriagent.browser_review import render_control_review, review_browser_controls
from veriagent.browser_suite import render_suite_review, review_browser_suite
from veriagent.cli import main


def test_strict_audit_accepts_matched_contract_without_rewriting(tmp_path, nested_audit):
    directory = versioned_evaluation(tmp_path)
    before = (directory / "controls.json").read_bytes()
    result = audit_browser_controls(directory, require_contract=True)
    assert result["evidence_passed"] and result["require_contract"]
    assert result["matrix_contract"]["status"] == "matched"
    assert before == (directory / "controls.json").read_bytes()


def test_legacy_compatibility_remains_default_but_strict_audit_stops_early(
    tmp_path, nested_audit, monkeypatch
):
    directory = fixture_evaluation(tmp_path / "legacy")
    assert audit_browser_controls(directory)["evidence_passed"]
    monkeypatch.setattr(
        "veriagent.browser_controls_audit.audit_browser_batch",
        lambda path: pytest.fail("No legacy nested interpretation"),
    )
    result = audit_browser_controls(directory, require_contract=True)
    assert not result["evidence_passed"] and result["matrix_contract"]["status"] == "legacy_missing"
    assert {"check": "matrix_contract_required", "passed": False} in result["checks"]


def test_strict_single_review_withholds_legacy_counts(tmp_path):
    directory = fixture_evaluation(tmp_path / "legacy")
    result = review_browser_controls(directory, require_contract=True)
    assert result["counts"] is None and result["require_contract"]
    text = render_control_review(result)
    assert "matched identity required" in text and "legacy_missing" in text


def test_suite_propagates_policy_to_every_selected_evaluation(tmp_path, monkeypatch):
    audits = [evaluation("default", "one"), evaluation("indexed", "two")]
    paths = [tmp_path / "a", tmp_path / "b"]
    seen = []

    def audit(path, *, require_contract=False):
        seen.append(require_contract)
        result = audits[paths.index(path)]
        result.update(require_contract=require_contract, matrix_contract={"status": "matched"})
        return result

    monkeypatch.setattr("veriagent.browser_suite.audit_browser_controls", audit)
    result = review_browser_suite(paths, require_contract=True)
    assert seen == [True, True] and result["evidence_passed"] and result["selection_passed"]
    assert not result["coverage_complete"]
    assert "every selected evaluation" in render_suite_review(result)


def test_a_single_unmatched_evaluation_withholds_strict_suite_totals(tmp_path, monkeypatch):
    good, legacy = evaluation("default", "one"), evaluation("indexed", "two")
    good.update(require_contract=True, matrix_contract={"status": "matched"})
    legacy.update(
        require_contract=True, evidence_passed=False, matrix_contract={"status": "legacy_missing"}
    )
    paths = mock_evaluations(monkeypatch, tmp_path, [good, legacy])
    result = review_browser_suite(paths, require_contract=True)
    assert not result["evidence_passed"] and result["counts"] is None


@pytest.mark.parametrize("command", ["audit-browser-controls", "review-browser-controls"])
def test_cli_strict_policy_rejects_legacy_and_emits_explicit_status(
    tmp_path, monkeypatch, capsys, command
):
    directory = fixture_evaluation(tmp_path / "legacy")
    arguments = ["veriagent", command, str(directory), "--require-contract"]
    if command == "review-browser-controls":
        arguments.extend(["--format", "json"])
    monkeypatch.setattr("sys.argv", arguments)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["require_contract"] and result["matrix_contract"]["status"] == "legacy_missing"


def test_cli_strict_review_accepts_matched_identity(tmp_path, nested_audit, monkeypatch, capsys):
    directory = versioned_evaluation(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "review-browser-controls",
            str(directory),
            "--require-contract",
            "--format",
            "json",
        ],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["evidence_passed"] and result["matrix_contract"]["status"] == "matched"


def test_cli_suite_keeps_all_matrix_requirement_independent_of_contract_policy(
    tmp_path, monkeypatch, capsys
):
    result = evaluation("default", "one")
    result.update(require_contract=True, matrix_contract={"status": "matched"})
    paths = mock_evaluations(monkeypatch, tmp_path, [result])
    monkeypatch.setattr(
        "sys.argv",
        [
            "veriagent",
            "review-browser-suite",
            str(paths[0]),
            "--require-contract",
            "--require-all",
            "--format",
            "json",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["evidence_passed"] and not output["selection_passed"]
    assert output["require_contract"] and output["counts"] is None
